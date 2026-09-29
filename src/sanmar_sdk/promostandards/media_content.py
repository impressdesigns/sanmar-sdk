"""SanMar's PromoStandards Media Content service, version 1.1.0.

Lists the images and documents for a style or one part of it. SanMar serves images and
documents only, not audio or video, and does not implement ``getMediaDateModified``.
SanMar recommends asking for whole styles, which returns every color's images at once.
"""

from datetime import datetime
from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING

from pydantic import AliasPath, Field

from sanmar_sdk._soap import PROMOSTANDARDS_MEDIA_CONTENT
from sanmar_sdk.base import Record

from ._common import PromoStandardsService, check

if TYPE_CHECKING:
    from ._wire import GetMediaContentRequest


class MediaType(StrEnum):
    """The kinds of media SanMar serves."""

    IMAGE = "Image"
    DOCUMENT = "Document"


class ClassType(IntEnum):
    """The image classes SanMar's guide lists. PromoStandards defines more."""

    SWATCH = 1004
    PRIMARY = 1006
    FRONT = 1007
    REAR = 1008
    HIGH_RESOLUTION = 2001


class MediaClass(Record):
    """A classification of a piece of media, such as ``Front`` or ``Swatch``."""

    id: int = Field(validation_alias="classTypeId")
    name: str = Field(validation_alias="classTypeName")


class MediaItem(Record):
    """One image or document."""

    product_id: str = Field(validation_alias="productId")
    part_id: str | None = Field(default=None, validation_alias="partId")
    url: str
    media_type: str = Field(validation_alias="mediaType")
    classes: list[MediaClass] = Field(default_factory=list, validation_alias=AliasPath("ClassTypeArray", "ClassType"))
    color: str | None = None
    """The color shown, as SanMar names it on the image."""
    description: str | None = None
    single_part: bool = Field(default=False, validation_alias="singlePart")
    """Whether the media shows exactly the one part it is listed under."""
    file_size: Decimal | None = Field(default=None, validation_alias="fileSize")
    width: Decimal | None = None
    height: Decimal | None = None
    dpi: int | None = None
    changed: datetime | None = Field(default=None, validation_alias="changeTimeStamp")


class MediaContentService(PromoStandardsService):
    """SanMar's PromoStandards Media Content service."""

    endpoint = PROMOSTANDARDS_MEDIA_CONTENT
    version = "1.1.0"

    def get(
        self,
        product_id: str,
        *,
        media_type: MediaType = MediaType.IMAGE,
        part_id: str | None = None,
        class_type: ClassType | int | None = None,
    ) -> list[MediaItem]:
        """List a style's images or documents, optionally for one part or one class."""
        request: GetMediaContentRequest = {"mediaType": MediaType(media_type).value, "productId": product_id}
        if part_id is not None:
            request["partId"] = part_id
        if class_type is not None:
            request["classType"] = int(class_type)
        result = self._call("getMediaContent", request)
        if check(result, allow_empty=True):
            return []
        array = result.get("MediaContentArray") or {}
        return [MediaItem.model_validate(item) for item in array.get("MediaContent") or []]
