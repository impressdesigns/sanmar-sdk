"""SanMar's PromoStandards Invoice service, version 1.0.0.

Finds invoices by purchase order, by invoice number, by invoice date, or everything
invoiced since a point in time. SanMar invoices once a day, after 9 p.m. Pacific, for what
shipped that day, and asks that this service be called after 3 p.m. Pacific the next day.
SanMar does not implement ``getVoidedInvoices``.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import AliasPath, Field

from sanmar_sdk._soap import PROMOSTANDARDS_INVOICE
from sanmar_sdk.base import Record
from sanmar_sdk.exceptions import NotFoundError

from ._common import PromoStandardsService, check

if TYPE_CHECKING:
    from ._wire import GetInvoicesRequest


class AccountInfo(Record):
    """The account and address an invoice is billed or sold to."""

    account_name: str | None = Field(default=None, validation_alias="accountName")
    account_number: str | None = Field(default=None, validation_alias="accountNumber")
    attention_to: str | None = Field(default=None, validation_alias="attentionTo")
    address1: str | None = Field(default=None, validation_alias="Address1")
    address2: str | None = Field(default=None, validation_alias="Address2")
    address3: str | None = Field(default=None, validation_alias="Address3")
    city: str | None = None
    region: str | None = None
    """The state."""
    postal_code: str | None = Field(default=None, validation_alias="postalCode")
    country: str | None = None
    email: str | None = None
    phone: str | None = None


class InvoiceLine(Record):
    """One line of an invoice."""

    invoice_quantity: Decimal = Field(validation_alias="invoiceQuantity")
    uom: str = Field(validation_alias="quantityUOM")
    description: str = Field(validation_alias="lineItemDescription")
    unit_price: Decimal = Field(validation_alias="unitPrice")
    extended_price: Decimal = Field(validation_alias="extendedPrice")
    line_number: Decimal | None = Field(default=None, validation_alias="invoiceLineItemNumber")
    product_id: str | None = Field(default=None, validation_alias="productId")
    """The style."""
    part_id: str | None = Field(default=None, validation_alias="partId")
    """SanMar's unique key for the style, color and size."""
    charge_id: str | None = Field(default=None, validation_alias="chargeId")
    po_line_number: Decimal | None = Field(default=None, validation_alias="purchaseOrderLineItemNumber")
    ordered_quantity: Decimal | None = Field(default=None, validation_alias="orderedQuantity")
    back_ordered_quantity: Decimal | None = Field(default=None, validation_alias="backOrderedQuantity")
    discount_amount: Decimal | None = Field(default=None, validation_alias="discountAmount")
    distributor_product_id: str | None = Field(default=None, validation_alias="distributorProductId")
    distributor_part_id: str | None = Field(default=None, validation_alias="distributorPartId")


class Tax(Record):
    """A tax charged on an invoice."""

    tax_type: str = Field(validation_alias="taxType")
    jurisdiction: str = Field(validation_alias="taxJurisdiction")
    amount: Decimal = Field(validation_alias="taxAmount")


class Invoice(Record):
    """An invoice or credit memo."""

    invoice_number: str = Field(validation_alias="invoiceNumber")
    invoice_type: str = Field(validation_alias="invoiceType")
    """Whether this is an invoice or a credit memo, as SanMar spells it."""
    invoice_date: date = Field(validation_alias="invoiceDate")
    payment_due_date: date = Field(validation_alias="paymentDueDate")
    currency: str
    sales_amount: Decimal = Field(validation_alias="salesAmount")
    shipping_amount: Decimal = Field(validation_alias="shippingAmount")
    handling_amount: Decimal = Field(validation_alias="handlingAmount")
    tax_amount: Decimal = Field(validation_alias="taxAmount")
    invoice_amount: Decimal = Field(validation_alias="invoiceAmount")
    advance_payment_amount: Decimal = Field(validation_alias="advancePaymentAmount")
    amount_due: Decimal = Field(validation_alias="invoiceAmountDue")
    po_number: str | None = Field(default=None, validation_alias="purchaseOrderNumber")
    po_version: str | None = Field(default=None, validation_alias="purchaseOrderVersion")
    bill_to: AccountInfo | None = Field(default=None, validation_alias=AliasPath("BillTo", "AccountInfo"))
    sold_to: AccountInfo | None = Field(default=None, validation_alias=AliasPath("SoldTo", "AccountInfo"))
    comments: str | None = Field(default=None, validation_alias="invoiceComments")
    payment_terms: str | None = Field(default=None, validation_alias="paymentTerms")
    fob: str | None = None
    document_url: str | None = Field(default=None, validation_alias="invoiceDocumentUrl")
    payment_url: str | None = Field(default=None, validation_alias="invoicePaymentUrl")
    lines: list[InvoiceLine] = Field(
        default_factory=list,
        validation_alias=AliasPath("InvoiceLineItemsArray", "InvoiceLineItem"),
    )
    sales_order_numbers: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("SalesOrderNumbersArray", "salesOrderNumber"),
    )
    taxes: list[Tax] = Field(default_factory=list, validation_alias=AliasPath("TaxArray", "tax"))


class InvoiceService(PromoStandardsService):
    """SanMar's PromoStandards Invoice service."""

    endpoint = PROMOSTANDARDS_INVOICE
    version = "1.0.0"

    def by_purchase_order(self, po_number: str) -> list[Invoice]:
        """Find the invoices for a purchase order."""
        return self._query({"queryType": "1", "referenceNumber": po_number})

    def get(self, invoice_number: str) -> Invoice:
        """Find one invoice by its number.

        Raises
        ------
        ~sanmar_sdk.exceptions.NotFoundError
            If SanMar has no such invoice.
        """
        invoices = self._query({"queryType": "2", "referenceNumber": invoice_number})
        if not invoices:
            message = f"SanMar has no invoice {invoice_number}."
            raise NotFoundError(message)
        return invoices[0]

    def by_date(self, invoice_date: date) -> list[Invoice]:
        """Find every invoice dated a given day."""
        return self._query({"queryType": "3", "requestedDate": invoice_date})

    def available_since(self, since: datetime) -> list[Invoice]:
        """Find every invoice issued after a point in time."""
        return self._query({"queryType": "4", "availableTimeStamp": since})

    def _query(self, request: GetInvoicesRequest) -> list[Invoice]:
        result = self._call("getInvoices", request)
        if check(result, allow_empty=True):
            return []
        invoices = result.get("InvoiceArray") or {}
        return [Invoice.model_validate(invoice) for invoice in invoices.get("Invoice") or []]
