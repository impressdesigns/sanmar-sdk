"""SanMar's PromoStandards web services.

Each is reached through ``sanmar.promostandards``, such as
``sanmar.promostandards.inventory``. They take the SanMar.com login but not the customer
number, and identify a style as a *product* and one style, color and size as a *part*,
whose id is SanMar's unique key.
"""

from .client import PromoStandards
from .inventory import FutureStock, InventoryService, LocationStock, PartStock
from .invoices import AccountInfo, Invoice, InvoiceLine, InvoiceService, Tax
from .media_content import ClassType, MediaClass, MediaContentService, MediaItem, MediaType
from .order_status import (
    Contact,
    ContactDetails,
    Issue,
    IssueDetail,
    OrderStatus,
    OrderStatusService,
    SalesOrderStatus,
    Status,
    StatusLine,
)
from .pricing import PartPrice, PriceBreak, PriceType, PricingService
from .product_data import (
    ApparelSize,
    Category,
    Color,
    Dimension,
    FobPoint,
    MarketingPoint,
    Packaging,
    PartReference,
    PriceGroup,
    Product,
    ProductDataService,
    ProductPart,
    ProductPrice,
    RelatedProduct,
    Specification,
)
from .purchase_orders import PromoStandardsOrder, PromoStandardsOrderLine, PurchaseOrderService
from .shipment_notification import (
    SalesOrderShipment,
    ShipmentAddress,
    ShipmentLocation,
    ShipmentNotification,
    ShipmentNotificationService,
    ShipmentPackage,
    ShippedItem,
)

__all__ = [
    "AccountInfo",
    "ApparelSize",
    "Category",
    "ClassType",
    "Color",
    "Contact",
    "ContactDetails",
    "Dimension",
    "FobPoint",
    "FutureStock",
    "InventoryService",
    "Invoice",
    "InvoiceLine",
    "InvoiceService",
    "Issue",
    "IssueDetail",
    "LocationStock",
    "MarketingPoint",
    "MediaClass",
    "MediaContentService",
    "MediaItem",
    "MediaType",
    "OrderStatus",
    "OrderStatusService",
    "Packaging",
    "PartPrice",
    "PartReference",
    "PartStock",
    "PriceBreak",
    "PriceGroup",
    "PriceType",
    "PricingService",
    "Product",
    "ProductDataService",
    "ProductPart",
    "ProductPrice",
    "PromoStandards",
    "PromoStandardsOrder",
    "PromoStandardsOrderLine",
    "PurchaseOrderService",
    "RelatedProduct",
    "SalesOrderShipment",
    "SalesOrderStatus",
    "ShipmentAddress",
    "ShipmentLocation",
    "ShipmentNotification",
    "ShipmentNotificationService",
    "ShipmentPackage",
    "ShippedItem",
    "Specification",
    "Status",
    "StatusLine",
    "Tax",
]
