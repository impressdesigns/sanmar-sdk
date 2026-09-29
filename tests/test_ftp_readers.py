"""Testing the streaming readers for SanMar's data files."""

import csv
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import GeneratorType
from typing import TYPE_CHECKING

import pytest

from sanmar_sdk import FileFormatError, Warehouse
from sanmar_sdk.ftp import (
    catalog,
    inventory,
    legacy,
    read_active_products,
    read_catalog,
    read_catalog_txt,
    read_customer_prices,
    read_extended_catalog,
    read_holding,
    read_pdd,
    read_price_changes,
    read_product_information,
    read_sale_items,
    read_shipment_status,
    read_warehouse_inventory,
)
from sanmar_sdk.ftp.readers import normalize_column

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

FILES = Path(__file__).parent / "fixtures" / "files"


@pytest.mark.parametrize(
    ("name", "normalized"),
    [
        ("STYLE#", "style#"),
        ("BACK_MODEL _IMAGE_URL", "back_model_image_url"),
        ("CATALOG.COLOR", "catalog_color"),
        ("Whse_ No", "whse_no"),
        ("Invoice.Attention", "invoice_attention"),
        (" SIZE ID ", "size_id"),
    ],
)
def test_column_names_are_normalized(name: str, normalized: str) -> None:
    """SanMar's spelling drift between files and guides matches the same column."""
    assert normalize_column(name) == normalized


def test_readers_are_lazy() -> None:
    """Nothing is read until rows are asked for, and then one at a time."""
    rows = read_catalog(FILES / "SanMar_SDL_N.csv")
    assert isinstance(rows, GeneratorType)
    assert next(rows).unique_key == "208284"


def test_catalog_separates_catalog_color_from_color_name() -> None:
    """The ordering color and the display color land in different, clearly named fields."""
    products = list(read_catalog(FILES / "SanMar_SDL_N.csv"))

    assert [(product.catalog_color, product.color_name) for product in products] == [
        ("Black", "Black"),
        ("Athletic Hthr", "Athletic Heather"),
    ]


def test_catalog_row_is_typed() -> None:
    """Keys are numbers, money is Decimal, GTINs keep their leading zeros, NA prices are None."""
    product = next(read_catalog(FILES / "SanMar_SDL_N.csv"))

    assert product.model_dump(
        include={
            "unique_key",
            "style",
            "size",
            "inventory_key",
            "size_index",
            "piece_price",
            "case_price",
            "case_size",
            "map_price",
            "gtin",
            "brand",
            "status",
            "quantity",
            "back_model_image_url",
        },
    ) == {
        "unique_key": "208284",
        "style": "K500",
        "size": "L",
        "inventory_key": 20828,
        "size_index": 4,
        "piece_price": Decimal("12.98"),
        "case_price": Decimal("10.98"),
        "case_size": 36,
        "map_price": None,
        "gtin": "00191265001373",
        "brand": "Port Authority",
        "status": "Regular",
        "quantity": None,
        "back_model_image_url": "https://cdnm.sanmar.com/imglib/mresjpg/K500_back.jpg",
    }


def test_extended_catalog_has_stock() -> None:
    """EPDD adds the stock across all warehouses."""
    assert [product.quantity for product in read_extended_catalog(FILES / "SanMar_EPDD.csv")] == [4500, 0]


def test_readers_take_open_streams() -> None:
    """A stream that is already open reads the same as a path."""
    with (FILES / "SanMar_SDL_N.csv").open(encoding="utf-8-sig", newline="") as stream:
        assert [product.style for product in read_catalog(stream)] == ["K500", "PC54"]


def test_missing_required_column_is_reported() -> None:
    """A header without a required column fails on line 1, naming the column."""
    stream = io.StringIO(
        '"UNIQUE_KEY","STYLE#","SIZE","INVENTORY_KEY","SIZE_INDEX","COLOR_NAME"\n"1","K500","L","2","3","Black"\n'
    )
    with pytest.raises(
        FileFormatError, match=r"line 1: the header has no sanmar_mainframe_color or catalog_color"
    ) as caught:
        list(read_catalog(stream))
    assert caught.value.line_number == 1


def test_bad_value_is_reported_with_its_line() -> None:
    """A row that does not validate fails with its line number."""
    stream = io.StringIO(
        '"UNIQUE_KEY","STYLE#","SIZE","INVENTORY_KEY","SIZE_INDEX","SANMAR_MAINFRAME_COLOR"\n'
        '"1","K500","L","2","3","Black"\n'
        "\n"
        '"2","K500","XL","two","5","Black"\n',
    )
    rows = read_catalog(stream)
    assert next(rows).unique_key == "1"
    with pytest.raises(FileFormatError, match=r"(?s)line 4: .*inventory_key"):
        next(rows)


def test_warehouse_inventory() -> None:
    """The dip file's quoted, pipe-delimited rows parse, sale datetimes included."""
    rows = list(read_warehouse_inventory(FILES / "sanmar_dip.txt"))

    assert [(row.unique_key, row.warehouse, row.quantity) for row in rows] == [
        ("208284", Warehouse.SEATTLE, 1500),
        ("208284", Warehouse.RICHMOND, 22),
        ("105661", 99, 0),
    ]
    first = rows[0]
    assert (first.piece_sale_price, first.sale_start_date, first.sale_end_date) == (
        Decimal("9.98"),
        date(2026, 10, 14),
        date(2026, 10, 20),
    )
    assert [row.discontinued for row in rows] == [False, False, True]


def test_header_row_decides_the_column_order() -> None:
    """A header row, in any order, is followed instead of the known layout."""
    stream = io.StringIO(
        "Whse_ No|Catalog_No|Catalog_Color|Size|Quantity|Inventory_Key|Size_Index\n3|K500|Black|L|7|20828|4\n"
    )
    row = next(read_warehouse_inventory(stream))
    assert (row.warehouse, row.style, row.quantity, row.unique_key) == (Warehouse.DALLAS, "K500", 7, None)


def test_file_without_a_header_is_read_by_the_known_layout() -> None:
    """Without a header, rows are read in the known column order, and must fit it exactly."""
    row = "20828|4|K500|Black|L|4|9|0.6094|12.98|12.98|10.98|36||||||208284|"
    assert next(read_warehouse_inventory(io.StringIO(row + "\n"))).warehouse == Warehouse.RENO
    with pytest.raises(FileFormatError, match=r"line 1: expected 19 fields.* found 3"):
        list(read_warehouse_inventory(io.StringIO("20828|4|K500\n")))


def test_active_products() -> None:
    """The older per-warehouse export ends with the unique key, whatever the guide says."""
    row = next(read_active_products(FILES / "sanmar_activeproductsexport.txt"))
    assert (row.inventory_key, row.warehouse, row.quantity, row.unique_key) == (20828, Warehouse.DALLAS, 500, "208284")


def test_customer_prices() -> None:
    """The account's own price is read alongside the list prices."""
    price = next(read_customer_prices(FILES / "sanmar_dp.csv"))
    assert (price.unique_key, price.catalog_color, price.case_price, price.my_price) == (
        "208284",
        "Black",
        Decimal("10.98"),
        Decimal("9.87"),
    )


def test_price_changes() -> None:
    """The delta file has only the key and the price, which may be unavailable."""
    changes = list(read_price_changes(FILES / "sanmar_dpc.csv"))
    assert [(change.unique_key, change.my_price) for change in changes] == [
        ("208284", Decimal("9.87")),
        ("105661", None),
    ]


def test_product_information() -> None:
    """SanMarPI files split keywords and parse sale dates."""
    stream = io.StringIO(
        "UNIQUE_KEY,STYLE#,SIZE,INVENTORY_KEY,SIZE_INDEX,CATALOG_COLOR,COLOR_NAME,BRAND_NAME,KEYWORDS,"
        "PIECE_SALE_PRICE,SALE_START_DATE,SALE_END_DATE,CATEGORY,MAP_PRICE\n"
        '118032,PC61,S,11803,2,White,White,Port & Company,"tee, tees, t-shirt",'
        "1.38,2015-09-14,2015-09-20,T-Shirts,$1.38\n",
    )
    info = next(read_product_information(stream))
    assert info.model_dump(
        include={"catalog_color", "brand", "keywords", "piece_sale_price", "sale_start_date", "category", "map_price"},
    ) == {
        "catalog_color": "White",
        "brand": "Port & Company",
        "keywords": ["tee", "tees", "t-shirt"],
        "piece_sale_price": Decimal("1.38"),
        "sale_start_date": date(2015, 9, 14),
        "category": "T-Shirts",
        "map_price": Decimal("1.38"),
    }


def test_holding_file() -> None:
    """The acknowledgement says which warehouse ships each line, and whether stock is there."""
    lines = list(read_holding(FILES / "06-07-2022-1Holding.txt"))
    assert [(line.po_number, line.style, line.size, line.warehouse, line.available) for line in lines] == [
        ("FX34689", "363B", "S", Warehouse.CINCINNATI, True),
        ("FX34689", "K500", "L", Warehouse.RENO, False),
    ]


def test_shipment_status_file() -> None:
    """The tab-delimited status file links a box's tracking number and license plate to its lines."""
    status = next(read_shipment_status(FILES / "1-15-16Status.txt"))
    assert status.model_dump(
        include={"po_number", "sales_order_number", "ship_date", "tracking_number", "license_plate", "size_index"},
    ) == {
        "po_number": "123456",
        "sales_order_number": "18367163",
        "ship_date": date(2015, 11, 20),
        "tracking_number": "1ZE435930310783934",
        "license_plate": "LP0002488302",
        "size_index": 4,
    }


LAYOUT = json.loads((Path(__file__).parent / "fixtures" / "ftp_layout.json").read_text(encoding="utf-8"))
REAL_FILES: list[tuple[str, Callable[..., Iterator[object]], tuple[str, ...], str]] = [
    ("SanMarPDD/SanMar_SDL_N.csv", read_catalog, catalog.SDL_COLUMNS, ","),
    ("SanMarPDD/SanMar_EPDD.csv", read_extended_catalog, catalog.EPDD_COLUMNS, ","),
    ("SanMarPDD/sanmar_dip.txt", read_warehouse_inventory, inventory.WAREHOUSE_INVENTORY_COLUMNS, "|"),
    ("SanMarPDD/sanmar_activeproductsexport.txt", read_active_products, inventory.ACTIVE_PRODUCTS_COLUMNS, "|"),
    ("SanMarPDD/sanmar_pdd.txt", read_pdd, legacy.PDD_COLUMNS, "|"),
    ("SanMarPDD/Catalog.txt", read_catalog_txt, legacy.CATALOG_TXT_COLUMNS, "\t"),
    ("SanMarPDD/sanmar_saleItems.txt", read_sale_items, legacy.SALE_ITEM_COLUMNS, "|"),
    *(
        (path, read_product_information, catalog.PRODUCT_INFORMATION_COLUMNS, ",")
        for path in (
            "SanMarPDD/SanMarPI/SanMarPI-Bulk-{customer_number}.csv",
            "SanMarPDD/SanMarPI/SanMarPI-Delta-{customer_number}.csv",
            "SanMarPDD/SanMarPI/Brand_A4_09-25-2026.csv",
            "SanMarPDD/SanMarPI/Category_Accessories_09-25-2026.csv",
        )
    ),
]


@pytest.mark.parametrize(("path", "reader", "columns", "delimiter"), REAL_FILES, ids=[entry[0] for entry in REAL_FILES])
def test_readers_know_sanmars_real_headers(
    path: str,
    reader: Callable[..., Iterator[object]],
    columns: tuple[str, ...],
    delimiter: str,
) -> None:
    """Every column of the header SanMar's server really writes is one the reader expects.

    The headers were recorded from SanMar's SFTP server by ``scripts/snapshot_wsdls.py --ftp``.
    """
    header = LAYOUT["headers"][path]
    names = [normalize_column(name) for name in next(csv.reader(io.StringIO(header), delimiter=delimiter))]
    assert names == list(columns)
    assert list(reader(io.StringIO(header + "\n"))) == []


def test_legacy_text_files() -> None:
    """The older text files parse, including Catalog.txt's own spelling of two columns."""
    pdd = next(
        read_pdd(
            io.StringIO(
                LAYOUT["headers"]["SanMarPDD/sanmar_pdd.txt"]
                + '\n"20828"|"K500"|"Port Authority"|"K500"|"NA"|"Black"|"L"|"Silk Touch Polo"|""|"12.98"|"12.98"|"1"'
                '|"10.98"|"36"|"0"|"0.6094"|"L"|"4"|"Unknown"|"00191265001373"\n',
            ),
        ),
    )
    catalog_txt = next(
        read_catalog_txt(
            io.StringIO(
                LAYOUT["headers"]["SanMarPDD/Catalog.txt"]
                + "\n20828\tK500\tPort Authority\tK500\tNA\tBlack\tL\tSilk Touch Polo\t\t12.98\t12.98\t1\t10.98\t36\t0"
                "\t0.6094\tL\t4\tUnknown\t00191265001373\n",
            ),
        ),
    )
    assert pdd == catalog_txt
    assert (pdd.style, pdd.catalog_color, pdd.size_index, pdd.mill_style, pdd.case_price, pdd.gtin) == (
        "K500",
        "Black",
        4,
        "K500",
        Decimal("10.98"),
        "00191265001373",
    )

    sale = next(
        read_sale_items(
            io.StringIO(
                LAYOUT["headers"]["SanMarPDD/sanmar_saleItems.txt"]
                + '\n"20828"|"K500"|"Port Authority"|"K500"|"NA"|"Black"|"L"|"Silk Touch Polo"|""|"9.98"|"9.98"|"1"'
                '|"8.98"|"36"|"0"|"0.6094"|"L"|"4"|"Unknown"|""|"10/14/2026"|"10/20/2026"\n',
            ),
        ),
    )
    assert (sale.piece_sale_price, sale.case_sale_price, sale.sale_end_date) == (
        Decimal("9.98"),
        Decimal("8.98"),
        date(2026, 10, 20),
    )
