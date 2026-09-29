"""Recording and replaying SanMar's WSDLs, so tests run through zeep without SanMar.

``scripts/snapshot_wsdls.py`` records every WSDL and schema document zeep loads into a
directory with an ``index.json``. Tests load that directory into :class:`ReplayTransport`,
which serves the documents back to zeep and answers each call with a queued response, so a
payload is validated against SanMar's real schema and a response is parsed exactly as it
would be in production.

Documents are keyed by path and query only, without the host, so one snapshot serves both
environments and survives SanMar writing an internal hostname into a schema import.
"""

import json
import re
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import requests
from zeep import Transport
from zeep.wsdl.utils import etree_to_string

if TYPE_CHECKING:
    from pathlib import Path

INDEX_FILE = "index.json"


def document_key(url: str) -> str:
    """Return the host-independent key a document is stored under."""
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}" if parts.query else parts.path


@dataclass
class WsdlSnapshot:
    """WSDL and schema documents, keyed by :func:`document_key`."""

    documents: dict[str, bytes] = field(default_factory=dict)

    @classmethod
    def load(cls, directory: Path) -> WsdlSnapshot:
        """Load a snapshot written by :meth:`save`."""
        index = json.loads((directory / INDEX_FILE).read_text(encoding="utf-8"))
        return cls({key: (directory / name).read_bytes() for key, name in index["documents"].items()})

    def save(self, directory: Path, **metadata: Any) -> None:  # noqa: ANN401 - free-form, JSON-serializable
        """Write every document to ``directory``, alongside an index of their keys."""
        directory.mkdir(parents=True, exist_ok=True)
        names: dict[str, str] = {}
        for key in sorted(self.documents):
            stem = re.sub(r"[^A-Za-z0-9]+", "_", key).strip("_")
            name = f"{stem}.xml"
            suffix = 1
            while name in names.values():
                suffix += 1
                name = f"{stem}_{suffix}.xml"
            names[key] = name
            (directory / name).write_bytes(self.documents[key])
        index = {**metadata, "documents": names}
        (directory / INDEX_FILE).write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class RecordingTransport(Transport):
    """A transport that keeps a copy of every document zeep loads."""

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401 - forwarded to zeep's Transport
        """Create the transport; keyword arguments go to zeep's :class:`~zeep.Transport`."""
        super().__init__(**kwargs)  # type: ignore[no-untyped-call]  # mypy's untyped_calls_exclude misses super()
        self.snapshot = WsdlSnapshot()

    def load(self, url: str) -> bytes:
        """Load a document as usual, and record it."""
        content: bytes = super().load(url)  # type: ignore[no-untyped-call]
        self.snapshot.documents[document_key(url)] = content
        return content


class ReplayTransport(Transport):
    """A transport that serves recorded documents and answers calls from a queue.

    Every envelope zeep sends is kept in :attr:`sent`, as ``(address, body)``.
    """

    def __init__(self, snapshot: WsdlSnapshot) -> None:
        """Serve documents from ``snapshot``; no call is answered until one is queued."""
        super().__init__()  # type: ignore[no-untyped-call]
        self.snapshot = snapshot
        self.sent: list[tuple[str, bytes]] = []
        self._responses: deque[tuple[int, bytes]] = deque()

    def queue(self, content: bytes | str, status: int = 200) -> None:
        """Queue the response to the next call."""
        self._responses.append((status, content.encode() if isinstance(content, str) else content))

    def load(self, url: str) -> bytes:
        """Serve a recorded document."""
        try:
            return self.snapshot.documents[document_key(url)]
        except KeyError:
            message = f"No recorded document for {url}; re-run scripts/snapshot_wsdls.py."
            raise LookupError(message) from None

    def post_xml(self, address: str, envelope: Any, headers: dict[str, str]) -> requests.Response:  # noqa: ANN401, ARG002 - zeep's signature
        """Record the envelope and answer with the next queued response."""
        self.sent.append((address, etree_to_string(envelope)))
        if not self._responses:
            message = f"No response queued for the call to {address}."
            raise LookupError(message)
        status, content = self._responses.popleft()
        response = requests.Response()
        response.status_code = status
        response._content = content  # noqa: SLF001 - building a canned response
        response.headers["Content-Type"] = "text/xml; charset=utf-8"
        response.encoding = "utf-8"
        response.url = address
        return response
