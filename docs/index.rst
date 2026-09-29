idi-sanmar-sdk
==============

A typed Python SDK for SanMar: its own web services, its PromoStandards web services, and
the data and order files on its SFTP server.

Everything you pass in is a strict, validated model, and everything that comes back is a
typed record, so SOAP envelopes, PromoStandards' required-but-ignored fields and SanMar's
file layouts stay inside the SDK. Files stream row by row, however large.

.. code-block:: python

   from sanmar_sdk import SanMar

   sanmar = SanMar(123456, "sanmar-username", "sanmar-password")

   product = sanmar.promostandards.product_data.get("K500")
   stock = sanmar.promostandards.inventory.get("K500", sizes=["L"])

Start with :doc:`authentication`, then read :doc:`identifiers` before anything else: most
SanMar integration problems come from using the wrong color name.

Guides
------

.. toctree::
   :maxdepth: 1

   authentication
   identifiers
   products
   inventory
   pricing
   orders
   tracking
   invoices
   ftp
   errors
   sources

Module Index
------------

.. toctree::
   :maxdepth: 1

   autoapi/index

.. toctree::
   :caption: Other:
   :hidden:

   changelog

Extras
------

* :ref:`genindex`
* :ref:`search`
* :doc:`changelog`
