Errors
======

Every error the SDK raises on purpose is a :class:`~sanmar_sdk.SanMarError`, so one
``except`` clause catches anything SanMar or the network did. Each is raised ``from`` the
zeep, requests or paramiko error underneath, which stays available as ``__cause__``.

.. code-block:: text

   SanMarError
   ├── SanMarConnectionError   SanMar could not be reached, or answered with an HTTP error
   ├── SoapFaultError          a SOAP fault SanMar did not explain further
   ├── ResponseError           SanMar's response did not match its own WSDL
   ├── FileFormatError         a data file did not have the expected layout
   └── ServiceError            SanMar reported an error for the request
       ├── AuthenticationError
       ├── AuthorizationError
       ├── NotFoundError
       └── RequestError

Mistakes the SDK can catch before sending anything, such as a PO number with a comma or a
date range SanMar would refuse, raise Pydantic's ``ValidationError`` or
:class:`ValueError` instead, and nothing is sent.

Nothing found
-------------

Methods that return a list return an empty one when SanMar finds nothing. Methods that
return one thing, such as an invoice or a product, raise :class:`~sanmar_sdk.NotFoundError`.

SanMar's own services
---------------------

SanMar's own services report errors as a flag and a message, or as a SOAP fault, never with
a code. The message decides the exception: a failed login is an
:class:`~sanmar_sdk.AuthenticationError`, an unknown style, color or size a
:class:`~sanmar_sdk.NotFoundError` (with a reminder about catalog colors when a color was
given), and anything else invalid a :class:`~sanmar_sdk.RequestError`.

PromoStandards
--------------

PromoStandards services report errors with a code, which
:attr:`~sanmar_sdk.ServiceError.code` carries:

.. list-table::
   :header-rows: 1

   * - Codes
     - Meaning
     - Raised as
   * - 100, 105, 110
     - Unknown account, or credentials missing or wrong
     - :class:`~sanmar_sdk.AuthenticationError`
   * - 104
     - The account is not authorized for this service
     - :class:`~sanmar_sdk.AuthorizationError`
   * - 130, 135, 140, 145, 150, 200
     - Product, part, color or size not found
     - :class:`~sanmar_sdk.NotFoundError`
   * - 160
     - No results
     - An empty list, or :class:`~sanmar_sdk.NotFoundError` for a single lookup
   * - 301
     - Purchase order or invoice not found (yet)
     - :class:`~sanmar_sdk.NotFoundError`, with SanMar's advice to wait
   * - 115, 120, 125, 155, 300, 302, 303
     - Missing or invalid field, unsupported request, bad date or range
     - :class:`~sanmar_sdk.RequestError`
   * - 999, and any other
     - General error
     - :class:`~sanmar_sdk.ServiceError`

Information and warning messages are not errors. They go to the ``sanmar_sdk`` logger, at
debug and warning level.
