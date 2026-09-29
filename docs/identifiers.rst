Identifiers
===========

SanMar names the same item several ways, and each service accepts only some of them.
Getting these right is most of the work of a SanMar integration.

Colors: catalog color, not color name
-------------------------------------

Every SanMar product has two color names, and only one of them works in a request.

.. list-table::
   :header-rows: 1

   * - In the SDK
     - What it is
     - Where SanMar calls it that
     - Example
   * - ``catalog_color``
     - SanMar's *catalog* or *mainframe* color. Every lookup and every order uses it.
     - ``SANMAR_MAINFRAME_COLOR`` in ``SanMar_SDL_N.csv`` and ``SanMar_EPDD.csv``;
       ``CATALOG_COLOR`` in the SanMarPI files and ``sanmar_dip.txt``; ``catalogColor``
       in the product information service; ``colorName`` and ``partColor`` in
       PromoStandards
     - ``Athletic Hthr``, ``DeepBlack``
   * - ``color_name``
     - The full display name, for showing to people. SanMar rejects it in requests.
     - ``COLOR_NAME``; ``color`` in the product information service;
       ``standardColorName`` in PromoStandards
     - ``Athletic Heather``, ``Deep Black``

The SDK never mixes the two: a field called ``catalog_color`` is always the catalog color,
everywhere. When SanMar cannot find a style and color, the error says so and reminds you
which column to use.

.. note::

   An integration that reads colors from the ``COLOR_NAME`` column, of any SanMar file,
   and then asks the web services about them will fail on every color whose display name
   differs from its catalog name. ``SanMar_SDL_D.csv``, which is on the SFTP server but in
   none of SanMar's guides, is one such file. Read ``SanMar_SDL_N.csv`` (or
   ``SanMar_EPDD.csv``) and use ``SANMAR_MAINFRAME_COLOR`` instead; with the SDK's
   readers, that is :attr:`~sanmar_sdk.ftp.ProductRecord.catalog_color`.

Sizes
-----

Sizes are SanMar's own labels (``S``, ``XL``, ``2XL``, ``OSFA``, pant sizes such as
``3232``), and every file and service uses the same ones. PromoStandards splits them into
a ``labelSize`` and, for sizes outside its fixed list, ``CUSTOM`` plus a ``customSize``;
:attr:`~sanmar_sdk.promostandards.ApparelSize.size` puts them back together.

Keys
----

.. list-table::
   :header-rows: 1

   * - In the SDK
     - What it is
     - Where it is accepted
   * - ``style`` / ``product_id``
     - The style number, as printed in the catalog (``K500``). PromoStandards calls it
       the product id.
     - Lookups by style; PromoStandards everywhere
   * - :class:`~sanmar_sdk.SkuKey` (``inventory_key``, ``size_index``)
     - SanMar's key for one style, color and size. The inventory key is not the style
       number.
     - SanMar's own pricing and purchase order services; SFTP order files accept nothing
       else
   * - ``unique_key`` / ``part_id``
     - Also one style, color and size: the inventory key with the size index appended.
       PromoStandards calls it the part id.
     - PromoStandards lookups and orders
   * - :class:`~sanmar_sdk.StyleColorSize`
     - A style, catalog color and size spelled out.
     - SanMar's own purchase order service

Every SanMar product file carries all of these, so any of them can be looked up from the
others. The SDK never derives a unique key from an inventory key and size index; it always
reads the one SanMar sends.

Warehouses
----------

:class:`~sanmar_sdk.Warehouse` numbers SanMar's warehouses as SanMar does. The same number
is the warehouse's PromoStandards FOB id, and its :attr:`~sanmar_sdk.Warehouse.code` is the
will-call code for picking an order up there.

.. list-table::
   :header-rows: 1

   * - Number
     - Warehouse
     - Will-call code
   * - 1
     - Seattle, WA
     - ``PRE``
   * - 2
     - Cincinnati, OH
     - ``CIN``
   * - 3
     - Dallas, TX
     - ``COP``
   * - 4
     - Reno, NV
     - ``REN``
   * - 5
     - Robbinsville, NJ
     - ``NJE``
   * - 6
     - Jacksonville, FL
     - ``JAC``
   * - 7
     - Minneapolis, MN
     - ``MSP``
   * - 12
     - Phoenix, AZ
     - ``PHX``
   * - 31
     - Richmond, VA
     - ``VA1``

A warehouse SanMar opens after this SDK was released still parses, as a plain ``int``.
