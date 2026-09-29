"""SanMar's SFTP server, and readers for the data files on it.

Every reader is a generator: rows are parsed one at a time as the file is read, so even
SanMar's largest files never sit in memory. Readers take a path to a local file or an open
text stream, so the same code parses a file streamed by :class:`SanMarFTP` or one
downloaded some other way.
"""

from .catalog import (
    CatalogProduct,
    ProductInformation,
    ProductRecord,
    read_catalog,
    read_extended_catalog,
    read_product_information,
)
from .client import SanMarFTP
from .inventory import WarehouseInventory, read_active_products, read_warehouse_inventory
from .legacy import SaleItem, TextFileProduct, TextFileRecord, read_catalog_txt, read_pdd, read_sale_items
from .orders import (
    HoldingLine,
    OrderFiles,
    ShipmentStatus,
    read_holding,
    read_shipment_status,
    render_order_files,
    render_release_file,
)
from .pricing import CustomerPrice, PriceChange, read_customer_prices, read_price_changes

__all__ = [
    "CatalogProduct",
    "CustomerPrice",
    "HoldingLine",
    "OrderFiles",
    "PriceChange",
    "ProductInformation",
    "ProductRecord",
    "SaleItem",
    "SanMarFTP",
    "ShipmentStatus",
    "TextFileProduct",
    "TextFileRecord",
    "WarehouseInventory",
    "read_active_products",
    "read_catalog",
    "read_catalog_txt",
    "read_customer_prices",
    "read_extended_catalog",
    "read_holding",
    "read_pdd",
    "read_price_changes",
    "read_product_information",
    "read_sale_items",
    "read_shipment_status",
    "read_warehouse_inventory",
    "render_order_files",
    "render_release_file",
]
