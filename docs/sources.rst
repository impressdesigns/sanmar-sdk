Sources
=======

The SDK is written against these revisions of SanMar's integration guides, also available
as :data:`sanmar_sdk.sources.GUIDES`:

.. list-table::
   :header-rows: 1

   * - Guide
     - Version
     - Updated
     - Covers
   * - `SanMar Web Services Integration Guide <https://www.sanmar.com/medias/sys_master/pdf/h7a/ha0/33815499964446/SanMar-Web-Services-Integration-Guide-24.6/SanMar-Web-Services-Integration-Guide-24.6.pdf>`_
     - 24.6
     - August 2026
     - Product, inventory, pricing, invoice, order status, shipment and packing slip
       services, SanMar's own and PromoStandards
   * - `SanMar Purchase Order Integration Guide <https://www.sanmar.com/medias/sys_master/root/h4b/ha7/33815499767838/SanMar-Purchase-Order-Integration-Guide-24.5/SanMar-Purchase-Order-Integration-Guide-24.5.pdf>`_
     - 24.5
     - August 2026
     - Ordering through SanMar's own service, PromoStandards, and SFTP order files
   * - `SanMar FTP Integration Guide <https://www.sanmar.com/medias/sys_master/root/h08/hae/33815499571230/SanMar-FTP-Integration-Guide-v23.6/SanMar-FTP-Integration-Guide-v23.6.pdf>`_
     - 23.6
     - August 2026
     - The SFTP server and its files

Where the guides are wrong or disagree with themselves, the SDK follows what SanMar's
servers actually do:

- **Web services** follow SanMar's WSDLs, recorded from production into ``tests/wsdl``
  with ``scripts/snapshot_wsdls.py``. Every request the SDK builds is serialized by zeep
  against them in the test suite, so an element name, order or type the WSDL does not
  allow fails a test. ``tests/live`` checks that SanMar still serves the same WSDLs.
- **SFTP files** follow the header lines of the files on SanMar's server, recorded into
  ``tests/fixtures/ftp_layout.json`` by the same script with ``--ftp``.
- **Responses** follow the guides' sample responses, which SanMar captured from its own
  servers. The SDK parses each of them strictly.

Web Services Integration Guide 24.6
-----------------------------------

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - The guide says
     - The SDK does
   * - PromoStandards Product Data has two production WSDLs,
       ``ProductDataServiceBindingV2?WSDL`` (page 8) and ``ProductDataServiceV2.xml?wsdl``
       (page 30).
     - Both serve identical operations. The SDK calls the one in the service's own section.
   * - The error flag is ``errorOccured`` in some places and ``errorOccurred`` in others.
     - The WSDLs use both: the product information service and purchase order lines
       ``errorOccured``, everything else ``errorOccurred``. The SDK reads each where its
       WSDL puts it.
   * - The by-warehouse inventory sample wraps its request in
       ``getInventoryQtyForStyleColorSize``.
     - Calls ``getInventoryQtyForStyleColorSizeByWhse``, with the warehouse as ``arg6``.
   * - The ``GetInvoicesByPurchaseOrderNo`` sample is a copy of ``GetInvoiceByInvoiceNo``,
       and the ``GetInvoicesHeaderByInvoiceDateRange`` sample calls
       ``GetInvoicesByInvoiceDateRange``.
     - Calls each operation by its own name, with the arguments its WSDL defines.
   * - Invoice operations are named ``GetInvoiceByInvoiceNo`` and ``GetInvoicesByInvoiceNo``,
       ``GetInvoiceByPurchaseOrderNo`` and ``GetInvoicesByPurchaseOrderNo``.
     - Uses the WSDL's ``GetInvoiceByInvoiceNo`` and ``GetInvoicesByPurchaseOrderNo``.
   * - The invoice login is ``custNo``, ``userName`` and ``password`` in the tables, and
       ``CustomerNo``, ``UserName`` and ``Password`` in the samples.
     - Sends ``CustomerNo``, ``UserName`` and ``Password``, as the WSDL defines.
   * - ``GetUnpaidInvoices`` takes an ``InvoiceNo``.
     - Sends only the login; the WSDL has no ``InvoiceNo`` there.
   * - The product-by-brand request field is ``brand`` in the table and ``brandName`` in the
       sample.
     - Sends ``brandName``, as the WSDL defines.
   * - PromoStandards fields are ``productID`` and ``primaryImageURL`` in the tables.
     - Uses the WSDLs' ``productId`` and ``primaryImageUrl``.
   * - ``getProductSellable`` requires a product id (page 8), or does not (page 42).
     - The product id is optional, as the WSDL has it.
   * - Inventory is listed by warehouse in descending order, while the sample is ascending;
       and a style, color and size lookup returns an unlabeled list of quantities, one short
       of the warehouse count in the sample.
     - Keeps SanMar's order, and labels every quantity with its warehouse. For a single
       size, the SDK asks for the style and color, whose response labels each warehouse,
       and picks the size out itself.
   * - The product information response table's descriptions are shifted by a row in
       places (size, case sale price, price code and text).
     - Names fields after their elements, not the descriptions.
   * - Media Content is version 1.1.0, but its namespace says 1.0.0.
     - Both are right: the WSDL's namespace is 1.0.0, and the version sent is 1.1.0.
   * - Pricing requires ``US`` and ``EN``; Product Data's examples send ``us`` and ``en``.
     - Sends ``US`` with ``EN`` for pricing and ``en`` for product data.
   * - Order Status reports success as code ``-0``.
     - SanMar sends ``0``; it is logged, not raised.
   * - ``fobCountry`` is ``USA`` in one sample and ``US`` in another; ``invoiceType`` is
       ``Invoice`` in the sample and ``INVOICE`` in the schema.
     - Keeps both as SanMar sends them.
   * - The order shipment notification date sample has an unclosed tag.
     - Builds the request from the WSDL.

Purchase Order Integration Guide 24.5
-------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - The guide says
     - The SDK does
   * - PromoStandards FOB id: "leave blank", while the sample sends ``1``.
     - Sends one only for a line that names a warehouse.
   * - PromoStandards ``locationLinkId`` is in the sample but not the table, and everything
       not in the table "should be removed".
     - Leaves it out.
   * - The tolerance is ``AllowOverRun`` in the table and ``AllowOverrun`` in the sample.
     - Sends ``ExactOnly``, which the schema also allows.
   * - The PromoStandards service is ``Ground`` in the sample and ship method table, and
       ``GROUND`` in the field table; ``NEXT DAY`` in one and ``NEXTDAY`` in the other.
     - Follows the ship method table and sample: ``Ground``, ``NEXT DAY``. Only an order
       can settle this; place one on EDEV before relying on anything but UPS Ground.
   * - The sample's "0 to 2 repetitions" comment sits on ``Shipment``.
     - The schema allows up to two ``shipReferences``, which is what it means.
   * - Release file names use a four-digit year in one example and two in another.
     - Batch names are yours to choose; the SDK checks only their characters.
   * - The Holding file's field table leaves out the size its example includes.
     - Reads the example's layout.

FTP Integration Guide 23.6
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - The guide says
     - The SDK does
   * - File names are spelled ``SanMar_SDL_N.csv`` and ``Sanmar_SDL_N.csv``,
       ``sanmar_dip.txt`` and ``Sanmar_dip.txt``.
     - Matches file and folder names case-insensitively.
   * - Some column names have stray spaces (``BACK_MODEL _IMAGE_URL``) or other
       punctuation.
     - Normalizes column names before matching them.
   * - ``SanMar_SDL_N.csv`` has ``COMPANION_STYLES`` and ``PRODUCT_MEASUREMENT``.
     - The file has ``COMPANION_STYLE`` and ``PRODUCT_MEASUREMENTS``; the SDK reads either.
   * - ``SanMar_EPDD.csv`` has the same image columns as SDL_N.
     - Its model and flat image columns drop SDL_N's ``_URL`` suffix; the SDK reads either.
   * - ``sanmar_dip.txt`` has ``SALE_START_DATE`` and ``SALE_END_DATE`` columns.
     - The file has only ``SALE_START_DATETIME`` and ``SALE_END_DATETIME``.
   * - ``sanmar_activeproductsexport.txt`` ends by repeating the inventory key.
     - It ends with the unique key.
   * - Stock is capped at 3,000 per warehouse, or 1,500, depending on the page.
     - Assumes no particular cap.
