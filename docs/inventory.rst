Inventory
=========

SanMar reports stock per warehouse, and caps what it reports for each warehouse: at 3,000
pieces, according to the Web Services guide. How often you need stock decides where to get
it:

.. list-table::
   :header-rows: 1

   * - Need
     - Use
   * - The whole catalog, up to a few times a day
     - ``sanmar_dip.txt`` over SFTP, refreshed hourly
       (:meth:`~sanmar_sdk.ftp.SanMarFTP.warehouse_inventory`), or ``SanMar_EPDD.csv``
       for totals only
   * - A live check while taking an order
     - ``sanmar.promostandards.inventory.get``, which checks up to 200 parts at once
   * - One style, color and size at one warehouse
     - ``sanmar.inventory.get_quantity``

SanMar asks that integrations not call its inventory services thousands of times a day.

PromoStandards Inventory
------------------------

:meth:`~sanmar_sdk.promostandards.InventoryService.get` reports every part of a style, or
a filtered set of them:

.. code-block:: python

   for part in sanmar.promostandards.inventory.get("K500", sizes=["L", "XL"], catalog_colors=["Black"]):
       print(part.part_id, part.quantity, [(stock.warehouse, stock.quantity) for stock in part.locations])

To check a whole cart in one call, pass up to 200 part ids. SanMar still needs a valid
style in the first argument, but does not require the parts to belong to it:

.. code-block:: python

   cart = sanmar.promostandards.inventory.get("K500", part_ids=["208284", "118864", "591373"])

Part ids and size or color filters cannot be combined.

SanMar's inventory service
--------------------------

:meth:`~sanmar_sdk.standard.InventoryService.get` reports a style, narrowed by catalog
color, size, or both, as one :class:`~sanmar_sdk.standard.SkuStock` per color and size:

.. code-block:: python

   [stock] = sanmar.inventory.get("K500", catalog_color="Black", size="L")
   stock.total  # across every warehouse
   stock.warehouses  # one WarehouseStock each

For one warehouse, :meth:`~sanmar_sdk.standard.InventoryService.get_quantity` returns just
the number:

.. code-block:: python

   from sanmar_sdk import Warehouse

   sanmar.inventory.get_quantity("K500", "Black", "L", Warehouse.DALLAS)

The inventory file
------------------

``sanmar_dip.txt`` has one row per style, color, size and warehouse, with the current
piece, case and sale prices alongside the quantity. SanMar recommends it over the
services for anything but a live check:

.. code-block:: python

   with SanMarFTP(123456, "ftp-password", host_key=KEY) as ftp, ftp.warehouse_inventory() as rows:
       for row in rows:
           if row.discontinued_code == "S" and row.quantity == 0:
               continue
           ...

SanMar suggests skipping rows it has discontinued (``discontinued_code`` ``S``) that are
out of stock. Discontinued colors stay in the file, at 0, while any size of them still has
12 or more pieces, and returned stock can bring one back, so check again later rather than
dropping it for good.
