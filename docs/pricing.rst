Pricing
=======

SanMar updates list and case prices once or twice a year, and sale prices every Monday and
Wednesday. For the whole catalog, read ``sanmar_dip.txt`` (piece, case and sale prices,
hourly) or ask SanMar to set up the daily customer pricing files; use the services for
individual styles.

SanMar's pricing service
------------------------

:meth:`~sanmar_sdk.standard.PricingService.get` prices a style, narrowed by catalog color,
size, or both. Each :class:`~sanmar_sdk.standard.PriceQuote` carries SanMar's piece, case
and sale prices, and ``my_price``, this account's own price:

.. code-block:: python

   for quote in sanmar.pricing.get("K500", catalog_color="Black"):
       print(quote.size, quote.piece_price, quote.case_price, quote.my_price)

Price one item by its key with :meth:`~sanmar_sdk.standard.PricingService.get_by_key`, or
several lookups at once with :meth:`~sanmar_sdk.standard.PricingService.get_many`.

Prices are :class:`~decimal.Decimal`. Where SanMar has no price it writes ``NA`` or
``NLA``; the SDK reads those as ``None``.

PromoStandards Pricing and Configuration
----------------------------------------

:meth:`~sanmar_sdk.promostandards.PricingService.get` prices every part of a style, or one
part, at the price type you ask for:

.. code-block:: python

   from sanmar_sdk.promostandards import PriceType

   for part in sanmar.promostandards.pricing.get("K500", price_type=PriceType.NET):
       for price in part.prices:
           print(part.part_id, price.min_quantity, price.price, price.uom)

- :attr:`~sanmar_sdk.promostandards.PriceType.NET` is this account's cost.
- :attr:`~sanmar_sdk.promostandards.PriceType.LIST` is SanMar's suggested retail price.
- :attr:`~sanmar_sdk.promostandards.PriceType.CUSTOMER` is special pricing SanMar has set
  up for the account.

PromoStandards prices by FOB point, which for SanMar is a warehouse. SanMar's prices do
not vary by warehouse, so the SDK sends Seattle unless told otherwise.
:meth:`~sanmar_sdk.promostandards.PricingService.fob_points` lists the warehouses; SanMar
asks that it be called no more than once a week.

Customer pricing files
----------------------

On request, SanMar writes customer pricing files to the account's outbound SFTP folder
every night after 2 AM Pacific. Read them with :func:`~sanmar_sdk.ftp.read_customer_prices`
and :func:`~sanmar_sdk.ftp.read_price_changes`:

.. list-table::
   :header-rows: 1

   * - File
     - What ``my_price`` holds
   * - ``sanmar_dp.csv``
     - The lowest price available to the account, for the whole catalog.
   * - ``sanmar_dpIncentive.csv``
     - Special program pricing, for the whole catalog, or 0 where there is none.
   * - ``sanmar_dpc.csv``
     - The lowest price, for only what changed since the day before. The first file has
       everything.

Where the outbound folder is depends on how SanMar sets the account up;
:meth:`~sanmar_sdk.ftp.SanMarFTP.list_folder` shows what is there. Then:

.. code-block:: python

   from sanmar_sdk.ftp import read_price_changes

   with ftp.stream("sanmar_dpc.csv", read_price_changes) as changes:
       for change in changes:
           print(change.unique_key, change.my_price)
