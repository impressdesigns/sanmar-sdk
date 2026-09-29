"""The SanMar integration guides this SDK is written against.

SanMar documents its web services, purchase orders, and FTP data files in three PDFs,
revised a few times a year. Behavior the guides contradict themselves on is settled by
SanMar's WSDLs where possible; the rest is listed in the documentation's sources page.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Guide:
    """One revision of a SanMar integration guide."""

    title: str
    version: str
    updated: str
    """The revision date printed on the guide's cover."""
    url: str


WEB_SERVICES_GUIDE = Guide(
    title="SanMar Web Services Integration Guide",
    version="24.6",
    updated="August 2026",
    url="https://www.sanmar.com/medias/sys_master/pdf/h7a/ha0/33815499964446/SanMar-Web-Services-Integration-Guide-24.6/SanMar-Web-Services-Integration-Guide-24.6.pdf",
)
"""Product, inventory, pricing, invoicing, order status, and packing slip services."""

PURCHASE_ORDER_GUIDE = Guide(
    title="SanMar Purchase Order Integration Guide",
    version="24.5",
    updated="August 2026",
    url="https://www.sanmar.com/medias/sys_master/root/h4b/ha7/33815499767838/SanMar-Purchase-Order-Integration-Guide-24.5/SanMar-Purchase-Order-Integration-Guide-24.5.pdf",
)
"""Ordering through SanMar's own service, PromoStandards, or order files over SFTP."""

FTP_GUIDE = Guide(
    title="SanMar FTP Integration Guide",
    version="23.6",
    updated="August 2026",
    url="https://www.sanmar.com/medias/sys_master/root/h08/hae/33815499571230/SanMar-FTP-Integration-Guide-v23.6/SanMar-FTP-Integration-Guide-v23.6.pdf",
)
"""The product, inventory, pricing, and order status files on SanMar's SFTP server."""

GUIDES = (WEB_SERVICES_GUIDE, PURCHASE_ORDER_GUIDE, FTP_GUIDE)
