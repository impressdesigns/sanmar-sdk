"""Exceptions raised by the SanMar SDK.

Every error the SDK raises on purpose is a :class:`SanMarError`, so one ``except`` clause is
enough to catch anything SanMar or the network did. Each is raised ``from`` the underlying
zeep, requests, or paramiko error, which stays available as ``__cause__``.
"""


class SanMarError(Exception):
    """Base class for every error the SDK raises."""


class SanMarConnectionError(SanMarError):
    """SanMar could not be reached, or answered with an HTTP error status.

    SanMar's web services listen on port 8080, which some networks block outright.
    """


class SoapFaultError(SanMarError):
    """SanMar answered with a SOAP fault."""

    def __init__(self, message: str, code: str | None = None) -> None:
        """Record the fault string and, when SanMar sent one, the fault code."""
        super().__init__(message)
        self.message = message
        self.code = code


class ResponseError(SanMarError):
    """SanMar's response could not be parsed, or did not match its own WSDL."""


class ServiceError(SanMarError):
    """SanMar reported an error for the request.

    ``code`` is the PromoStandards error code. SanMar's own services report a message
    without a code, so it is ``None`` for them.
    """

    def __init__(self, message: str, code: int | None = None) -> None:
        """Record SanMar's message and, when there is one, its error code."""
        super().__init__(message if code is None else f"{code}: {message}")
        self.message = message
        self.code = code


class AuthenticationError(ServiceError):
    """SanMar rejected the credentials.

    Web services use a SanMar.com username and password (plus the customer number for
    SanMar's own services). EDEV has separate credentials from production, and the SFTP
    server has its own password.
    """


class AuthorizationError(ServiceError):
    """The account is not authorized to use this service (PromoStandards code 104)."""


class NotFoundError(ServiceError):
    """SanMar has no record matching the request."""


class RequestError(ServiceError):
    """SanMar rejected the request as malformed or out of range."""


class FileFormatError(SanMarError):
    """A SanMar data file did not have the layout the SDK expects."""

    def __init__(self, message: str, line_number: int | None = None) -> None:
        """Record the problem and the 1-based line it was found on."""
        super().__init__(message if line_number is None else f"line {line_number}: {message}")
        self.message = message
        self.line_number = line_number
