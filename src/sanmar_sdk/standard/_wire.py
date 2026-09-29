"""The request payloads of SanMar's own web services, as their WSDLs name them.

Each is what a service module's shaping step builds from a caller's model, and what zeep
serializes. Keys are SanMar's element names, so a misspelling is a type error here rather
than a rejected request.
"""

from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from datetime import date


class WebServiceUser(TypedDict):
    """The login block most of SanMar's services take (``webServiceUser``)."""

    sanMarCustomerNumber: str
    sanMarUserName: str
    sanMarUserPassword: str


class ProductQuery(TypedDict):
    """One lookup for ``getProductInfoByStyleColorSize`` (``product``)."""

    style: str
    color: NotRequired[str]
    size: NotRequired[str]


class ProductInfoRequest(TypedDict):
    """``getProductInfoByStyleColorSize``: any number of lookups in one call."""

    arg0: list[ProductQuery]
    arg1: WebServiceUser


class ProductBrand(TypedDict):
    """``productBrand``."""

    brandName: str


class ProductInfoByBrandRequest(TypedDict):
    """``getProductInfoByBrand``."""

    arg0: ProductBrand
    arg1: WebServiceUser


class ProductCategory(TypedDict):
    """``productCategory``."""

    category: str


class ProductInfoByCategoryRequest(TypedDict):
    """``getProductInfoByCategory``."""

    arg0: ProductCategory
    arg1: WebServiceUser


class ProductFileRequest(TypedDict):
    """``getProductBulkInfo`` and ``getProductDeltaInfo``, whose login is ``arg0``."""

    arg0: WebServiceUser


class InventoryRequest(TypedDict):
    """``getInventoryQtyForStyleColorSize``, whose arguments are positional strings."""

    arg0: str
    """The customer number."""
    arg1: str
    """The SanMar.com username."""
    arg2: str
    """The SanMar.com password."""
    arg3: str
    """The style."""
    arg4: NotRequired[str]
    """The catalog color."""
    arg5: NotRequired[str]
    """The size."""


class WarehouseInventoryRequest(InventoryRequest):
    """``getInventoryQtyForStyleColorSizeByWhse``."""

    arg6: str
    """The warehouse number."""


class PricingItem(TypedDict):
    """One lookup for ``getPricing`` (``item``): by style, or by key."""

    style: NotRequired[str]
    color: NotRequired[str]
    size: NotRequired[str]
    inventoryKey: NotRequired[str]
    sizeIndex: NotRequired[int]


class PricingRequest(TypedDict):
    """``getPricing``: any number of lookups in one call."""

    arg0: list[PricingItem]
    arg1: WebServiceUser


class InvoiceLogin(TypedDict):
    """The login every invoicing operation takes."""

    CustomerNo: str
    UserName: str
    Password: str


class InvoiceByNumberRequest(InvoiceLogin):
    """``GetInvoiceByInvoiceNo``."""

    InvoiceNo: int


class InvoicesByPurchaseOrderRequest(InvoiceLogin):
    """``GetInvoicesByPurchaseOrderNo`` and ``GetInvoicesHeaderByPurchaseOrderNo``."""

    PurchaseOrderNo: str


class InvoicesByDateRangeRequest(InvoiceLogin):
    """``GetInvoicesByInvoiceDateRange`` and ``GetInvoicesHeaderByInvoiceDateRange``."""

    StartDate: date
    EndDate: date


class InvoicesByOrderDateRequest(InvoiceLogin):
    """``GetInvoicesByOrderDate`` and ``GetInvoicesHeaderByOrderDate``."""

    Date: date


class PurchaseOrderLine(TypedDict):
    """One line of a purchase order (``webServicePODetail``): by key, or by style."""

    quantity: int
    inventoryKey: NotRequired[str]
    sizeIndex: NotRequired[int]
    style: NotRequired[str]
    color: NotRequired[str]
    size: NotRequired[str]
    whseNo: NotRequired[int]


class PurchaseOrder(TypedDict):
    """A purchase order (``webServicePO``). SanMar says to leave out what it does not use."""

    poNum: str
    shipAddress1: str
    shipCity: str
    shipState: str
    shipZip: str
    shipMethod: str
    residence: str
    webServicePoDetailList: list[PurchaseOrderLine]
    attention: NotRequired[str]
    shipAddress2: NotRequired[str]
    shipEmail: NotRequired[str]
    shipTo: NotRequired[str]


class PurchaseOrderRequest(TypedDict):
    """``getPreSubmitInfo`` and ``submitPO``."""

    arg0: PurchaseOrder
    arg1: WebServiceUser


class PackingSlipRequest(TypedDict):
    """``GetPackingSlip``."""

    wsVersion: str
    UserId: str
    Password: str
    PackingSlipId: str
