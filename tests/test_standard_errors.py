"""Testing how errors from SanMar's own services map onto the SDK's exceptions."""

import pytest

from sanmar_sdk import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RequestError,
    ServiceError,
    SoapFaultError,
)
from sanmar_sdk.standard._common import error_class, raise_error, raise_fault


@pytest.mark.parametrize(
    ("message", "error"),
    [
        ("User authentication failed.", AuthenticationError),
        ("ERROR: User authenticating failed ", AuthenticationError),
        ("Unauthenticated request", AuthenticationError),
        ("Unauthorized request", AuthorizationError),
        ("Data not found", NotFoundError),
        ("Invalid Style + Color + Size specified.", NotFoundError),
        ("Invalid warehouse specified", RequestError),
        ("' is not a valid value for 'integer'", RequestError),
        ("Value '12345678901' is not facet-valid with respect to maxInclusive", RequestError),
        ("Service unavailable", ServiceError),
    ],
)
def test_messages_map_to_exceptions(message: str, error: type[ServiceError]) -> None:
    """Each message SanMar documents picks the matching exception."""
    assert error_class(message) is error


def test_missing_message_is_still_an_error() -> None:
    """An error flag without a message still raises."""
    with pytest.raises(ServiceError, match="without a message"):
        raise_error(None)


def test_unclassified_fault_stays_a_fault() -> None:
    """A fault that matches no known message is re-raised unchanged."""
    fault = SoapFaultError("Something broke")
    with pytest.raises(SoapFaultError) as caught:
        raise_fault(fault)
    assert caught.value is fault
