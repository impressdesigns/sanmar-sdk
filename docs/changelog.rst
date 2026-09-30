Changelog
=========

- :release:`1.0.0 <30th September 2026>`
- :feature:`-` Read SanMar's SFTP files, and place orders through them, with ``sanmar_sdk.ftp.SanMarFTP``. Files stream row by row into typed records.
- :feature:`-` Add SanMar's PromoStandards services under ``SanMar.promostandards``: Product Data 2.0.0, Media Content 1.1.0, Inventory 2.0.0, Pricing and Configuration 1.0.0, Order Status 2.0.0, Order Shipment Notification 1.0.0, Invoice 1.0.0 and Purchase Order 1.0.0.
- :feature:`-` Add SanMar's own product information, inventory, pricing, invoicing and purchase order services.
- :feature:`-` Rebuild the SDK on zeep and strict Pydantic models. ``SanMar`` now takes ``customer_number``, ``username`` and ``password``, plus optional ``environment``, ``timeout`` and ``transport``, and no longer takes ``version`` or ``packing_slip_service_wsdl_url``. ``get_packing_slip`` is now ``packing_slips.get``, and returns a typed ``PackingSlip``.
- :release:`0.1.0 <7th October 2023>`
- :feature:`1` Initialize package
