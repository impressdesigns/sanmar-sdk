"""A small in-process SFTP server, serving a local folder, for testing the SFTP client."""

import os
import socket
import threading
from pathlib import Path, PurePosixPath
from typing import IO, Any

import paramiko
from paramiko.common import AUTH_FAILED, AUTH_SUCCESSFUL, OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED, OPEN_SUCCEEDED
from paramiko.sftp import SFTP_NO_SUCH_FILE


class _Server(paramiko.ServerInterface):
    """Accepts one username and password, and SFTP sessions."""

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    def check_auth_password(self, username: str, password: str) -> int:
        if (username, password) == (self.username, self.password):
            return AUTH_SUCCESSFUL
        return AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:  # noqa: ARG002 - paramiko's signature
        return "password"

    def check_channel_request(self, kind: str, chanid: int) -> int:  # noqa: ARG002 - paramiko's signature
        if kind == "session":
            return OPEN_SUCCEEDED
        return OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED


class _Handle(paramiko.SFTPHandle):
    """An open file, read or written through the handle's own file object.

    paramiko's handle reads and writes through ``readfile`` and ``writefile`` when they
    are set, which its stubs do not declare.
    """

    readfile: IO[bytes]
    writefile: IO[bytes]

    def stat(self) -> paramiko.SFTPAttributes:
        return paramiko.SFTPAttributes.from_stat(os.fstat(self.readfile.fileno()))


class _Files(paramiko.SFTPServerInterface):
    """Serves the files under ``root``."""

    def __init__(self, server: paramiko.ServerInterface, *, root: Path, **kwargs: Any) -> None:  # noqa: ANN401 - paramiko's signature
        super().__init__(server, **kwargs)
        self.root = root

    def _local(self, path: str) -> Path:
        return self.root / PurePosixPath(self.canonicalize(path)).relative_to("/")

    def canonicalize(self, path: str) -> str:
        parts: list[str] = []
        for part in PurePosixPath("/", path).parts[1:]:
            if part == "..":
                if parts:
                    parts.pop()
            elif part != ".":
                parts.append(part)
        return "/" + "/".join(parts)

    def list_folder(self, path: str) -> list[paramiko.SFTPAttributes] | int:
        folder = self._local(path)
        if not folder.is_dir():
            return SFTP_NO_SUCH_FILE
        return [paramiko.SFTPAttributes.from_stat(entry.stat(), filename=entry.name) for entry in folder.iterdir()]

    def stat(self, path: str) -> paramiko.SFTPAttributes | int:
        local = self._local(path)
        if not local.exists():
            return SFTP_NO_SUCH_FILE
        return paramiko.SFTPAttributes.from_stat(local.stat())

    lstat = stat

    def open(self, path: str, flags: int, attr: paramiko.SFTPAttributes) -> _Handle | int:  # noqa: ARG002 - paramiko's signature
        local = self._local(path)
        writing = flags & (os.O_WRONLY | os.O_RDWR)
        if not writing and not local.is_file():
            return SFTP_NO_SUCH_FILE
        handle = _Handle(flags)
        file = local.open("wb" if writing else "rb")
        handle.readfile = file
        handle.writefile = file
        return handle


class SFTPServer:
    """An SFTP server on localhost, serving ``root`` to one username and password."""

    def __init__(self, root: Path, username: str, password: str) -> None:
        """Start listening on a free port."""
        self.root = root
        self.host_key = paramiko.ECDSAKey.generate()
        self._username = username
        self._password = password
        self._socket = socket.create_server(("127.0.0.1", 0))
        self._socket.settimeout(0.1)
        self.port: int = self._socket.getsockname()[1]
        self._stopped = threading.Event()
        self._transports: list[paramiko.Transport] = []
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    @property
    def host_key_line(self) -> str:
        """The server's public key, as ``ssh-keyscan`` would print it."""
        return f"[127.0.0.1]:{self.port} {self.host_key.get_name()} {self.host_key.get_base64()}"

    def _serve(self) -> None:
        while not self._stopped.is_set():
            try:
                connection, _ = self._socket.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            transport = paramiko.Transport(connection)
            transport.add_server_key(self.host_key)
            transport.set_subsystem_handler("sftp", paramiko.SFTPServer, _Files, root=self.root)
            self._transports.append(transport)
            try:
                transport.start_server(server=_Server(self._username, self._password))
            except paramiko.SSHException, EOFError, OSError:
                # The client hung up during the handshake, as it does when it refuses the
                # host key; keep serving the next connection.
                transport.close()

    def close(self) -> None:
        """Stop serving and drop every connection."""
        self._stopped.set()
        self._socket.close()
        self._thread.join()
        for transport in self._transports:
            transport.close()
