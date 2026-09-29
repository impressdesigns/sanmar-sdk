Tracking orders
===============

Once an order is placed, SanMar reports on it four ways.

.. list-table::
   :header-rows: 1

   * - Question
     - Use
   * - Where does an order stand?
     - ``sanmar.promostandards.order_status``
   * - What shipped, and under which tracking numbers?
     - The daily status file over SFTP, or ``sanmar.promostandards.shipment_notifications``
   * - What is in this box?
     - ``sanmar.packing_slips.get``, with the license plate number on the box's label

SanMar asks that the status and shipment services be called no more than three times a
day, starting two hours after an order is placed. EDEV orders are only shipped and
invoiced when you email SanMar their PO numbers, which can take a day or two.

Order status
------------

.. code-block:: python

   for status in sanmar.promostandards.order_status.by_purchase_order("85496"):
       for sales_order in status.sales_orders:
           print(sales_order.sales_order_number, sales_order.status, sales_order.issue_category)
           for line in sales_order.lines:
               print(line.part_id, line.quantity_ordered, line.quantity_shipped, line.status)
       if status.finished:
           ...  # complete or canceled: SanMar will report nothing more

A status is one of :class:`~sanmar_sdk.promostandards.Status`, or the text SanMar sent if
it is none of them. An order on hold or backordered stays
:attr:`~sanmar_sdk.promostandards.Status.RECEIVED`, with an ``issue_category`` of
``generalHold`` or ``backOrderHold``. Once a backordered order has an in-hands date from
SanMar's sales team, SanMar asks that you stop checking it until that date has passed.

Besides :meth:`~sanmar_sdk.promostandards.OrderStatusService.by_purchase_order`, there are
lookups by SanMar sales order, by change since a time (up to 30 days back), and for every
open order or every open order with an issue.

.. note::

   A new order is not in SanMar's system right away. A lookup for it raises
   :class:`~sanmar_sdk.NotFoundError` with code 301; wait at least 24 hours before trying
   again. If SanMar still cannot find it after 48, the order may not have reached SanMar.

Shipments
---------

.. code-block:: python

   for shipment in sanmar.promostandards.shipment_notifications.by_purchase_order("85496"):
       print(shipment.po_number, shipment.complete, shipment.tracking_numbers)

Look shipments up by purchase order, by SanMar sales order, or everything shipped since a
time up to seven days back. Each lists the warehouse it left from, the address it went to,
and every package with its items.

The daily status file
~~~~~~~~~~~~~~~~~~~~~

Where SanMar has set one up, it writes a tab-delimited file every night listing everything
that shipped that day, box by box, with tracking numbers, costs and license plate numbers.
SanMar recommends it over the shipment service. Read it with
:func:`~sanmar_sdk.ftp.read_shipment_status`.

Packing slips
-------------

Every box SanMar ships carries a license plate number (LPN) on its label.
:meth:`~sanmar_sdk.standard.PackingSlipService.get` returns what is in it:

.. code-block:: python

   slip = sanmar.packing_slips.get("LP1234567890")
   for item in slip.items:
       print(item.style, item.catalog_color, item.size, item.quantity)
