"""The request payloads of SanMar's PromoStandards services, as their WSDLs name them.

Each is what a service module's shaping step builds from a caller's arguments, and what
zeep serializes. Keys are the PromoStandards element names, so a misspelling is a type
error here rather than a rejected request. The login every request starts with is added by
:meth:`~sanmar_sdk.promostandards._common.PromoStandardsService._call`.
"""

from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from datetime import date, datetime
    from decimal import Decimal


class Login(TypedDict):
    """The version and login every PromoStandards request starts with."""

    wsVersion: str
    id: str
    password: str


class GetProductRequest(TypedDict):
    """Product Data ``getProduct``."""

    localizationCountry: str
    localizationLanguage: str
    productId: str
    partId: NotRequired[str]
    colorName: NotRequired[str]


class GetProductCloseOutRequest(TypedDict):
    """Product Data ``getProductCloseOut``, which takes nothing but the login."""


class GetProductDateModifiedRequest(TypedDict):
    """Product Data ``getProductDateModified``."""

    changeTimeStamp: datetime


class GetProductSellableRequest(TypedDict):
    """Product Data ``getProductSellable``."""

    productId: NotRequired[str]
    partId: NotRequired[str]
    isSellable: bool


class GetMediaContentRequest(TypedDict):
    """Media Content ``getMediaContent``."""

    mediaType: str
    productId: str
    partId: NotRequired[str]
    classType: NotRequired[int]


class PartIdArray(TypedDict):
    """``partIdArray``."""

    partId: list[str]


class LabelSizeArray(TypedDict):
    """``LabelSizeArray``."""

    labelSize: list[str]


class PartColorArray(TypedDict):
    """``PartColorArray``."""

    partColor: list[str]


class InventoryFilter(TypedDict, total=False):
    """Inventory ``Filter``: by part ids, or by sizes and colors."""

    partIdArray: PartIdArray
    LabelSizeArray: LabelSizeArray
    PartColorArray: PartColorArray


class GetInventoryLevelsRequest(TypedDict):
    """Inventory ``getInventoryLevels``."""

    productId: str
    Filter: NotRequired[InventoryFilter]


class GetConfigurationAndPricingRequest(TypedDict):
    """Pricing and Configuration ``getConfigurationAndPricing``."""

    productId: str
    partId: NotRequired[str]
    currency: str
    fobId: str
    priceType: str
    localizationCountry: str
    localizationLanguage: str
    configurationType: str


class GetFobPointsRequest(TypedDict):
    """Pricing and Configuration ``getFobPoints``."""

    productId: str
    localizationCountry: str
    localizationLanguage: str


class GetOrderShipmentNotificationRequest(TypedDict):
    """Order Shipment Notification ``getOrderShipmentNotification``."""

    queryType: str
    referenceNumber: NotRequired[str]
    shipmentDateTimeStamp: NotRequired[datetime]


class GetOrderStatusRequest(TypedDict):
    """Order Status ``getOrderStatus``."""

    queryType: str
    referenceNumber: NotRequired[str]
    statusTimeStamp: NotRequired[datetime]
    returnIssueDetailType: str
    returnProductDetail: bool


class GetServiceMethodsRequest(TypedDict):
    """Order Status ``getServiceMethods``, which takes nothing but the login."""


class GetInvoicesRequest(TypedDict):
    """Invoice ``getInvoices``."""

    queryType: str
    referenceNumber: NotRequired[str]
    requestedDate: NotRequired[date]
    availableTimeStamp: NotRequired[datetime]


class Quantity(TypedDict):
    """A PO ``Quantity``."""

    uom: str
    value: int


class Part(TypedDict):
    """A PO ``Part``: one SanMar unique key and how many of it."""

    partId: str
    customerSupplied: bool
    Quantity: Quantity


class PartArray(TypedDict):
    """``PartArray``."""

    Part: list[Part]


class ToleranceDetails(TypedDict):
    """``ToleranceDetails``."""

    tolerance: str


class LineItem(TypedDict):
    """A PO ``LineItem``."""

    lineNumber: int
    description: str
    lineType: str
    fobId: NotRequired[str]
    ToleranceDetails: ToleranceDetails
    allowPartialShipments: bool
    lineItemTotal: Decimal
    PartArray: PartArray


class LineItemArray(TypedDict):
    """``LineItemArray``."""

    LineItem: list[LineItem]


class ContactDetails(TypedDict):
    """A PO ``ContactDetails``. SanMar says to leave out what it does not use."""

    address1: str
    city: str
    region: str
    postalCode: str
    country: str
    attentionTo: NotRequired[str]
    companyName: NotRequired[str]
    address2: NotRequired[str]
    email: NotRequired[str]
    phone: NotRequired[str]


class ShipTo(TypedDict):
    """A PO shipment's ``ShipTo``."""

    customerPickup: bool
    ContactDetails: ContactDetails
    shipmentId: int


class FreightDetails(TypedDict):
    """``FreightDetails``: the carrier, and the carrier's service."""

    carrier: str
    service: str


class Shipment(TypedDict):
    """A PO ``Shipment``."""

    shipReferences: list[str]
    allowConsolidation: bool
    blindShip: bool
    packingListRequired: bool
    FreightDetails: FreightDetails
    ShipTo: ShipTo


class ShipmentArray(TypedDict):
    """``ShipmentArray``."""

    Shipment: list[Shipment]


class PurchaseOrder(TypedDict):
    """A PromoStandards ``PO``."""

    orderType: str
    orderNumber: str
    orderDate: datetime
    totalAmount: Decimal
    rush: bool
    currency: str
    ShipmentArray: ShipmentArray
    LineItemArray: LineItemArray
    termsAndConditions: str


class SendPORequest(TypedDict):
    """Purchase Order ``sendPO``."""

    PO: PurchaseOrder


class GetSupportedOrderTypesRequest(TypedDict):
    """Purchase Order ``getSupportedOrderTypes``, which takes nothing but the login."""
