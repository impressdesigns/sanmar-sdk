"""Testing SanMar's PromoStandards Media Content and Inventory services against their recorded WSDLs."""

import pytest

from sanmar_sdk import AuthenticationError, Warehouse
from sanmar_sdk.promostandards import ClassType, MediaType

from .replay import PASSWORD, USERNAME, envelope, replay_client, sent

MEDIA = (
    'xmlns:ns2="http://www.promostandards.org/WSDL/MediaService/1.0.0/" '
    'xmlns="http://www.promostandards.org/WSDL/MediaService/1.0.0/SharedObjects/"'
)
INVENTORY = (
    'xmlns:ns2="http://www.promostandards.org/WSDL/Inventory/2.0.0/" '
    'xmlns="http://www.promostandards.org/WSDL/Inventory/2.0.0/SharedObjects/"'
)


def _location(warehouse: int, name: str, quantity: int) -> str:
    return f"""<InventoryLocation>
      <inventoryLocationId>{warehouse}</inventoryLocationId><inventoryLocationName>{name}</inventoryLocationName>
      <postalCode>98027</postalCode><country>US</country>
      <inventoryLocationQuantity><Quantity><uom>EA</uom><value>{quantity}</value></Quantity></inventoryLocationQuantity>
    </InventoryLocation>"""


# Shaped like the Web Services Integration Guide's sample response.
STOCK = envelope(
    f"""<ns2:GetInventoryLevelsResponse {INVENTORY}>
      <Inventory>
        <productId>k420</productId>
        <PartInventoryArray>
          <PartInventory>
            <partId>92032</partId><mainPart>false</mainPart><partColor>Black</partColor><labelSize>S</labelSize>
            <partDescription>Port Authority Heavyweight Cotton Pique Polo. K420</partDescription>
            <quantityAvailable><Quantity><uom>EA</uom><value>167</value></Quantity></quantityAvailable>
            <manufacturedItem>false</manufacturedItem><buyToOrder>false</buyToOrder>
            <InventoryLocationArray>
              {_location(1, "Seattle", 0)}
              {_location(2, "Cincinnati", 167)}
              <InventoryLocation>
                <inventoryLocationId>3</inventoryLocationId>
                <inventoryLocationQuantity><Quantity><uom>EA</uom><value>0</value></Quantity></inventoryLocationQuantity>
                <FutureAvailabilityArray>
                  <FutureAvailability>
                    <Quantity><uom>EA</uom><value>500</value></Quantity><availableOn>2026-10-15T00:00:00</availableOn>
                  </FutureAvailability>
                </FutureAvailabilityArray>
              </InventoryLocation>
            </InventoryLocationArray>
          </PartInventory>
        </PartInventoryArray>
      </Inventory>
    </ns2:GetInventoryLevelsResponse>""",
)


def test_media_for_a_style() -> None:
    """A style's images come back with their classes and colors."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:GetMediaContentResponse {MEDIA}>
              <ns2:MediaContentArray>
                <ns2:MediaContent>
                  <productId>K420</productId><partId>92032</partId>
                  <ns2:url>https://cdnm.sanmar.com/imglib/mresjpg/2014/f7/K420_Black_back_FS06.jpg</ns2:url>
                  <mediaType>Image</mediaType>
                  <ns2:ClassTypeArray>
                    <ns2:ClassType><ns2:classTypeId>1008</ns2:classTypeId><ns2:classTypeName>Rear</ns2:classTypeName></ns2:ClassType>
                  </ns2:ClassTypeArray>
                  <ns2:color>Black</ns2:color>
                  <ns2:singlePart>true</ns2:singlePart>
                </ns2:MediaContent>
              </ns2:MediaContentArray>
            </ns2:GetMediaContentResponse>""",
        ),
    )

    [image] = sanmar.promostandards.media_content.get("K420", class_type=ClassType.REAR)

    assert sent(transport) == (
        "GetMediaContentRequest",
        {
            "wsVersion": "1.1.0",
            "id": USERNAME,
            "password": PASSWORD,
            "mediaType": "Image",
            "productId": "K420",
            "classType": "1008",
        },
    )
    assert (image.part_id, image.color, image.single_part) == ("92032", "Black", True)
    assert [(media_class.id, media_class.name) for media_class in image.classes] == [(1008, "Rear")]
    assert image.url.endswith("K420_Black_back_FS06.jpg")


def test_media_documents_for_a_part() -> None:
    """Documents can be asked for one part at a time."""
    sanmar, transport = replay_client()
    transport.queue(envelope(f"<ns2:GetMediaContentResponse {MEDIA}/>"))

    assert sanmar.promostandards.media_content.get("K420", media_type=MediaType.DOCUMENT, part_id="92032") == []
    assert sent(transport)[1]["mediaType"] == "Document"
    assert sent(transport)[1]["partId"] == "92032"


def test_media_error_message_is_raised() -> None:
    """Media Content reports errors as a lower-case errorMessage."""
    sanmar, transport = replay_client()
    transport.queue(
        envelope(
            f"""<ns2:GetMediaContentResponse {MEDIA}>
              <errorMessage><code>105</code><description>Authentication Credentials failed</description></errorMessage>
            </ns2:GetMediaContentResponse>""",
        ),
    )

    with pytest.raises(AuthenticationError, match="105"):
        sanmar.promostandards.media_content.get("K420")


def test_stock_by_size_and_color() -> None:
    """Stock comes back per part and per warehouse, with what is on its way."""
    sanmar, transport = replay_client()
    transport.queue(STOCK)

    [part] = sanmar.promostandards.inventory.get("K420", sizes=["S"], catalog_colors=["Black"])

    assert sent(transport) == (
        "GetInventoryLevelsRequest",
        {
            "wsVersion": "2.0.0",
            "id": USERNAME,
            "password": PASSWORD,
            "productId": "K420",
            "Filter": {"LabelSizeArray": {"labelSize": "S"}, "PartColorArray": {"partColor": "Black"}},
        },
    )
    assert (part.part_id, part.catalog_color, part.size, part.quantity) == ("92032", "Black", "S", 167)
    assert [(location.warehouse, location.quantity) for location in part.locations] == [
        (Warehouse.SEATTLE, 0),
        (Warehouse.CINCINNATI, 167),
        (Warehouse.DALLAS, 0),
    ]
    [future] = part.locations[2].future
    assert (future.quantity, future.available_on.month) == (500, 10)


def test_stock_for_parts_across_styles() -> None:
    """Part ids from any styles go in one call."""
    sanmar, transport = replay_client()
    transport.queue(STOCK)

    sanmar.promostandards.inventory.get("C855", part_ids=["295993", "647554", "678183"])

    assert sent(transport)[1]["Filter"] == {"partIdArray": {"partId": ["295993", "647554", "678183"]}}


def test_unfiltered_stock_sends_no_filter() -> None:
    """A whole style is asked for without a filter."""
    sanmar, transport = replay_client()
    transport.queue(envelope(f"<ns2:GetInventoryLevelsResponse {INVENTORY}/>"))

    assert sanmar.promostandards.inventory.get("K420") == []
    assert "Filter" not in sent(transport)[1]


@pytest.mark.parametrize(
    ("arguments", "match"),
    [
        ({"part_ids": ["1"], "sizes": ["S"]}, "not both"),
        ({"part_ids": [str(number) for number in range(201)]}, "at most 200"),
    ],
)
def test_impossible_filters_fail_up_front(arguments: dict[str, list[str]], match: str) -> None:
    """Filters SanMar would refuse fail before anything is sent."""
    sanmar, transport = replay_client()

    with pytest.raises(ValueError, match=match):
        sanmar.promostandards.inventory.get("K420", **arguments)
    assert transport.sent == []


def test_a_single_string_filter_is_refused() -> None:
    """A filter given as one string would be sent a character at a time, so it is refused."""
    sanmar, _ = replay_client()

    with pytest.raises(TypeError, match="sizes takes a list"):
        sanmar.promostandards.inventory.get("K420", sizes="XL")
