# idi-sanmar-sdk

A typed Python SDK for [SanMar](https://www.sanmar.com): its own web services, its
PromoStandards web services, and the data and order files on its SFTP server.

- **Strict in, typed out.** Orders and lookups are validated Pydantic models, so a bad
  address or a comma in a PO number fails before anything is sent. Responses come back as
  typed records, with prices as `Decimal`.
- **No SOAP or file layouts to learn.** Each call is shaped into SanMar's payload in one
  place, including the PromoStandards fields SanMar requires and then ignores.
- **Streams.** SFTP files are parsed row by row as they download, zip archives included.

Documentation: https://impressdesigns.dev/sanmar-sdk/

## Install

```sh
uv add idi-sanmar-sdk
```

Python 3.14 or newer. SanMar's web services listen on port 8080, and its SFTP server on
port 2200; some networks block both.

## Quick start

```python
from sanmar_sdk import SanMar, ShipMethod, ShipTo
from sanmar_sdk.promostandards import PromoStandardsOrder, PromoStandardsOrderLine

sanmar = SanMar(123456, "sanmar-username", "sanmar-password")

# Look a style up, and check stock for one of its parts.
product = sanmar.promostandards.product_data.get("K500")
[stock] = sanmar.promostandards.inventory.get("K500", part_ids=["208284"])

# Place an order.
order = PromoStandardsOrder(
    po_number="85496",
    ship_to=ShipTo(address1="1404 W MAIN ST", city="CARROLLTON", state="TX", zip_code="75006"),
    ship_method=ShipMethod.UPS_GROUND,
    lines=[PromoStandardsOrderLine(part_id="208284", quantity=12)],
)
transaction_id = sanmar.promostandards.purchase_orders.send(order)
```

Reading the catalog over SFTP:

```python
from sanmar_sdk.ftp import SanMarFTP

with SanMarFTP(123456, "ftp-password", host_key="ssh-rsa AAAA...") as ftp, ftp.catalog() as products:
    for product in products:
        print(product.style, product.catalog_color, product.size, product.unique_key)
```

Colors in requests and orders are SanMar's **catalog** colors (`SANMAR_MAINFRAME_COLOR`),
not the display names in `COLOR_NAME`. The SDK calls them `catalog_color` everywhere; see
[Identifiers](https://impressdesigns.dev/sanmar-sdk/identifiers/).

## Sources

Written against these revisions of SanMar's integration guides:

| Guide | Version | Updated |
|---|---|---|
| [SanMar Web Services Integration Guide](https://www.sanmar.com/medias/sys_master/pdf/h7a/ha0/33815499964446/SanMar-Web-Services-Integration-Guide-24.6/SanMar-Web-Services-Integration-Guide-24.6.pdf) | 24.6 | August 2026 |
| [SanMar Purchase Order Integration Guide](https://www.sanmar.com/medias/sys_master/root/h4b/ha7/33815499767838/SanMar-Purchase-Order-Integration-Guide-24.5/SanMar-Purchase-Order-Integration-Guide-24.5.pdf) | 24.5 | August 2026 |
| [SanMar FTP Integration Guide](https://www.sanmar.com/medias/sys_master/root/h08/hae/33815499571230/SanMar-FTP-Integration-Guide-v23.6/SanMar-FTP-Integration-Guide-v23.6.pdf) | 23.6 | August 2026 |

Where the guides contradict themselves, the SDK follows SanMar's own WSDLs and file
headers, recorded in `tests/`. The
[Sources](https://impressdesigns.dev/sanmar-sdk/sources/) page lists each case.

## Development

```sh
uv sync --all-groups
uv run nox -s lints tests
```

The live suite calls SanMar's real services, read-only:

```sh
SANMAR_LIVE=1 SANMAR_CUSTOMER_NUMBER=... SANMAR_USERNAME=... SANMAR_PASSWORD=... \
  uv run pytest tests/live
```
