"""SanMar's PromoStandards Order Status service, version 2.0.0.

Reports where orders stand, line by line, with any holds. SanMar asks that it be called no
more than three times a day, starting two hours after an order is placed, and that an order
not be checked again once it is :attr:`Status.COMPLETE` or :attr:`Status.CANCELED`. SanMar
does not implement ``getIssue`` or the ``transactionId`` query.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import AliasPath, BeforeValidator, Field

from sanmar_sdk._soap import PROMOSTANDARDS_ORDER_STATUS
from sanmar_sdk.base import Record

from ._common import PromoStandardsService, check

if TYPE_CHECKING:
    from ._wire import GetOrderStatusRequest

MAX_AGE = timedelta(days=30)


class Status(StrEnum):
    """Where an order or line stands."""

    RECEIVED = "received"
    """SanMar has the order, including when it is on hold or backordered."""
    CONFIRMED = "confirmed"
    PREPRODUCTION = "preproduction"
    IN_PRODUCTION = "inProduction"
    IN_STORAGE = "inStorage"
    PARTIALLY_SHIPPED = "partiallyShipped"
    SHIPPED = "shipped"
    COMPLETE = "complete"
    """Shipped in full and invoiced. SanMar reports nothing further."""
    CANCELED = "canceled"
    """SanMar reports nothing further."""


def _status(value: Any) -> Any:  # noqa: ANN401 - runs before validation
    """Match a status however SanMar capitalizes or spaces it."""
    if isinstance(value, str):
        folded = value.replace(" ", "").casefold()
        return next((status for status in Status if status.value.casefold() == folded), value)
    return value


type StatusValue = Annotated[Status | str, Field(union_mode="left_to_right"), BeforeValidator(_status)]
"""A :class:`Status`, or the text SanMar sent if it is none of them."""


class IssueDetail(StrEnum):
    """Which issues to include in an order status."""

    NONE = "noIssues"
    OPEN = "openIssues"
    """Issues that are open or pending."""
    ALL = "allIssues"


class ContactDetails(Record):
    """A contact's name and address."""

    attention_to: str | None = Field(default=None, validation_alias="attentionTo")
    company_name: str | None = Field(default=None, validation_alias="companyName")
    address1: str | None = None
    address2: str | None = None
    address3: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = Field(default=None, validation_alias="postalCode")
    country: str | None = None
    email: str | None = None
    phone: str | None = None
    comments: str | None = None


class Contact(Record):
    """Someone at SanMar to ask about an order, such as its account executive."""

    contact_type: str = Field(validation_alias="contactType")
    details: ContactDetails = Field(default_factory=ContactDetails, validation_alias="ContactDetails")
    account_name: str | None = Field(default=None, validation_alias="accountName")
    account_number: str | None = Field(default=None, validation_alias="accountNumber")


class StatusLine(Record):
    """Where one line of a sales order stands."""

    product_id: str = Field(validation_alias="productId")
    """The style."""
    sales_order_line_number: str = Field(validation_alias="salesOrderLineNumber")
    status: StatusValue
    part_id: str | None = Field(default=None, validation_alias="partId")
    """SanMar's unique key for the style, color and size."""
    po_line_number: str | None = Field(default=None, validation_alias="purchaseOrderLineNumber")
    quantity_ordered: Decimal = Field(validation_alias=AliasPath("QuantityOrdered", "value"))
    quantity_shipped: Decimal = Field(default=Decimal(0), validation_alias=AliasPath("QuantityShipped", "value"))
    issue_category: str | None = Field(default=None, validation_alias="issueCategory")


class Issue(Record):
    """A hold on an order, such as ``generalHold`` or ``backOrderHold``."""

    status: str = Field(validation_alias="issueStatus")
    """``Open``, ``Pending`` or ``Closed``."""
    category: str = Field(validation_alias="issueCategory")
    urgent_response_required: bool = Field(default=False, validation_alias="urgentResponseRequired")
    id: str | None = Field(default=None, validation_alias="issueId")
    name: str | None = Field(default=None, validation_alias="issueName")
    description: str | None = Field(default=None, validation_alias="issueDescription")
    response_required_by: datetime | None = Field(default=None, validation_alias="responseRequiredBy")
    resolution_url: str | None = Field(default=None, validation_alias="issueResolutionURL")
    product_id: str | None = Field(default=None, validation_alias="productId")
    part_id: str | None = Field(default=None, validation_alias="partId")


class SalesOrderStatus(Record):
    """Where one of SanMar's sales orders stands."""

    sales_order_number: str = Field(validation_alias="salesOrderNumber")
    status: StatusValue
    valid_timestamp: datetime = Field(validation_alias="validTimestamp")
    """When SanMar last confirmed this status."""
    issue_category: str | None = Field(default=None, validation_alias="issueCategory")
    """``generalHold`` when the order is on hold, ``backOrderHold`` when it is backordered."""
    expected_ship_date: date | None = Field(default=None, validation_alias="expectedShipDate")
    expected_delivery_date: date | None = Field(default=None, validation_alias="expectedDeliveryDate")
    additional_explanation: str | None = Field(default=None, validation_alias="additionalExplanation")
    contacts: list[Contact] = Field(default_factory=list, validation_alias=AliasPath("OrderContactArray", "Contact"))
    lines: list[StatusLine] = Field(default_factory=list, validation_alias=AliasPath("ProductArray", "Product"))
    """The lines, when they were asked for."""
    issues: list[Issue] = Field(default_factory=list, validation_alias=AliasPath("IssueArray", "Issue"))


class OrderStatus(Record):
    """Where one purchase order stands, sales order by sales order."""

    po_number: str = Field(validation_alias="purchaseOrderNumber")
    sales_orders: list[SalesOrderStatus] = Field(
        default_factory=list,
        validation_alias=AliasPath("OrderStatusDetailArray", "OrderStatusDetail"),
    )
    audit_url: str | None = Field(default=None, validation_alias="auditURL")

    @property
    def finished(self) -> bool:
        """Whether every sales order is complete or canceled, so SanMar will report nothing more."""
        return bool(self.sales_orders) and all(
            order.status in {Status.COMPLETE, Status.CANCELED} for order in self.sales_orders
        )


class OrderStatusService(PromoStandardsService):
    """SanMar's PromoStandards Order Status service."""

    endpoint = PROMOSTANDARDS_ORDER_STATUS
    version = "2.0.0"

    def by_purchase_order(
        self,
        po_number: str,
        *,
        issues: IssueDetail = IssueDetail.OPEN,
        lines: bool = True,
    ) -> list[OrderStatus]:
        """Report where a purchase order stands.

        ``issues`` picks which holds to include, and ``lines`` whether to include each line.
        """
        return self._query("poSearch", issues, lines, reference=po_number)

    def by_sales_order(
        self,
        sales_order_number: str,
        *,
        issues: IssueDetail = IssueDetail.OPEN,
        lines: bool = True,
    ) -> list[OrderStatus]:
        """Report where one of SanMar's sales orders stands."""
        return self._query("soSearch", issues, lines, reference=sales_order_number)

    def updated_since(
        self,
        since: datetime,
        *,
        issues: IssueDetail = IssueDetail.OPEN,
        lines: bool = True,
    ) -> list[OrderStatus]:
        """Report every order whose status changed after a point in time, at most 30 days ago.

        SanMar suggests narrowing to seven days if the call times out.

        Raises
        ------
        ValueError
            If ``since`` has no time zone, or is more than 30 days ago.
        """
        if since.tzinfo is None:
            message = "Give the time with a time zone; SanMar reads it as UTC."
            raise ValueError(message)
        if datetime.now(tz=UTC) - since > MAX_AGE:
            message = "SanMar reports status changes from at most 30 days back."
            raise ValueError(message)
        return self._query("lastUpdate", issues, lines, since=since.astimezone(UTC))

    def open_orders(self, *, issues: IssueDetail = IssueDetail.OPEN, lines: bool = True) -> list[OrderStatus]:
        """Report every order that is not yet complete or canceled."""
        return self._query("allOpen", issues, lines)

    def open_issues(self, *, issues: IssueDetail = IssueDetail.OPEN, lines: bool = True) -> list[OrderStatus]:
        """Report every open order with an open or pending issue."""
        return self._query("allOpenIssues", issues, lines)

    def service_methods(self) -> list[str]:
        """List the Order Status operations SanMar implements."""
        result = self._call("getServiceMethods", {})
        if check(result, allow_empty=True):
            return []
        methods = result.get("ServiceMethodArray") or {}
        return [str(method) for method in methods.get("serviceMethod") or []]

    def _query(
        self,
        query_type: str,
        issues: IssueDetail,
        lines: bool,  # noqa: FBT001 - private, and always passed through by keyword above
        *,
        reference: str | None = None,
        since: datetime | None = None,
    ) -> list[OrderStatus]:
        request: GetOrderStatusRequest = {
            "queryType": query_type,
            "returnIssueDetailType": IssueDetail(issues).value,
            "returnProductDetail": lines,
        }
        if reference is not None:
            request["referenceNumber"] = reference
        if since is not None:
            request["statusTimeStamp"] = since
        result = self._call("getOrderStatus", request)
        if check(result, allow_empty=True):
            return []
        statuses = result.get("OrderStatusArray") or {}
        return [OrderStatus.model_validate(status) for status in statuses.get("OrderStatus") or []]
