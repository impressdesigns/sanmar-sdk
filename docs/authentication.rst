Authentication
==============

SanMar has three separate sets of credentials, and each works in one place only.

.. list-table::
   :header-rows: 1

   * - Credentials
     - Used by
     - Where they come from
   * - Customer number, SanMar.com username and password
     - SanMar's own web services (:class:`~sanmar_sdk.SanMar`)
     - Create a web user at https://www.sanmar.com/signup/webuser, then ask
       sanmarintegrations@sanmar.com to enable web service access.
   * - SanMar.com username and password
     - SanMar's PromoStandards services (``sanmar.promostandards``)
     - The same web user. PromoStandards calls do not send the customer number.
   * - Customer number and FTP password
     - The SFTP server (:class:`~sanmar_sdk.ftp.SanMarFTP`)
     - SanMar issues the FTP password during onboarding. SanMar.com logins do not work
       on the SFTP server.

EDEV, SanMar's test environment, has its own web service logins, separate from production.
Ask sanmarintegrations@sanmar.com for them. There is no test SFTP server: order files
uploaded there go straight to production.

Web services
------------

One :class:`~sanmar_sdk.SanMar` reaches every web service, SanMar's own and
PromoStandards alike:

.. code-block:: python

   from sanmar_sdk import Environment, SanMar

   sanmar = SanMar(
       123456,  # customer number
       "sanmar-username",
       "sanmar-password",
       environment=Environment.EDEV,  # PRODUCTION is the default
       timeout=30.0,
   )

Nothing is loaded until the first call, which fetches that service's WSDL. The client
points every service at the environment it was built for, whatever address the WSDL
itself names, so a client built for EDEV can never place a production order.

SanMar's web services listen on port 8080, which some networks block. If a call times out
before anything comes back, check that the machine can reach ``ws.sanmar.com:8080``.

A rejected login raises :class:`~sanmar_sdk.AuthenticationError`. An account that is not
set up for a service raises :class:`~sanmar_sdk.AuthorizationError`; ordering in
particular has to be switched on by SanMar, first on EDEV and then in production (see
:doc:`orders`).

SFTP
----

The SFTP server checks your host key the way any SSH server does, so the SDK refuses a
server it has not been told to trust. Get SanMar's key once, check it, and pin it:

.. code-block:: console

   $ ssh-keyscan -p 2200 ftp.sanmar.com

.. code-block:: python

   from sanmar_sdk.ftp import SanMarFTP

   with SanMarFTP(123456, "ftp-password", host_key="ssh-rsa AAAA...") as ftp:
       ...

Or pass ``known_hosts`` to trust the entries in a known_hosts file instead. See :doc:`ftp`
for the rest.
