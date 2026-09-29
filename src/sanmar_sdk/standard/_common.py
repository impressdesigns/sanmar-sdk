"""What SanMar's own services share: their login block, and how they report errors.

SanMar's own services report a failure as a flag and a message, or as a SOAP fault, never
as a code. The message decides which of the SDK's exceptions is raised.
"""

from typing import TYPE_CHECKING, NoReturn

from sanmar_sdk.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RequestError,
    ServiceError,
    SoapFaultError,
)

if TYPE_CHECKING:
    from sanmar_sdk._soap import Credentials

    from ._wire import WebServiceUser

COLOR_HINT = (
    " SanMar matches colors by catalog (mainframe) color, as in the SANMAR_MAINFRAME_COLOR "
    "column of SanMar_SDL_N.csv, not by the display name in COLOR_NAME."
)


def web_service_user(credentials: Credentials) -> WebServiceUser:
    """Build the login block most of SanMar's services take."""
    return {
        "sanMarCustomerNumber": str(credentials.customer_number),
        "sanMarUserName": credentials.username,
        "sanMarUserPassword": credentials.password,
    }


def error_class(message: str) -> type[ServiceError]:
    """Pick the exception for a SanMar error message."""
    text = message.casefold()
    if "authentica" in text:
        return AuthenticationError
    if "unauthorized" in text:
        return AuthorizationError
    if "not found" in text or "no data" in text or "invalid style" in text:
        return NotFoundError
    if "invalid" in text or "not a valid value" in text or "not facet-valid" in text:
        return RequestError
    return ServiceError


def raise_error(message: str | None, *, color_hint: bool = False) -> NoReturn:
    """Raise the SDK exception for an error SanMar reported.

    ``color_hint`` adds a reminder about catalog colors when the request named a color and
    SanMar could not find it, the most common cause of that failure.
    """
    text = message or "SanMar reported an error without a message."
    error = error_class(text)
    if color_hint and error is NotFoundError:
        text += COLOR_HINT
    raise error(text)


def raise_fault(fault: SoapFaultError) -> NoReturn:
    """Re-raise a SOAP fault from one of SanMar's own services as the matching error."""
    error = error_class(fault.message)
    if error is ServiceError:
        raise fault
    raise error(fault.message) from fault
