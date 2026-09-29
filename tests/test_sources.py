"""Testing the record of which SanMar guides the SDK follows."""

from sanmar_sdk.sources import FTP_GUIDE, GUIDES, PURCHASE_ORDER_GUIDE, WEB_SERVICES_GUIDE


def test_guides_are_the_revisions_the_sdk_was_written_against() -> None:
    """Each guide names its exact revision, and links to that revision's PDF."""
    assert [(guide.version, guide.updated) for guide in GUIDES] == [
        ("24.6", "August 2026"),
        ("24.5", "August 2026"),
        ("23.6", "August 2026"),
    ]
    assert GUIDES == (WEB_SERVICES_GUIDE, PURCHASE_ORDER_GUIDE, FTP_GUIDE)
    assert all(guide.url.startswith("https://www.sanmar.com/") and guide.version in guide.url for guide in GUIDES)
