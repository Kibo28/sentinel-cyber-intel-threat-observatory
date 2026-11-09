from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from . import store
from .public_feed import checked_url
from .sources import EXTERNAL, FEEDS

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
WebURL = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class FeedConfig(BaseModel):
    name: Name
    url: WebURL
    category: Literal["auto", "Cyberattacks", "Vulnerabilities", "Data Breaches", "Ransomware", "Technology"] = "auto"
    source_type: Literal["news", "research", "official"] = "news"
    enabled: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, url):
        checked_url(url)
        return url


class LinkConfig(BaseModel):
    name: Name
    url: WebURL
    note: str = Field(default="", max_length=400)

    @field_validator("url")
    @classmethod
    def validate_url(cls, url):
        checked_url(url, public=False)
        return url


class SourceConfig(BaseModel):
    revision: int = Field(default=0, ge=0, strict=True)
    feeds: list[FeedConfig] = Field(max_length=50)
    external: list[LinkConfig] = Field(max_length=50)
    kev_enabled: bool = True
    epss_enabled: bool = True

    @model_validator(mode="after")
    def unique_names(self):
        names = {"cisa kev", "first epss"}
        for source in [*self.feeds, *self.external]:
            key = source.name.casefold()
            if key in names:
                raise ValueError(f"Source name already in use: {source.name}")
            names.add(key)
        return self


class CollectionSettings(BaseModel):
    revision: int = Field(default=0, ge=0, strict=True)
    interval_minutes: int | None = Field(default=None, ge=1, le=1440, strict=True)
    email_enabled: bool = False


def source_config():
    value, revision = store.get_setting("sources")
    if value is None:
        value = {
            "feeds": [FeedConfig(name=s.name, url=s.url, category=s.category, source_type=s.source_type) for s in FEEDS],
            "external": [s for s in EXTERNAL if s["name"] != "FIRST EPSS"],
        }
    return SourceConfig(revision=revision, **value)


def collection_settings():
    value, revision = store.get_setting("collection")
    return CollectionSettings(revision=revision, **(value or {}))
