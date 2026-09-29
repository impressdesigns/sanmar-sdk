"""SOAP plumbing shared by every SanMar web service.

Each service module shapes a caller's model into a payload and hands it to
:meth:`SoapClient.call`, which owns everything zeep-specific: loading WSDLs, pointing them
at the right environment, finding the operation, translating errors, and turning zeep's
response objects into plain data for a :class:`~sanmar_sdk.base.Record` to validate.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit, urlunsplit

import requests
from zeep import Client, Transport
from zeep.exceptions import Error as ZeepError
from zeep.exceptions import Fault, TransportError
from zeep.helpers import serialize_object
from zeep.proxy import OperationProxy, ServiceProxy
from zeep.wsdl.bindings.soap import Soap11Binding

from .exceptions import ResponseError, SanMarConnectionError, SoapFaultError

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from .common import Environment


@dataclass(frozen=True, slots=True)
class Endpoint:
    """One SanMar web service, identified by its WSDL's path on either environment's host."""

    name: str
    path: str
    alternate_paths: tuple[str, ...] = ()
    """Other paths the guides give for the same service. The SDK calls ``path``."""

    def wsdl_url(self, environment: Environment) -> str:
        """Return the service's WSDL URL on the given environment."""
        return f"{environment.value}{self.path}"


PRODUCT_INFO = Endpoint("SanMar Standard Product Info", "/SanMarWebService/SanMarProductInfoServicePort?wsdl")
INVENTORY = Endpoint("SanMar Product Inventory", "/SanMarWebService/SanMarWebServicePort?wsdl")
PRICING = Endpoint("SanMar Pricing", "/SanMarWebService/SanMarPricingServicePort?wsdl")
INVOICING = Endpoint("SanMar Standard Invoicing", "/SanMarWebService/InvoicePort?wsdl")
PURCHASE_ORDER = Endpoint("SanMar Standard Purchase Order", "/SanMarWebService/SanMarPOServicePort?wsdl")
PACKING_SLIP = Endpoint(
    "SanMar License Plate Number (Packing Slip)",
    "/SanMarWebService/webservices/PackingSlipService?wsdl",
)
PROMOSTANDARDS_PRODUCT_DATA = Endpoint(
    "PromoStandards Product Data 2.0.0",
    "/promostandards/ProductDataServiceV2.xml?wsdl",
    alternate_paths=("/promostandards/ProductDataServiceBindingV2?WSDL",),
)
PROMOSTANDARDS_MEDIA_CONTENT = Endpoint(
    "PromoStandards Media Content 1.1.0",
    "/promostandards/MediaContentServiceBinding?wsdl",
)
PROMOSTANDARDS_INVENTORY = Endpoint(
    "PromoStandards Inventory 2.0.0",
    "/promostandards/InventoryServiceBindingV2final?WSDL",
)
PROMOSTANDARDS_PRICING = Endpoint(
    "PromoStandards Pricing and Configuration 1.0.0",
    "/promostandards/PricingAndConfigurationServiceBinding?WSDL",
)
PROMOSTANDARDS_SHIPMENT_NOTIFICATION = Endpoint(
    "PromoStandards Order Shipment Notification 1.0.0",
    "/promostandards/OrderShipmentNotificationServiceBinding?wsdl",
)
PROMOSTANDARDS_ORDER_STATUS = Endpoint(
    "PromoStandards Order Status 2.0.0",
    "/promostandards/OrderStatusServiceBindingV2?wsdl",
)
PROMOSTANDARDS_INVOICE = Endpoint(
    "PromoStandards Invoice 1.0.0",
    "/promostandards/InvoiceServiceBindingV1_0_0?WSDL",
)
PROMOSTANDARDS_PURCHASE_ORDER = Endpoint(
    "PromoStandards Purchase Order 1.0.0",
    "/promostandards/POServiceBinding?WSDL",
)

ENDPOINTS = (
    PRODUCT_INFO,
    INVENTORY,
    PRICING,
    INVOICING,
    PURCHASE_ORDER,
    PACKING_SLIP,
    PROMOSTANDARDS_PRODUCT_DATA,
    PROMOSTANDARDS_MEDIA_CONTENT,
    PROMOSTANDARDS_INVENTORY,
    PROMOSTANDARDS_PRICING,
    PROMOSTANDARDS_SHIPMENT_NOTIFICATION,
    PROMOSTANDARDS_ORDER_STATUS,
    PROMOSTANDARDS_INVOICE,
    PROMOSTANDARDS_PURCHASE_ORDER,
)
"""Every web service in the Web Services and Purchase Order integration guides."""


@dataclass(frozen=True, slots=True)
class Credentials:
    """What SanMar's web services authenticate with.

    SanMar's own services take all three; PromoStandards services take only the SanMar.com
    username and password.
    """

    customer_number: int
    username: str
    password: str = field(repr=False)


def _rebase(address: str, environment: Environment) -> str:
    """Point a WSDL's service address at the given environment's host."""
    base = urlsplit(environment.value)
    parts = urlsplit(address)
    return urlunsplit((base.scheme, base.netloc, parts.path, parts.query, parts.fragment))


def _bind(client: Client, environment: Environment) -> ServiceProxy:
    """Bind a loaded WSDL's SOAP 1.1 port to the given environment.

    The address inside a WSDL is whatever SanMar's server wrote into it, so it is replaced
    with the environment's host. That keeps a client pointed at EDEV from ever sending an
    order to production.
    """
    ports = [port for service in client.wsdl.services.values() for port in service.ports.values()]
    ports.sort(key=lambda port: not isinstance(port.binding, Soap11Binding))
    if not ports:
        message = "SanMar's WSDL defines no SOAP port."
        raise ResponseError(message)
    port = ports[0]
    return ServiceProxy(client, port.binding, address=_rebase(port.binding_options["address"], environment))


def resolve_operation(service: ServiceProxy, candidates: Sequence[str]) -> OperationProxy:
    """Find an operation by the first of its candidate names the WSDL defines.

    SanMar's guides spell some operations more than one way. An exact match wins; otherwise
    names are compared case-insensitively.
    """
    available: dict[str, OperationProxy] = dict(iter(service))
    for candidate in candidates:
        if candidate in available:
            return available[candidate]
    folded = {name.casefold(): operation for name, operation in available.items()}
    for candidate in candidates:
        if candidate.casefold() in folded:
            return folded[candidate.casefold()]
    message = f"SanMar's WSDL has no operation named {' or '.join(candidates)}; it has {', '.join(sorted(available))}."
    raise ResponseError(message)


class SoapClient:
    """Calls SanMar's web services on one environment, loading each WSDL on first use."""

    def __init__(
        self,
        environment: Environment,
        *,
        timeout: float,
        transport: Transport | None = None,
    ) -> None:
        """Prepare to call the given environment.

        ``timeout`` applies to both loading a WSDL and each call. A ``transport`` given by
        the caller is used as-is, timeouts included.
        """
        self.environment = environment
        self.transport = transport or Transport(timeout=timeout, operation_timeout=timeout)
        self._services: dict[Endpoint, ServiceProxy] = {}

    def service(self, endpoint: Endpoint) -> ServiceProxy:
        """Return the bound service for an endpoint, loading its WSDL the first time."""
        if endpoint not in self._services:
            with _translated_errors():
                # zeep parses strictly by default, and that matters here: in recover mode an
                # element SanMar sends out of schema order is dropped along with every field
                # after it, silently.
                client = Client(endpoint.wsdl_url(self.environment), transport=self.transport)
            self._services[endpoint] = _bind(client, self.environment)
        return self._services[endpoint]

    def call(self, endpoint: Endpoint, operation: Sequence[str], payload: Mapping[str, object]) -> Any:  # noqa: ANN401
        """Call an operation and return its response as plain dicts, lists and scalars.

        ``operation`` lists the names the operation may go by, in order of preference.
        """
        proxy = resolve_operation(self.service(endpoint), operation)
        with _translated_errors():
            result = proxy(**payload)
        return serialize_object(result, dict)


@contextmanager
def _translated_errors() -> Iterator[None]:
    """Re-raise zeep and requests errors as the SDK's own exceptions."""
    try:
        yield
    except Fault as exc:
        raise SoapFaultError(str(exc.message), code=None if exc.code is None else str(exc.code)) from exc
    except TransportError as exc:
        # zeep raises TransportError both for an HTTP error status and for a successful
        # response whose body is not XML at all.
        if exc.status_code == HTTPStatus.OK:
            message = f"SanMar's response is not valid XML: {exc}"
            raise ResponseError(message) from exc
        message = f"SanMar answered with HTTP {exc.status_code}."
        raise SanMarConnectionError(message) from exc
    except requests.RequestException as exc:
        message = f"Could not reach SanMar: {exc}"
        raise SanMarConnectionError(message) from exc
    except ZeepError as exc:
        message = f"Could not read SanMar's response: {exc}"
        raise ResponseError(message) from exc
