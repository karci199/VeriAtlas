"""Indicator dictionary: what an id in the fact table means.

The fact table stores ids only. Everything a reader sees — the Turkish name, the unit,
how many decimals to print — is looked up here, so a label change never touches stored
data (decision K1).

The dictionary is also the guard on the flexible `dims` field: an indicator declares
which breakdown keys it may carry, and `check_dims` refuses the rest. Without that,
one typo (`yas` instead of `age`) would quietly become a second, parallel series.

Loading validates the whole file: a topic or unit that no indicator can resolve is a
mistake worth hearing about at import time, not when a chart comes out empty.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DICTIONARY_PATH = Path(__file__).parent / "data" / "indicators.toml"


@dataclass(frozen=True)
class Topic:
    """A branch of the indicator tree."""

    topic_id: str
    label_tr: str
    label_en: str
    order: int


@dataclass(frozen=True)
class Unit:
    """A unit of measure, with the precision it should be printed at."""

    unit_id: str
    label_tr: str
    label_en: str
    decimals: int


@dataclass(frozen=True)
class Indicator:
    """One measurable quantity."""

    indicator_id: str
    label_tr: str
    label_en: str
    topic: Topic
    unit: Unit
    frequency: str
    dims: tuple[str, ...]
    definition_tr: str


@dataclass(frozen=True)
class Dictionary:
    """The whole file, cross-references already resolved."""

    topics: dict[str, Topic]
    units: dict[str, Unit]
    indicators: dict[str, Indicator]

    def tree(self) -> list[tuple[Topic, list[Indicator]]]:
        """Topics in display order, each with its indicators sorted by Turkish label."""
        ordered = sorted(self.topics.values(), key=lambda t: (t.order, t.topic_id))
        return [
            (
                topic,
                sorted(
                    (i for i in self.indicators.values() if i.topic is topic),
                    key=lambda i: i.label_tr,
                ),
            )
            for topic in ordered
        ]


@lru_cache(maxsize=1)
def load() -> Dictionary:
    """Read and validate the dictionary. Cached; the file does not change at runtime."""
    raw = tomllib.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))

    topics = {
        key: Topic(key, body["label_tr"], body["label_en"], body["order"])
        for key, body in raw.get("topic", {}).items()
    }
    units = {
        key: Unit(key, body["label_tr"], body["label_en"], body["decimals"])
        for key, body in raw.get("unit", {}).items()
    }

    indicators: dict[str, Indicator] = {}
    for key, body in raw.get("indicator", {}).items():
        if body["topic"] not in topics:
            raise KeyError(
                "indicator '" + key + "' names unknown topic: " + body["topic"]
            )
        if body["unit"] not in units:
            raise KeyError(
                "indicator '" + key + "' names unknown unit: " + body["unit"]
            )

        indicators[key] = Indicator(
            indicator_id=key,
            label_tr=body["label_tr"],
            label_en=body["label_en"],
            topic=topics[body["topic"]],
            unit=units[body["unit"]],
            frequency=body["frequency"],
            dims=tuple(body.get("dims", ())),
            definition_tr=body.get("definition_tr", "").strip(),
        )

    return Dictionary(topics=topics, units=units, indicators=indicators)


def get(indicator_id: str) -> Indicator:
    """Look up one indicator, raising if it is not declared."""
    try:
        return load().indicators[indicator_id]
    except KeyError:
        raise KeyError(
            "undeclared indicator '"
            + indicator_id
            + "'; add it to indicators.toml before loading its data"
        ) from None


def check_dims(indicator_id: str, keys: set[str]) -> None:
    """Refuse breakdown keys the indicator has not declared."""
    allowed = set(get(indicator_id).dims)
    unexpected = keys - allowed
    if unexpected:
        raise KeyError(
            "indicator '"
            + indicator_id
            + "' does not declare dimension(s): "
            + ", ".join(sorted(unexpected))
            + (
                " (declared: " + ", ".join(sorted(allowed)) + ")"
                if allowed
                else " (declares none)"
            )
        )
