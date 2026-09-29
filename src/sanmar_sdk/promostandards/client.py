"""The PromoStandards services, grouped under :attr:`sanmar_sdk.SanMar.promostandards`."""

from typing import TYPE_CHECKING

from .inventory import InventoryService
from .invoices import InvoiceService
from .media_content import MediaContentService
from .order_status import OrderStatusService
from .pricing import PricingService
from .product_data import ProductDataService
from .purchase_orders import PurchaseOrderService
from .shipment_notification import ShipmentNotificationService

if TYPE_CHECKING:
    from sanmar_sdk._soap import Credentials, SoapClient


class PromoStandards:
    """SanMar's PromoStandards services, which take only the SanMar.com login."""

    def __init__(self, soap: SoapClient, credentials: Credentials) -> None:
        """Share the client's connection and login."""
        self.product_data = ProductDataService(soap, credentials)
        """Product Data 2.0.0."""
        self.media_content = MediaContentService(soap, credentials)
        """Media Content 1.1.0."""
        self.inventory = InventoryService(soap, credentials)
        """Inventory 2.0.0."""
        self.pricing = PricingService(soap, credentials)
        """Pricing and Configuration 1.0.0."""
        self.order_status = OrderStatusService(soap, credentials)
        """Order Status 2.0.0."""
        self.shipment_notifications = ShipmentNotificationService(soap, credentials)
        """Order Shipment Notification 1.0.0."""
        self.invoices = InvoiceService(soap, credentials)
        """Invoice 1.0.0."""
        self.purchase_orders = PurchaseOrderService(soap, credentials)
        """Purchase Order 1.0.0."""
