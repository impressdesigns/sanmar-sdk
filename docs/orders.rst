Orders
======

SanMar takes integrated orders three ways. All three need SanMar to set the account up
first: ask sanmarintegrations@sanmar.com, place test orders on EDEV to an address you will
really ship to, and email SanMar the PO numbers. Setup can take 24 to 48 hours in each
environment.

.. list-table::
   :header-rows: 1

   * - Channel
     - Items named by
     - Test environment
     - Extras
   * - SanMar's purchase order service (``sanmar.purchase_orders``)
     - :class:`~sanmar_sdk.SkuKey` or :class:`~sanmar_sdk.StyleColorSize`
     - EDEV
     - Checks stock before placing; will call; truck freight
   * - PromoStandards (``sanmar.promostandards.purchase_orders``)
     - Part id (unique key)
     - EDEV
     - None: blank goods, shipped
   * - Order files over SFTP (:class:`~sanmar_sdk.ftp.SanMarFTP`)
     - :class:`~sanmar_sdk.SkuKey` only
     - None; every file goes to production
     - Upload now, release later; will call; truck freight

Where to ship
-------------

Every channel takes the same :class:`~sanmar_sdk.ShipTo`. Its limits are the tightest
across SanMar's channels, so an address that validates is accepted by all of them:

.. code-block:: python

   from sanmar_sdk import ShipTo

   ship_to = ShipTo(
       company="IMPRESS DESIGNS",
       attention="Receiving",
       address1="1404 W MAIN ST",  # SanMar asks for ST, AVE, RD, DR and BLVD
       city="CARROLLTON",
       state="TX",
       zip_code="75006",
       email="orders@example.com",  # confirmations and tracking go here
       residential=False,
   )

SanMar's order processor splits on commas and its order files are ASCII, so every order
field rejects commas and non-ASCII characters when the model is built, before anything is
sent.

SanMar's own purchase order service and its order files carry no country, so a
:class:`~sanmar_sdk.orders.PurchaseOrder` takes US addresses only. Only PromoStandards sends
``country``.

How to ship
~~~~~~~~~~~

:class:`~sanmar_sdk.ShipMethod` lists SanMar's ship methods: UPS services, USPS Ground
Advantage and Priority Mail, PSST (Pack Separately, Ship Together, which needs the
ship-to to match the address SanMar has on file exactly) and truck freight for orders over
500 pounds. PromoStandards takes every one but truck.

To pick an order up instead, pass :class:`~sanmar_sdk.WillCall` with the warehouse. Only
SanMar's own service and order files support it, and only for accounts set up for
warehouse selection.

Which warehouse
~~~~~~~~~~~~~~~

Leave each line's ``warehouse`` unset unless SanMar has set the account up for warehouse
selection; SanMar otherwise ships from the warehouses the account's shipping option picks.

Duplicate lines
~~~~~~~~~~~~~~~

SanMar checks stock line by line, so two lines for the same item from the same warehouse
can each pass while their total is short. Every channel combines them before sending, and
a combined quantity over the five-digit limit fails rather than going out wrong.

SanMar's purchase order service
-------------------------------

.. code-block:: python

   from sanmar_sdk import ShipMethod, SkuKey, StyleColorSize
   from sanmar_sdk.orders import OrderLine, PurchaseOrder

   order = PurchaseOrder(
       po_number="85496",
       ship_to=ship_to,
       ship_method=ShipMethod.UPS_GROUND,
       lines=[
           OrderLine(item=SkuKey(inventory_key=20828, size_index=4), quantity=12),
           OrderLine(item=StyleColorSize(style="PC61", catalog_color="Charcoal", size="L"), quantity=6),
       ],
   )

   check = sanmar.purchase_orders.check(order)
   if check.available:
       message = sanmar.purchase_orders.submit(order)
   else:
       for line in check.lines:
           print(line.style, line.catalog_color, line.size, line.message)

:meth:`~sanmar_sdk.standard.PurchaseOrderService.check` asks SanMar whether the order could
ship, and from where, without placing it. Being out of stock is an answer, not an error.
:meth:`~sanmar_sdk.standard.OrderCheck.line_for` finds the line for a given item.

Name items by :class:`~sanmar_sdk.SkuKey` where you can, as SanMar recommends: a key
cannot be misspelled. By :class:`~sanmar_sdk.StyleColorSize`, the color must be the
catalog color (see :doc:`identifiers`).

PromoStandards
--------------

.. code-block:: python

   from sanmar_sdk.promostandards import PromoStandardsOrder, PromoStandardsOrderLine

   order = PromoStandardsOrder(
       po_number="85496",
       ship_to=ship_to,
       ship_method=ShipMethod.UPS_GROUND,
       lines=[PromoStandardsOrderLine(part_id="208284", quantity=12)],
   )
   transaction_id = sanmar.promostandards.purchase_orders.send(order)

PromoStandards requires many fields SanMar ignores: order and line totals, rush,
consolidation, blind shipping, tolerances, partial shipment flags. The SDK fills them with
neutral values and leaves out everything SanMar says not to send. ``ship_to.phone`` is
sent here, and nowhere else.

The transaction id SanMar returns starts with the PO number.

Order files over SFTP
---------------------

An SFTP order is a batch of files: ``CustInfo.txt`` (where each purchase order ships) and
``Details.txt`` (what is on it), uploaded to ``In``, then a ``Release`` file that releases
some or all of the batch for processing, any time within two weeks.

.. code-block:: python

   from sanmar_sdk.ftp import SanMarFTP

   with SanMarFTP(123456, "ftp-password", host_key=KEY) as ftp:
       ftp.upload_orders("09-29-2026-1", [order])
       # Within about 15 minutes, SanMar acknowledges the batch:
       with ftp.holding("09-29-2026-1") as lines:
           for line in lines:
               print(line.po_number, line.warehouse, line.available)
       ftp.release_orders("09-29-2026-1", ["85496"])

Batch names hold letters, digits and dashes, and must never repeat; SanMar suggests the
date and a running number for the day. Order files name items by
:class:`~sanmar_sdk.SkuKey` only, and every order needs a ship-to email.

These are production orders. SanMar has no test environment for SFTP ordering, so try the
same :class:`~sanmar_sdk.orders.PurchaseOrder` against EDEV through SanMar's purchase
order service first.
