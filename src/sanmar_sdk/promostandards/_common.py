"""What SanMar's PromoStandards services share: the login, and how they report errors.

PromoStandards services report problems as coded messages in the response body rather than
as SOAP faults: a ``ServiceMessageArray`` of messages with a severity, or a single
``ErrorMessage`` (spelled ``errorMessage`` by some services). The code decides which of
the SDK's exceptions is raised; information and warnings go to the ``sanmar_sdk`` logger.
"""

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BeforeValidator

from sanmar_sdk._soap import Service
from sanmar_sdk.base import Record
from sanmar_sdk.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RequestError,
    ServiceError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sanmar_sdk._soap import Endpoint

    from ._wire import Login

logger = logging.getLogger("sanmar_sdk")

NO_RESULTS = 160
"""The code SanMar sends when a query matched nothing."""

REFERENCE_NOT_FOUND = 301

_REFERENCE_NOTE = (
    " SanMar reports an order here only once it has processed it, and an invoice only once the "
    "order has shipped and been invoiced. Wait at least 24 hours before asking again; if SanMar "
    "still cannot find it after 48, the order may not have reached SanMar."
)

_ERRORS: dict[int, type[ServiceError]] = {
    100: AuthenticationError,
    104: AuthorizationError,
    105: AuthenticationError,
    110: AuthenticationError,
    115: RequestError,
    120: RequestError,
    125: RequestError,
    130: NotFoundError,
    135: NotFoundError,
    140: NotFoundError,
    145: NotFoundError,
    150: NotFoundError,
    155: RequestError,
    NO_RESULTS: NotFoundError,
    200: NotFoundError,
    300: RequestError,
    REFERENCE_NOT_FOUND: NotFoundError,
    302: RequestError,
    303: RequestError,
}
"""The SDK exception for each code in the Web Services Integration Guide's error table."""


class ServiceMessage(Record):
    """One message in a PromoStandards response."""

    code: int
    description: str = ""
    severity: str = "Error"
    """``Error``, ``Warning`` or ``Information``. ``ErrorMessage`` elements have none."""

    @property
    def is_error(self) -> bool:
        """Whether the message reports a failure."""
        return self.severity.casefold() == "error"

    def error(self) -> ServiceError:
        """Build the SDK exception for this message."""
        description = self.description or "SanMar reported an error without a description."
        if self.code == REFERENCE_NOT_FOUND:
            description += _REFERENCE_NOTE
        return _ERRORS.get(self.code, ServiceError)(description, code=self.code)


def pluck(key: str) -> BeforeValidator:
    """Read a list of one-field elements, such as ``ProductKeyword``, as a list of values."""

    def values(items: Any) -> Any:  # noqa: ANN401 - runs before validation
        if isinstance(items, list):
            return [item.get(key) if isinstance(item, dict) else item for item in items]
        return items

    return BeforeValidator(values)


def messages(result: Mapping[str, Any]) -> list[ServiceMessage]:
    """Collect every message in a response, whichever way the service reports them."""
    found: list[ServiceMessage] = []
    array = result.get("ServiceMessageArray")
    if isinstance(array, dict):
        found.extend(ServiceMessage.model_validate(message) for message in array.get("ServiceMessage") or [])
    found.extend(
        ServiceMessage.model_validate(result[key]) for key in ("ErrorMessage", "errorMessage") if result.get(key)
    )
    return found


def check(result: Mapping[str, Any], *, allow_empty: bool = False) -> bool:
    """Raise the SDK exception for an error SanMar reported, and log everything else.

    Returns ``True`` when SanMar reported that nothing matched (code 160) and
    ``allow_empty`` is set, so a list method can return an empty list; otherwise that is
    a :class:`~sanmar_sdk.NotFoundError` like any other.
    """
    empty = False
    for message in messages(result):
        if message.code == NO_RESULTS and allow_empty:
            empty = True
        elif message.is_error:
            raise message.error()
        elif message.severity.casefold() == "warning":
            logger.warning("SanMar: %s (%s)", message.description, message.code)
        else:
            logger.debug("SanMar: %s (%s)", message.description, message.code)
    return empty


class PromoStandardsService(Service):
    """One of SanMar's PromoStandards services, at the version SanMar implements."""

    endpoint: ClassVar[Endpoint]
    version: ClassVar[str]
    """The PromoStandards version SanMar implements, sent as ``wsVersion``."""

    def _call(self, operation: str, request: Mapping[str, object]) -> dict[str, Any]:
        """Call an operation with the login added, and return its response as plain data."""
        login: Login = {
            "wsVersion": self.version,
            "id": self._credentials.username,
            "password": self._credentials.password,
        }
        result: dict[str, Any] = self._soap.call(self.endpoint, (operation,), {**login, **request})
        return result
