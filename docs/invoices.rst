Invoices
========

SanMar invoices once a day, after 9 PM Pacific, for what shipped that day. Pull invoices
the next day: SanMar suggests after 3 PM Pacific for the PromoStandards service. Once or
twice a day is plenty; there is no need to ask about the same order repeatedly.

SanMar's invoicing service
--------------------------

:class:`~sanmar_sdk.standard.InvoiceService` covers every lookup SanMar's own service
offers. Full invoices carry their lines; header lookups return just the totals, and allow
longer date ranges.

.. code-block:: python

   from datetime import date

   invoice = sanmar.invoices.get(58316700)
   print(invoice.header.total, [(line.style, line.quantity, line.amount) for line in invoice.lines])

   for header in sanmar.invoices.headers_by_invoice_date(date(2026, 1, 1), date(2026, 6, 30)):
       print(header.invoice_number, header.status, header.total)

.. list-table::
   :header-rows: 1

   * - Invoices
     - Headers only
     - Finds
   * - :meth:`~sanmar_sdk.standard.InvoiceService.get`
     -
     - One invoice, by number
   * - :meth:`~sanmar_sdk.standard.InvoiceService.by_purchase_order`
     - :meth:`~sanmar_sdk.standard.InvoiceService.headers_by_purchase_order`
     - A purchase order's invoices
   * - :meth:`~sanmar_sdk.standard.InvoiceService.by_invoice_date`
     - :meth:`~sanmar_sdk.standard.InvoiceService.headers_by_invoice_date`
     - Invoices dated within a range: up to 92 days, or a year for headers
   * - :meth:`~sanmar_sdk.standard.InvoiceService.by_order_date`
     - :meth:`~sanmar_sdk.standard.InvoiceService.headers_by_order_date`
     - Invoices for orders placed on a day
   * - :meth:`~sanmar_sdk.standard.InvoiceService.unpaid`
     - :meth:`~sanmar_sdk.standard.InvoiceService.unpaid_headers`
     - Every unpaid invoice
   * - :meth:`~sanmar_sdk.standard.InvoiceService.since_last_call`
     -
     - Everything invoiced since the last time it was called

:meth:`~sanmar_sdk.standard.InvoiceService.since_last_call` moves SanMar's bookmark
forward: whatever it returns will not be returned again. The first call returns the last
three months. Purchase order lookups match at most the first 13 characters of the PO
number.

Where SanMar has nothing to report, lookups return an empty list;
:meth:`~sanmar_sdk.standard.InvoiceService.get` raises :class:`~sanmar_sdk.NotFoundError`.

PromoStandards Invoice
----------------------

.. code-block:: python

   for invoice in sanmar.promostandards.invoices.by_date(date(2026, 9, 24)):
       print(invoice.invoice_number, invoice.invoice_type, invoice.amount_due)
       for line in invoice.lines:
           print(line.part_id, line.invoice_quantity, line.extended_price)

Look invoices up by purchase order, by invoice number, by invoice date, or everything
issued since a point in time.

Invoice files
-------------

On request, SanMar also writes a daily invoice file to the SFTP server, as fixed-width
text, Excel or EDI 810. The SDK does not read these yet; the services return the same
data.
