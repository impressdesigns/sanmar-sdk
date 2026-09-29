"""Testing SanMar's packing slip service against its recorded WSDL."""

from datetime import date

import pytest

from sanmar_sdk import NotFoundError

from .replay import PASSWORD, USERNAME, envelope, fault, replay_client, sent

ADDRESS = """<Address><Line1>1404 W Main St</Line1><CityName>Carrollton</CityName><StateCode>TX</StateCode>
  <PostalCode>75006</PostalCode><CountryCode>US</CountryCode><IsResidential>false</IsResidential></Address>"""

PACKING_SLIP = envelope(
    f"""<GetPackingSlipResponse xmlns="http://ws.sanmar.com/webservices/PackingSlip">
      <PackingSlip id="LP000123456789">
        <Header>
          <ShipmentDate>2026-06-17</ShipmentDate><ShipmentUnitIndex>1</ShipmentUnitIndex>
          <ShipmentUnitQuantity>2</ShipmentUnitQuantity><OrderDate>2026-06-16</OrderDate>
          <OrderNumber>71490386</OrderNumber><InvoiceNumber>58316700</InvoiceNumber>
          <PurchaseOrderReference>85496</PurchaseOrderReference>
          <ShipFrom><Name>SanMar</Name>{ADDRESS}</ShipFrom>
          <ShipTo><Name>Impress Designs</Name>{ADDRESS}</ShipTo>
          <Weight uom="lb">12.5</Weight>
          <Carrier><Name>UPS</Name><ShippingMethod>GROUND</ShippingMethod><TrackingId>1Z999</TrackingId></Carrier>
        </Header>
        <Body>
          <Item id="1"><SkuId>175762</SkuId><StyleNo>PC61</StyleNo><Description>Essential Tee</Description>
            <Color>Aquatic Blue</Color><Size>S</Size><Quantity>12</Quantity><GTIN>00191265001373</GTIN></Item>
          <Item id="2"><SkuId>175763</SkuId><StyleNo>PC61</StyleNo><Description>Essential Tee</Description>
            <Color>Aquatic Blue</Color><Size>M</Size>
            <Quantity>24</Quantity></Item>
        </Body>
      </PackingSlip>
    </GetPackingSlipResponse>""",
)


def test_packing_slip() -> None:
    """A box's order, carrier and contents come back typed."""
    sanmar, transport = replay_client()
    transport.queue(PACKING_SLIP)

    slip = sanmar.packing_slips.get("LP000123456789")

    assert sent(transport) == (
        "GetPackingSlip",
        {"wsVersion": "1.0.0", "UserId": USERNAME, "Password": PASSWORD, "PackingSlipId": "LP000123456789"},
    )
    assert (slip.license_plate, slip.box_number, slip.box_count, slip.order_number, slip.po_number) == (
        "LP000123456789",
        1,
        2,
        71490386,
        "85496",
    )
    assert (slip.ship_date, slip.weight, slip.weight_unit, slip.carrier, slip.tracking_number) == (
        date(2026, 6, 17),
        12.5,
        "lb",
        "UPS",
        "1Z999",
    )
    assert slip.ship_to is not None
    assert (slip.ship_to.name, slip.ship_to.address.city, slip.ship_to.address.residential) == (
        "Impress Designs",
        "Carrollton",
        False,
    )
    assert [(item.unique_key, item.catalog_color, item.size, item.quantity) for item in slip.items] == [
        ("175762", "Aquatic Blue", "S", 12),
        ("175763", "Aquatic Blue", "M", 24),
    ]


def test_license_plates_are_checked_up_front() -> None:
    """Something that is not a license plate number never reaches SanMar."""
    sanmar, transport = replay_client()
    with pytest.raises(ValueError, match="start with LP, L, S or R"):
        sanmar.packing_slips.get("1Z999")
    assert transport.sent == []


def test_unknown_box_is_not_found() -> None:
    """SanMar's "Data Not Found" fault is a NotFoundError."""
    sanmar, transport = replay_client()
    transport.queue(fault("Data Not Found"), status=500)

    with pytest.raises(NotFoundError, match="Data Not Found"):
        sanmar.packing_slips.get("LP000123456789")
