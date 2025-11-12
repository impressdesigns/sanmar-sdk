"""A module for wrapping SanMar's SOAP API."""

from typing import TYPE_CHECKING

from suds.client import Client

if TYPE_CHECKING:
    from suds.sudsobject import Object as SudsObject


class SanMar:
    """A client for SanMar's SOAP API."""

    def __init__(
        self,
        username: str,
        password: str,
        version: str = "1.0.0",
        packing_slip_service_wsdl_url: str = "https://ws.sanmar.com:8080/SanMarWebService/webservices/PackingSlipService?wsdl",
    ) -> None:
        """Initialize the SanMar client."""
        self.username = username
        self.password = password
        self.version = version
        self.packing_slip_client = Client(packing_slip_service_wsdl_url)

    def get_packing_slip(self, license_plate: str) -> SudsObject:
        """Retrieve a packing slip by its license plate ID."""
        return self.packing_slip_client.service.GetPackingSlip(
            wsVersion=self.version,
            UserId=self.username,
            Password=self.password,
            PackingSlipId=license_plate,
        )
