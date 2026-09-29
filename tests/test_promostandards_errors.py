"""Testing how PromoStandards error codes become the SDK's exceptions."""

import pytest

from sanmar_sdk import AuthenticationError, AuthorizationError, NotFoundError, RequestError, ResponseError, ServiceError

from .replay import envelope, replay_client, service_message

NAMESPACES = (
    'xmlns:ns2="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/" '
    'xmlns="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/"'
)


def _message(code: int, severity: str = "Error") -> str:
    return envelope(
        f"""<ns2:GetProductCloseOutResponse {NAMESPACES}>
          {service_message(code, f"Message {code}", severity)}
        </ns2:GetProductCloseOutResponse>""",
    )


@pytest.mark.parametrize(
    ("code", "error"),
    [
        (100, AuthenticationError),
        (104, AuthorizationError),
        (105, AuthenticationError),
        (110, AuthenticationError),
        (115, RequestError),
        (120, RequestError),
        (125, RequestError),
        (130, NotFoundError),
        (135, NotFoundError),
        (140, NotFoundError),
        (145, NotFoundError),
        (150, NotFoundError),
        (155, RequestError),
        (200, NotFoundError),
        (300, RequestError),
        (301, NotFoundError),
        (302, RequestError),
        (303, RequestError),
        (999, ServiceError),
        (12345, ServiceError),
    ],
)
def test_every_code_in_the_guide_has_its_exception(code: int, error: type[ServiceError]) -> None:
    """Each code in the guide's error table raises its exception, carrying the code."""
    sanmar, transport = replay_client()
    transport.queue(_message(code))

    with pytest.raises(error, match=f"^{code}: Message {code}") as raised:
        sanmar.promostandards.product_data.closeouts()
    assert type(raised.value) is error
    assert raised.value.code == code


def test_no_results_is_empty_for_lists() -> None:
    """Code 160 means an empty list, not an error, from a list method."""
    sanmar, transport = replay_client()
    transport.queue(_message(160))

    assert sanmar.promostandards.product_data.closeouts() == []


def test_an_error_code_with_a_lesser_severity_is_not_raised() -> None:
    """Only messages marked as errors are raised."""
    sanmar, transport = replay_client()
    transport.queue(_message(130, severity="Warning"))

    assert sanmar.promostandards.product_data.closeouts() == []


def test_empty_body_is_a_response_error() -> None:
    """A SOAP body with nothing in it is a ResponseError, not zeep's IndexError."""
    sanmar, transport = replay_client()
    transport.queue(envelope(""))

    with pytest.raises(ResponseError, match="empty SOAP body"):
        sanmar.promostandards.product_data.closeouts()


def _no_results(response: str, service: str, style: str) -> str:
    """Build a response reporting code 160 the way the service reports errors."""
    messages = {
        "ServiceMessageArray": service_message(160, "No Results Found"),
        "ErrorMessage": "<ErrorMessage><code>160</code><description>No Results Found</description></ErrorMessage>",
        "errorMessage": "<errorMessage><code>160</code><description>No Results Found</description></errorMessage>",
    }
    namespaces = (
        f'xmlns:ns2="http://www.promostandards.org/WSDL/{service}/" '
        f'xmlns="http://www.promostandards.org/WSDL/{service}/SharedObjects/"'
    )
    return envelope(f"<ns2:{response} {namespaces}>{messages[style]}</ns2:{response}>")


@pytest.mark.parametrize(
    ("service", "method", "arguments", "response"),
    [
        (
            "media_content",
            "get",
            ("K420",),
            _no_results("GetMediaContentResponse", "MediaService/1.0.0", "errorMessage"),
        ),
        (
            "inventory",
            "get",
            ("K420",),
            _no_results("GetInventoryLevelsResponse", "Inventory/2.0.0", "ServiceMessageArray"),
        ),
        (
            "pricing",
            "get",
            ("K500",),
            _no_results("GetConfigurationAndPricingResponse", "PricingAndConfiguration/1.0.0", "ErrorMessage"),
        ),
        (
            "pricing",
            "fob_points",
            ("K500",),
            _no_results("GetFobPointsResponse", "PricingAndConfiguration/1.0.0", "ErrorMessage"),
        ),
        (
            "order_status",
            "service_methods",
            (),
            _no_results("GetServiceMethodsResponse", "OrderStatus/2.0.0", "ServiceMessageArray"),
        ),
        (
            "shipment_notifications",
            "by_sales_order",
            ("1112223334",),
            _no_results(
                "GetOrderShipmentNotificationResponse",
                "OrderShipmentNotificationService/1.0.0",
                "errorMessage",
            ),
        ),
    ],
)
def test_every_list_method_treats_no_results_as_empty(
    service: str,
    method: str,
    arguments: tuple[str, ...],
    response: str,
) -> None:
    """Every list method returns an empty list for code 160, however the service reports it."""
    sanmar, transport = replay_client()
    transport.queue(response)

    assert getattr(getattr(sanmar.promostandards, service), method)(*arguments) == []
