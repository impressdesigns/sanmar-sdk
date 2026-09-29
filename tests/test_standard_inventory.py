"""Testing SanMar's own inventory service against its recorded WSDL."""

import pytest

from sanmar_sdk import NotFoundError, SoapFaultError, Warehouse

from .replay import CUSTOMER_NUMBER, PASSWORD, USERNAME, envelope, fault, replay_client, sent

LOGIN = {"arg0": str(CUSTOMER_NUMBER), "arg1": USERNAME, "arg2": PASSWORD}


def _inventory(skus: str) -> str:
    return envelope(
        f"""<ns2:getInventoryQtyForStyleColorSizeResponse xmlns:ns2="http://webservice.integration.sanmar.com/">
          <return>
            <errorOccurred>false</errorOccurred>
            <message>Inventory returned successfully</message>
            <response xsi:type="ns2:Inventory"><style>L223</style><skus>{skus}</skus></response>
          </return>
        </ns2:getInventoryQtyForStyleColorSizeResponse>""",
    )


TWO_SIZES = _inventory(
    """<sku><color>Amethyst Purpl</color><size>XS</size>
         <whse><whseID>1</whseID><whseName>Seattle</whseName><qty>17</qty></whse>
         <whse><whseID>31</whseID><whseName>Richmond</whseName><qty>3000</qty></whse></sku>
       <sku><color>Amethyst Purpl</color><size>S</size>
         <whse><whseID>1</whseID><whseName>Seattle</whseName><qty>5</qty></whse></sku>""",
)


def test_color_and_size_lookup_asks_by_color_and_keeps_the_size() -> None:
    """Given a color and a size, only the color is sent, and the size is picked out locally."""
    sanmar, transport = replay_client()
    transport.queue(TWO_SIZES)

    [stock] = sanmar.inventory.get("L223", catalog_color="Amethyst Purpl", size="xs")

    assert sent(transport) == ("getInventoryQtyForStyleColorSize", {**LOGIN, "arg3": "L223", "arg4": "Amethyst Purpl"})
    assert (stock.style, stock.catalog_color, stock.size, stock.total) == ("L223", "Amethyst Purpl", "XS", 3017)
    assert [(entry.warehouse, entry.name, entry.quantity) for entry in stock.warehouses] == [
        (Warehouse.SEATTLE, "Seattle", 17),
        (Warehouse.RICHMOND, "Richmond", 3000),
    ]


def test_size_lookup_asks_by_size() -> None:
    """Given only a size, the size is sent, and every color comes back."""
    sanmar, transport = replay_client()
    transport.queue(TWO_SIZES)

    stock = sanmar.inventory.get("L223", size="S")

    assert sent(transport)[1] == {**LOGIN, "arg3": "L223", "arg5": "S"}
    assert [entry.size for entry in stock] == ["S"]


def test_single_sku_and_warehouse_are_lists() -> None:
    """One size at one warehouse still comes back as lists."""
    sanmar, transport = replay_client()
    transport.queue(
        _inventory("<sku><color>Black</color><size>L</size><whse><whseID>4</whseID><qty>9</qty></whse></sku>")
    )

    [stock] = sanmar.inventory.get("K500")

    assert [(entry.warehouse, entry.quantity) for entry in stock.warehouses] == [(Warehouse.RENO, 9)]


def test_unknown_style_is_not_found() -> None:
    """An unmatched style, color or size is a NotFoundError, with a reminder about colors."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            """<ns2:getInventoryQtyForStyleColorSizeResponse xmlns:ns2="http://webservice.integration.sanmar.com/">
              <return>
                <errorOccurred>true</errorOccurred><message>Invalid Style + Color + Size specified.</message>
              </return>
            </ns2:getInventoryQtyForStyleColorSizeResponse>""",
        ),
    )

    with pytest.raises(NotFoundError, match="catalog"):
        sanmar.inventory.get("K500", catalog_color="Jet Black")


def test_fault_on_the_unparsed_path_is_raised() -> None:
    """A SOAP fault is still a SoapFaultError, though the response is read without the WSDL."""
    sanmar, transport = replay_client()
    transport.queue(fault("Internal error"), status=500)

    with pytest.raises(SoapFaultError, match="Internal error"):
        sanmar.inventory.get("K500")


def test_quantity_at_one_warehouse() -> None:
    """The by-warehouse lookup sends the warehouse number and returns one quantity."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            """<ns2:getInventoryQtyForStyleColorSizeByWhseResponse xmlns:ns2="http://webservice.integration.sanmar.com/">
              <return><errorOccurred>false</errorOccurred><message>Inventory returned successfully</message>
              <response xsi:type="xs:int">1500</response></return>
            </ns2:getInventoryQtyForStyleColorSizeByWhseResponse>""",
        ),
    )

    assert sanmar.inventory.get_quantity("K500", "Black", "XL", Warehouse.DALLAS) == 1500  # noqa: PLR2004
    assert sent(transport) == (
        "getInventoryQtyForStyleColorSizeByWhse",
        {**LOGIN, "arg3": "K500", "arg4": "Black", "arg5": "XL", "arg6": "3"},
    )
