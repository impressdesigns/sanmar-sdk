"""SanMar's own invoicing service.

SanMar invoices once a day, after 9 PM Pacific, for everything shipped that day, and
suggests waiting a further day before reading invoices. Every lookup comes in two forms:
whole invoices, with their lines, and headers only.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic import AliasPath, Field

from sanmar_sdk._soap import INVOICING, Service
from sanmar_sdk.base import OneOrMany, Record, SanMarDate
from sanmar_sdk.exceptions import NotFoundError, SoapFaultError

from ._common import raise_fault

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ._wire import (
        InvoiceByNumberRequest,
        InvoiceLogin,
        InvoicesByDateRangeRequest,
        InvoicesByOrderDateRequest,
        InvoicesByPurchaseOrderRequest,
    )

INVOICE_RANGE_LIMIT = timedelta(days=92)
"""SanMar returns whole invoices for up to three months of invoice dates at a time."""
HEADER_RANGE_LIMIT = timedelta(days=366)
"""SanMar returns invoice headers for up to a year of invoice dates at a time."""


class Address(Record):
    """A postal address on an invoice."""

    address1: str | None = Field(default=None, validation_alias="Address1")
    address2: str | None = Field(default=None, validation_alias="Address2")
    address3: str | None = Field(default=None, validation_alias="Address3")
    city: str | None = Field(default=None, validation_alias="City")
    state: str | None = Field(default=None, validation_alias="State")
    postal_code: str | None = Field(default=None, validation_alias="PostalCode")
    country: str | None = Field(default=None, validation_alias="Country")


class Party(Record):
    """Who an invoice is sold to, shipped to, or paid to."""

    name: str | None = Field(default=None, validation_alias="Name")
    address: Address = Field(default_factory=Address, validation_alias="Address")


class InvoiceHeader(Record):
    """The header of one SanMar invoice."""

    invoice_number: int = Field(validation_alias="InvoiceNo")
    invoice_date: SanMarDate = Field(validation_alias="InvoiceDate")
    sales_order_number: int | None = Field(default=None, validation_alias="SalesOrderNumber")
    status: str | None = Field(default=None, validation_alias="InvoiceStatus")
    """``Paid`` or ``Unpaid``."""
    is_credit_memo: bool = Field(default=False, validation_alias="IsCreditMemo")
    customer_number: int | None = Field(default=None, validation_alias="CustomerNo")
    po_number: str | None = Field(default=None, validation_alias="PurchaseOrderNo")
    order_date: SanMarDate | None = Field(default=None, validation_alias="OrderDate")
    due_date: SanMarDate | None = Field(default=None, validation_alias="DueDate")
    sold_to: Party | None = Field(default=None, validation_alias="SoldTo")
    ship_to: Party | None = Field(default=None, validation_alias="ShipTo")
    remit_to: Party | None = Field(default=None, validation_alias="RemitTo")
    ship_via: str | None = Field(default=None, validation_alias="ShipVia")
    fob: str | None = Field(default=None, validation_alias="FOB")
    """The shipping point, such as ``SPARKS NV``."""
    terms: str | None = Field(default=None, validation_alias="Terms")
    department: str | None = Field(default=None, validation_alias="DeptNo")
    total_cases: int | None = Field(default=None, validation_alias="TotalCases")
    total_weight: int | None = Field(default=None, validation_alias="TotalWeight")
    subtotal: Decimal | None = Field(default=None, validation_alias="SubTotal")
    sales_tax: Decimal | None = Field(default=None, validation_alias="SalesTax")
    shipping_and_handling: Decimal | None = Field(default=None, validation_alias="ShippingHandlingCharges")
    total: Decimal | None = Field(default=None, validation_alias="TotalAmount")
    freight_savings: Decimal | None = Field(default=None, validation_alias=AliasPath("Miscellaneous", "FreightSavings"))


class InvoiceLine(Record):
    """One line of a SanMar invoice."""

    style: str | None = Field(default=None, validation_alias="StyleNo")
    catalog_color: str | None = Field(default=None, validation_alias="StyleColor")
    """The color as SanMar's order system records it, which is the catalog (mainframe) color."""
    size: str | None = Field(default=None, validation_alias="StyleSize")
    description: str | None = Field(default=None, validation_alias="StyleDescription")
    quantity: int = Field(validation_alias="Quantity")
    unit_price: Decimal | None = Field(default=None, validation_alias="UnitPrice")
    amount: Decimal | None = Field(default=None, validation_alias="Amount")
    unique_key: str | None = Field(default=None, validation_alias="UniqueKey")


class Invoice(Record):
    """One SanMar invoice, with its lines."""

    header: InvoiceHeader = Field(validation_alias="Header")
    lines: OneOrMany[InvoiceLine] = Field(default_factory=list, validation_alias="LineItem")


def _check_range(start: date, end: date, limit: timedelta) -> None:
    if end < start:
        message = "The end date is before the start date."
        raise ValueError(message)
    if end - start > limit:
        message = f"SanMar returns at most {limit.days} days of invoices per call; split the range."
        raise ValueError(message)


class InvoiceService(Service):
    """SanMar's own invoicing service."""

    def _login(self) -> InvoiceLogin:
        return {
            "CustomerNo": str(self._credentials.customer_number),
            "UserName": self._credentials.username,
            "Password": self._credentials.password,
        }

    def _call(self, operation: str, request: Mapping[str, object]) -> Any:  # noqa: ANN401 - zeep's data
        """Call an invoicing operation; SanMar's "Data not found" fault means no invoices."""
        try:
            return self._soap.call(INVOICING, (operation,), request)
        except SoapFaultError as fault:
            if "data not found" in fault.message.casefold():
                return None
            raise_fault(fault)

    def _invoices(self, operation: str, request: Mapping[str, object]) -> list[Invoice]:
        return [Invoice.model_validate(invoice) for invoice in self._call(operation, request) or []]

    def _headers(self, operation: str, request: Mapping[str, object]) -> list[InvoiceHeader]:
        return [InvoiceHeader.model_validate(header) for header in self._call(operation, request) or []]

    def _by_purchase_order(self, po_number: str) -> InvoicesByPurchaseOrderRequest:
        return {**self._login(), "PurchaseOrderNo": po_number}

    def _by_invoice_date(self, start: date, end: date, limit: timedelta) -> InvoicesByDateRangeRequest:
        _check_range(start, end, limit)
        return {**self._login(), "StartDate": start, "EndDate": end}

    def _by_order_date(self, order_date: date) -> InvoicesByOrderDateRequest:
        return {**self._login(), "Date": order_date}

    def get(self, invoice_number: int) -> Invoice:
        """Fetch one invoice by its number.

        Raises
        ------
        ~sanmar_sdk.exceptions.NotFoundError
            If SanMar has no invoice with that number.
        """
        request: InvoiceByNumberRequest = {**self._login(), "InvoiceNo": invoice_number}
        result = self._call("GetInvoiceByInvoiceNo", request)
        if not result:
            message = f"SanMar has no invoice {invoice_number}."
            raise NotFoundError(message)
        return Invoice.model_validate(result)

    def by_purchase_order(self, po_number: str) -> list[Invoice]:
        """Fetch the invoices for one purchase order.

        SanMar matches at most the first 13 characters of a PO number here.
        """
        return self._invoices("GetInvoicesByPurchaseOrderNo", self._by_purchase_order(po_number))

    def by_invoice_date(self, start: date, end: date) -> list[Invoice]:
        """Fetch the invoices dated between two days, inclusive, up to three months apart."""
        return self._invoices("GetInvoicesByInvoiceDateRange", self._by_invoice_date(start, end, INVOICE_RANGE_LIMIT))

    def by_order_date(self, order_date: date) -> list[Invoice]:
        """Fetch the invoices for orders placed on one day."""
        return self._invoices("GetInvoicesByOrderDate", self._by_order_date(order_date))

    def unpaid(self) -> list[Invoice]:
        """Fetch every unpaid invoice."""
        return self._invoices("GetUnpaidInvoices", self._login())

    def since_last_call(self) -> list[Invoice]:
        """Fetch the invoices added since this was last called.

        The first call returns the last three months. Each call moves SanMar's marker, so
        the invoices it returns are not returned again.
        """
        return self._invoices("GetInvoices", self._login())

    def headers_by_purchase_order(self, po_number: str) -> list[InvoiceHeader]:
        """Fetch the invoice headers for one purchase order."""
        return self._headers("GetInvoicesHeaderByPurchaseOrderNo", self._by_purchase_order(po_number))

    def headers_by_invoice_date(self, start: date, end: date) -> list[InvoiceHeader]:
        """Fetch the invoice headers dated between two days, inclusive, up to a year apart."""
        return self._headers(
            "GetInvoicesHeaderByInvoiceDateRange",
            self._by_invoice_date(start, end, HEADER_RANGE_LIMIT),
        )

    def headers_by_order_date(self, order_date: date) -> list[InvoiceHeader]:
        """Fetch the invoice headers for orders placed on one day."""
        return self._headers("GetInvoicesHeaderByOrderDate", self._by_order_date(order_date))

    def unpaid_headers(self) -> list[InvoiceHeader]:
        """Fetch the headers of every unpaid invoice."""
        return self._headers("GetUnpaidInvoicesHeader", self._login())
