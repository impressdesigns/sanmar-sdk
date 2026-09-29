"""SanMar's own web services, as opposed to its PromoStandards ones.

Each is reached through an attribute of :class:`~sanmar_sdk.client.SanMar`, such as
``sanmar.products`` or ``sanmar.purchase_orders``. They take the SanMar customer number as
well as the SanMar.com login.
"""

from .inventory import InventoryService, SkuStock, WarehouseStock
from .invoices import Address, Invoice, InvoiceHeader, InvoiceLine, InvoiceService, Party
from .packing_slips import PackingSlip, PackingSlipAddress, PackingSlipItem, PackingSlipParty, PackingSlipService
from .pricing import PriceQuote, PricingService
from .products import FileRequest, ProductImages, ProductInfo, ProductInfoService, ProductPrices
from .purchase_orders import LineAvailability, OrderCheck, PurchaseOrderService

__all__ = [
    "Address",
    "FileRequest",
    "InventoryService",
    "Invoice",
    "InvoiceHeader",
    "InvoiceLine",
    "InvoiceService",
    "LineAvailability",
    "OrderCheck",
    "PackingSlip",
    "PackingSlipAddress",
    "PackingSlipItem",
    "PackingSlipParty",
    "PackingSlipService",
    "Party",
    "PriceQuote",
    "PricingService",
    "ProductImages",
    "ProductInfo",
    "ProductInfoService",
    "ProductPrices",
    "PurchaseOrderService",
    "SkuStock",
    "WarehouseStock",
]
