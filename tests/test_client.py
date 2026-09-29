"""Testing the client."""

from sanmar_sdk import Environment, SanMar


def test_client_defaults_to_production() -> None:
    """A client calls production unless told otherwise, and loads nothing up front."""
    assert SanMar(12345, "user", "secret").environment is Environment.PRODUCTION
    assert SanMar(12345, "user", "secret", environment=Environment.EDEV).environment is Environment.EDEV


def test_password_is_not_in_the_repr() -> None:
    """Credentials can be logged without leaking the password."""
    client = SanMar(12345, "user", "secret")
    assert "secret" not in repr(client._credentials)  # noqa: SLF001 - checking the private holder
