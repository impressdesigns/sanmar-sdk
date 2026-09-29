"""The SanMar web services client."""

from typing import TYPE_CHECKING

from ._soap import Credentials, SoapClient
from .common import Environment

if TYPE_CHECKING:
    from zeep import Transport


class SanMar:
    """A client for SanMar's web services, both SanMar's own and PromoStandards.

    Parameters
    ----------
    customer_number
        The SanMar customer number. SanMar's own services require it; PromoStandards
        services do not use it.
    username, password
        A SanMar.com login. Create one at https://www.sanmar.com/signup/webuser, then ask
        sanmarintegrations@sanmar.com to enable web service access. EDEV logins are separate
        from production ones, and neither works on SanMar's SFTP server.
    environment
        Production, or SanMar's EDEV test environment.
    timeout
        Seconds to wait for a WSDL to load or a call to finish.
    transport
        A zeep :class:`~zeep.Transport` to use instead of the default one, for example to
        cache WSDLs or go through a proxy. It is used as-is, so ``timeout`` does not apply.
    """

    def __init__(  # noqa: PLR0913 - every argument is a distinct connection setting
        self,
        customer_number: int,
        username: str,
        password: str,
        *,
        environment: Environment = Environment.PRODUCTION,
        timeout: float = 30.0,
        transport: Transport | None = None,
    ) -> None:
        """Prepare a client; nothing is loaded until the first call."""
        self._credentials = Credentials(customer_number, username, password)
        self._soap = SoapClient(environment, timeout=timeout, transport=transport)

    @property
    def environment(self) -> Environment:
        """The environment this client calls."""
        return self._soap.environment
