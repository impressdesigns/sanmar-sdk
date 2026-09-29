"""Testing SanMar's own pricing service against its recorded WSDL."""

from datetime import date
from decimal import Decimal

import pytest

from sanmar_sdk import NotFoundError, SkuKey, StyleQuery

from .replay import CUSTOMER_NUMBER, PASSWORD, USERNAME, envelope, replay_client, sent

LOGIN = {"sanMarCustomerNumber": str(CUSTOMER_NUMBER), "sanMarUserName": USERNAME, "sanMarUserPassword": PASSWORD}

PRICES = envelope(
    """<ns2:getPricingResponse xmlns:ns2="http://impl.webservice.integration.sanmar.com/">
      <return>
        <errorOccurred>false</errorOccurred>
        <listResponse xsi:type="ns2:item">
          <casePrice>2.59</casePrice><color>Lime</color><dozenPrice>3.59</dozenPrice><inventoryKey>46389</inventoryKey>
          <myPrice>1.76</myPrice><piecePrice>3.59</piecePrice><salePrice>1.99</salePrice><size>M</size>
          <sizeIndex>3</sizeIndex><style>LPC61</style><saleStartDate>2017-06-26</saleStartDate>
          <saleEndDate>2017-07-02</saleEndDate><incentivePrice>1.76</incentivePrice>
        </listResponse>
        <message>Pricing returned successfully</message>
      </return>
    </ns2:getPricingResponse>""",
)


def test_price_by_style_color_and_size() -> None:
    """A lookup by style sends the catalog color and size, and returns the account's price."""
    sanmar, transport = replay_client()
    transport.queue(PRICES)

    [quote] = sanmar.pricing.get("LPC61", catalog_color="Lime", size="M")

    assert sent(transport) == ("getPricing", {"arg0": {"color": "Lime", "size": "M", "style": "LPC61"}, "arg1": LOGIN})
    assert quote.model_dump(
        include={"inventory_key", "size_index", "case_price", "my_price", "sale_price", "sale_end_date"},
    ) == {
        "inventory_key": 46389,
        "size_index": 3,
        "case_price": Decimal("2.59"),
        "my_price": Decimal("1.76"),
        "sale_price": Decimal("1.99"),
        "sale_end_date": date(2017, 7, 2),
    }


def test_price_by_key_and_in_batches() -> None:
    """Lookups by key and by style can share one call."""
    sanmar, transport = replay_client()
    transport.queue(PRICES)

    sanmar.pricing.get_many([SkuKey(inventory_key=46389, size_index=3), StyleQuery(style="K500")])

    assert sent(transport)[1]["arg0"] == [{"inventoryKey": "46389", "sizeIndex": "3"}, {"style": "K500"}]


def test_price_by_key_alone() -> None:
    """The single-key shortcut sends just the key."""
    sanmar, transport = replay_client()
    transport.queue(PRICES)

    sanmar.pricing.get_by_key(SkuKey(inventory_key=46389, size_index=3))

    assert sent(transport)[1]["arg0"] == {"inventoryKey": "46389", "sizeIndex": "3"}


def test_unknown_color_is_not_found() -> None:
    """An unmatched color raises, with the reminder about catalog colors."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            """<ns2:getPricingResponse xmlns:ns2="http://impl.webservice.integration.sanmar.com/">
              <return>
                <errorOccurred>true</errorOccurred><message>Invalid Style + Color + Size specified.</message>
              </return>
            </ns2:getPricingResponse>""",
        ),
    )

    with pytest.raises(NotFoundError, match="catalog"):
        sanmar.pricing.get("LPC61", catalog_color="Lime Shock")
