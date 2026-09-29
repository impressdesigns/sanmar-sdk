Products
========

SanMar publishes its catalog three ways. For the whole catalog, or anything refreshed
daily, SanMar asks that you read its files rather than call its services style by style.

.. list-table::
   :header-rows: 1

   * - Need
     - Use
   * - The whole catalog, refreshed monthly or daily
     - ``SanMar_SDL_N.csv`` or ``SanMar_EPDD.csv`` over SFTP (:doc:`ftp`)
   * - One style, on demand
     - ``sanmar.products.get`` or ``sanmar.promostandards.product_data.get``
   * - What changed since last time
     - ``sanmar.products.request_delta_file`` (once a day), or
       ``sanmar.promostandards.product_data.modified_since``
   * - Images and spec sheets
     - ``sanmar.promostandards.media_content.get``, or the image links in the product
       files

SanMar's product information service
------------------------------------

:meth:`~sanmar_sdk.standard.ProductInfoService.get` returns one
:class:`~sanmar_sdk.standard.ProductInfo` per style, color and size, with its images and
prices flattened in:

.. code-block:: python

   for item in sanmar.products.get("K500", catalog_color="Black"):
       print(item.size, item.unique_key, item.prices.piece_price, item.images.front_model)

Narrow by catalog color, by size, or both; see :doc:`identifiers` for which color.
:meth:`~sanmar_sdk.standard.ProductInfoService.get_many` looks up several styles in one
call.

Product files on request
~~~~~~~~~~~~~~~~~~~~~~~~

The same service can ask SanMar to write a product file to the SFTP server, about 20
minutes later, in ``SanMarPDD/SanMarPI``:

.. code-block:: python

   request = sanmar.products.request_brand_file("Port & Co")
   request.file_pattern  # 'Brand_PortCo_*.csv': SanMar dates brand and category files

   # Later, over SFTP:
   with SanMarFTP(123456, "ftp-password", host_key=KEY) as ftp:
       name = ftp.newest(request.folder, request.file_pattern)
       with ftp.product_information(name) as products:
           for product in products:
               ...

:meth:`~sanmar_sdk.standard.ProductInfoService.request_bulk_file` writes the whole catalog
(SanMar allows it once a month) and
:meth:`~sanmar_sdk.standard.ProductInfoService.request_delta_file` what changed since the
last bulk or delta file (once a day). A delta file consumes the changes it reports: the
next one starts from it.

PromoStandards Product Data
---------------------------

:meth:`~sanmar_sdk.promostandards.ProductDataService.get` describes a whole style: its
descriptions, categories, keywords, price groups and every part (color and size), with
GTINs, dimensions and case packs.

.. code-block:: python

   product = sanmar.promostandards.product_data.get("K500")
   for part in product.parts:
       print(part.part_id, part.catalog_color, part.apparel_size.size, part.gtin)

The list methods return :class:`~sanmar_sdk.promostandards.PartReference` items:

- :meth:`~sanmar_sdk.promostandards.ProductDataService.closeouts` lists every discontinued
  part.
- :meth:`~sanmar_sdk.promostandards.ProductDataService.modified_since` lists what changed
  after a point in time.
- :meth:`~sanmar_sdk.promostandards.ProductDataService.sellable` lists what SanMar sells,
  across the catalog or within a style.

Media
-----

:meth:`~sanmar_sdk.promostandards.MediaContentService.get` lists a style's images or
documents. SanMar recommends asking for a whole style, which returns every color's images
in one call:

.. code-block:: python

   from sanmar_sdk.promostandards import ClassType, MediaType

   fronts = sanmar.promostandards.media_content.get("K500", class_type=ClassType.FRONT)
   documents = sanmar.promostandards.media_content.get("K500", media_type=MediaType.DOCUMENT)

SanMar serves images and documents only, not audio or video.
