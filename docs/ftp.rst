SFTP files
==========

SanMar's SFTP server holds its product, inventory and pricing files, and takes order files.
Its layout is documented in the FTP Integration Guide, except where noted; the column lists
the SDK reads were checked against the files on the server, which differ from the guide in
places (see :doc:`sources`).

Connecting
----------

The server is ``ftp.sanmar.com``, port 2200, SFTP only. The username is the customer
number and the password is the FTP password SanMar issued, not a SanMar.com login.

.. code-block:: python

   from sanmar_sdk.ftp import SanMarFTP

   KEY = "ssh-rsa AAAA..."  # from ssh-keyscan -p 2200 ftp.sanmar.com, checked once

   with SanMarFTP(123456, "ftp-password", host_key=KEY) as ftp:
       print(ftp.list_folder("SanMarPDD"))

The SDK refuses a server whose key it has not been told to trust: pin the key with
``host_key``, or pass a ``known_hosts`` file. SanMar's server offers only the older
``ssh-rsa`` host key algorithm, which paramiko 5 dropped, so the SDK requires paramiko 4.

File names match case-insensitively: SanMar's guides spell the same file several ways.

Streaming
---------

Every file is read as a stream, parsed row by row as it downloads, and never held in
memory or written to disk. Read inside the ``with`` block that opened it:

.. code-block:: python

   with ftp.catalog() as products:
       for product in products:
           print(product.style, product.catalog_color, product.size, product.unique_key)

Zip archives are read in place, one member at a time. :meth:`~sanmar_sdk.ftp.SanMarFTP.stream`
reads any file through any reader, and :meth:`~sanmar_sdk.ftp.SanMarFTP.download` copies a
file down instead.

Every reader also takes a local path or an open text file, so a file fetched some other way
parses the same:

.. code-block:: python

   from pathlib import Path
   from sanmar_sdk.ftp import read_catalog

   for product in read_catalog(Path("SanMar_SDL_N.csv")):
       ...

A malformed row raises :class:`~sanmar_sdk.FileFormatError` with its line number. Blank
cells, ``NA`` and ``NLA`` read as ``None``, and prices as :class:`~decimal.Decimal`.

The files
---------

Everything in ``SanMarPDD`` is refreshed nightly, finished by 6 AM Pacific, and has the same
name for every SanMar customer.

.. list-table::
   :header-rows: 1

   * - File
     - What it is
     - Read with
   * - ``SanMar_SDL_N.csv`` (also zipped)
     - The main product file: one row per style, color and size, with descriptions,
       prices, image links and GTINs. The source of catalog colors.
     - :meth:`~sanmar_sdk.ftp.SanMarFTP.catalog`, :func:`~sanmar_sdk.ftp.read_catalog`
   * - ``SanMar_EPDD.csv`` (also zipped)
     - The product file with stock across all warehouses. A style in several categories
       appears once per category.
     - :meth:`~sanmar_sdk.ftp.SanMarFTP.extended_catalog`,
       :func:`~sanmar_sdk.ftp.read_extended_catalog`
   * - ``SanMar_SDL_DI.zip``
     - The product file with the same columns as SDL_N.
     - :func:`~sanmar_sdk.ftp.read_catalog`
   * - ``sanmar_dip.txt``
     - Stock by warehouse, with current prices, refreshed hourly.
     - :meth:`~sanmar_sdk.ftp.SanMarFTP.warehouse_inventory`,
       :func:`~sanmar_sdk.ftp.read_warehouse_inventory`
   * - ``sanmar_activeproductsexport.txt``
     - An older stock-by-warehouse export, without sale prices.
     - :func:`~sanmar_sdk.ftp.read_active_products`
   * - ``sanmar_pdd.txt``, ``Catalog.txt``
     - Older catalog files: no images, no display colors.
     - :func:`~sanmar_sdk.ftp.read_pdd`, :func:`~sanmar_sdk.ftp.read_catalog_txt`
   * - ``sanmar_saleItems.txt``
     - What is on sale, with sale prices and dates.
     - :func:`~sanmar_sdk.ftp.read_sale_items`
   * - ``SanMarPI/``
     - Product files written on request by the product information service (see
       :doc:`products`). Bulk and delta files are named with the customer number; brand
       and category files with the date.
     - :meth:`~sanmar_sdk.ftp.SanMarFTP.product_information`,
       :func:`~sanmar_sdk.ftp.read_product_information`

``SanMar_SDL_D.zip``, ``HtsCodeCompliance.csv``, ``sanmar_shopify.csv`` and the image
archives are on the server too, and the SDK has no reader for them. ``SanMar_SDL_D`` is in
none of SanMar's guides; see :doc:`identifiers` before using its colors.

On request, SanMar also writes files to the account's own folders: customer pricing (see
:doc:`pricing`), a daily shipment status file (see :doc:`tracking`), and daily invoices.

Ordering
--------

The ``In``, ``Release``, ``Holding`` and ``Done`` folders are for order files; see
:doc:`orders`.
