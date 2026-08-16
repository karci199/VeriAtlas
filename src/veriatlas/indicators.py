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

#: The ways the explorer knows how to draw a series. An indicator may only offer these;
#: a name outside the set is a typo that would otherwise show up as a tab that draws
#: nothing (decision K10).
VIEWS = ("table", "map", "line", "bar", "pyramid")


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
    #: Whether values in this unit may be summed across a breakdown. Persons add up;
    #: a rate does not. The screen only offers "Tümü (topla)" where this is true.
    additive: bool
    #: Whether dividing by the area's population says anything. People and the events
    #: people have — a birth, a death, a marriage — give a crude rate that demographers
    #: read every day. Households, buildings and dwellings do not: they are counted in
    #: units that are not persons, so "hane ÷ kişi" is a ratio of two different things.
    #:
    #: Additivity does not answer this. A household count adds up perfectly and is still
    #: the wrong numerator, which is how the screen came to offer "İl nüfusunun %'si" for
    #: hanehalkı tipleri — a reading that happens to be true for one of the four values
    #: (a one-person household holds exactly one person) and meaningless for the other
    #: three. One right answer beside three wrong ones is worse than no answer.
    per_capita: bool


@dataclass(frozen=True)
class Dimension:
    """A breakdown key, and the Turkish for the values it stores.

    `values` may be empty: an age band reads the same in every language, a sex code does
    not.
    """

    dim_id: str
    label_tr: str
    label_en: str
    values_tr: dict[str, str]


@dataclass(frozen=True)
class Grouping:
    """A coarser reading of one breakdown: which values are summed into which group.

    Declared rather than computed so that "0-14 / 15-64 / 65+" is a recorded decision in
    one line instead of an indicator of its own or a branch in the page (K12's argument,
    applied across a breakdown instead of across time).
    """

    grouping_id: str
    label_tr: str
    label_en: str
    dim: str
    #: Group name -> the dimension values that add up into it.
    covers: dict[str, tuple[str, ...]]
    #: True when the grouping's boundary falls inside the bands a level publishes, so it
    #: can only be built from the finer rows underneath them. "18+" at province level is
    #: the case: the export is banded by fives and eighteen sits inside 15-19, but the
    #: warehouse keeps single years and the sum off those is exact.
    needs_fine: bool
    note_tr: str


@dataclass(frozen=True)
class Comparison:
    """Two values of one breakdown read against each other: a gap, or a ratio."""

    comparison_id: str
    label_tr: str
    label_en: str
    dim: str
    plus: str
    minus: str
    #: "difference" or "ratio".
    how: str
    #: `None` where the result keeps the indicator's unit — a difference of persons is
    #: persons. A ratio has a unit of its own.
    unit: Unit | None
    note_tr: str


@dataclass(frozen=True)
class Ratio:
    """One set of a breakdown's values over another, as a percentage.

    Where a comparison takes two values, this takes two *sets* — which is what the total
    dependency ratio needs, being (0-14 + 65+) over 15-64. Named through a grouping, so
    the bands each group covers are resolved per level rather than written out once and
    being wrong at the level whose tail runs further.
    """

    ratio_id: str
    label_tr: str
    label_en: str
    dim: str
    grouping: str
    over: tuple[str, ...]
    under: tuple[str, ...]
    unit: Unit
    note_tr: str


@dataclass(frozen=True)
class Base:
    """A denominator taken from a slice of another indicator.

    The screen can already read a count against the area's whole population, which is how
    the crude rates are drawn without downloading them (K12). The demographic rates worth
    having are not over everyone though: a fertility rate is over the women who could have
    the children. Over the whole population instead, the number moves whenever the age
    structure moves — which is the thing the rate exists to hold still.

    `applies_to` is a list rather than a rule about units. Births over women 15-49 is the
    general fertility rate; deaths over those same women is not a statistic, and offering
    it because both happen to be counts would be offering an answer to no question.
    """

    base_id: str
    label_tr: str
    label_en: str
    #: The indicator the denominator is summed from, and the slice of it.
    indicator: str
    dims: dict[str, str]
    grouping: str | None
    values: tuple[str, ...]
    #: What the ratio is multiplied by: 1000 for a per-mille rate, 100 for a percentage.
    factor: int
    unit: Unit
    applies_to: tuple[str, ...]
    note_tr: str


@dataclass(frozen=True)
class Derivation:
    """A series computed from a measurement: an index, a rate of change.

    It is not stored — the screen computes it — but it is declared here for the same
    reason indicators are: the unit it produces and the honesty of the result are
    decisions, not implementation details (decision K12).
    """

    derivation_id: str
    label_tr: str
    label_en: str
    #: `None` where the result keeps the indicator's own unit — a difference of persons
    #: is persons, an average of a rate is a rate.
    unit: Unit | None
    quality: str
    needs_span: bool
    note_tr: str


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
    views: tuple[str, ...]
    definition_tr: str


@dataclass(frozen=True)
class Dictionary:
    """The whole file, cross-references already resolved."""

    topics: dict[str, Topic]
    units: dict[str, Unit]
    dimensions: dict[str, Dimension]
    groupings: dict[str, Grouping]
    comparisons: dict[str, Comparison]
    ratios: dict[str, Ratio]
    bases: dict[str, Base]
    derivations: dict[str, Derivation]
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
        key: Unit(
            key,
            body["label_tr"],
            body["label_en"],
            body["decimals"],
            body.get("additive", False),
            body.get("per_capita", False),
        )
        for key, body in raw.get("unit", {}).items()
    }

    dimensions = {
        key: Dimension(
            key,
            body["label_tr"],
            body["label_en"],
            dict(body.get("values", {})),
        )
        for key, body in raw.get("dim", {}).items()
    }

    groupings: dict[str, Grouping] = {}
    for key, body in raw.get("grouping", {}).items():
        if body["dim"] not in dimensions:
            raise KeyError("grouping '" + key + "' names unknown dim: " + body["dim"])
        covers = {name: tuple(values) for name, values in body["covers"].items()}
        # A value in two groups would be counted twice the moment anything sums across
        # the grouping, and the total would quietly stop being the total.
        flat = [value for values in covers.values() for value in values]
        if len(flat) != len(set(flat)):
            raise ValueError("grouping '" + key + "' puts a value in two groups")
        groupings[key] = Grouping(
            grouping_id=key,
            label_tr=body["label_tr"],
            label_en=body["label_en"],
            dim=body["dim"],
            covers=covers,
            needs_fine=bool(body.get("needs_fine", False)),
            note_tr=body.get("note_tr", "").strip(),
        )

    comparisons: dict[str, Comparison] = {}
    for key, body in raw.get("comparison", {}).items():
        if body["dim"] not in dimensions:
            raise KeyError("comparison '" + key + "' names unknown dim: " + body["dim"])
        if body["how"] not in ("difference", "ratio"):
            raise ValueError("comparison '" + key + "' has unknown how: " + body["how"])
        if body["unit"] and body["unit"] not in units:
            raise KeyError(
                "comparison '" + key + "' names unknown unit: " + body["unit"]
            )
        comparisons[key] = Comparison(
            comparison_id=key,
            label_tr=body["label_tr"],
            label_en=body["label_en"],
            dim=body["dim"],
            plus=body["plus"],
            minus=body["minus"],
            how=body["how"],
            unit=units[body["unit"]] if body["unit"] else None,
            note_tr=body.get("note_tr", "").strip(),
        )

    ratios: dict[str, Ratio] = {}
    for key, body in raw.get("ratio", {}).items():
        if body["dim"] not in dimensions:
            raise KeyError("ratio '" + key + "' names unknown dim: " + body["dim"])
        if body["grouping"] not in groupings:
            raise KeyError(
                "ratio '" + key + "' names unknown grouping: " + body["grouping"]
            )
        grouping = groupings[body["grouping"]]
        if grouping.dim != body["dim"]:
            raise ValueError(
                "ratio '" + key + "' uses a grouping of another dim: " + grouping.dim
            )
        # A group name that is not in the grouping would contribute nothing and the ratio
        # would come out of a smaller numerator than it claims — silent, and wrong in a
        # plausible direction.
        named = set(body["over"]) | set(body["under"])
        missing = named - set(grouping.covers)
        if missing:
            raise KeyError(
                "ratio '"
                + key
                + "' names groups the grouping does not have: "
                + ", ".join(sorted(missing))
            )
        if set(body["over"]) & set(body["under"]):
            raise ValueError("ratio '" + key + "' has a group on both sides")
        if body["unit"] not in units:
            raise KeyError("ratio '" + key + "' names unknown unit: " + body["unit"])
        ratios[key] = Ratio(
            ratio_id=key,
            label_tr=body["label_tr"],
            label_en=body["label_en"],
            dim=body["dim"],
            grouping=body["grouping"],
            over=tuple(body["over"]),
            under=tuple(body["under"]),
            unit=units[body["unit"]],
            note_tr=body.get("note_tr", "").strip(),
        )

    bases: dict[str, Base] = {}
    for key, body in raw.get("base", {}).items():
        if body["unit"] not in units:
            raise KeyError("base '" + key + "' names unknown unit: " + body["unit"])
        grouping = body.get("grouping")
        if grouping and grouping not in groupings:
            raise KeyError("base '" + key + "' names unknown grouping: " + grouping)
        if grouping:
            missing = set(body.get("values", [])) - set(groupings[grouping].covers)
            if missing:
                raise KeyError(
                    "base '"
                    + key
                    + "' names groups the grouping does not have: "
                    + ", ".join(sorted(missing))
                )
        # The dims are every key that is not one of the fields above: `sex = "female"`
        # says the denominator is women, and a base over everyone names none of them.
        reserved = {
            "label_tr",
            "label_en",
            "indicator",
            "factor",
            "unit",
            "applies_to",
            "grouping",
            "values",
            "note_tr",
        }
        bases[key] = Base(
            base_id=key,
            label_tr=body["label_tr"],
            label_en=body["label_en"],
            indicator=body["indicator"],
            dims={k: v for k, v in body.items() if k not in reserved},
            grouping=grouping,
            values=tuple(body.get("values", ())),
            factor=int(body["factor"]),
            unit=units[body["unit"]],
            applies_to=tuple(body["applies_to"]),
            note_tr=body.get("note_tr", "").strip(),
        )

    derivations: dict[str, Derivation] = {}
    for key, body in raw.get("derivation", {}).items():
        # An empty unit means "whatever the indicator is in". A difference of two counts
        # is a count and a moving average of a rate is a rate; naming a unit for those
        # would be inventing one. The page reads `None` as "keep the indicator's".
        if body["unit"] and body["unit"] not in units:
            raise KeyError(
                "derivation '" + key + "' names unknown unit: " + body["unit"]
            )
        derivations[key] = Derivation(
            derivation_id=key,
            label_tr=body["label_tr"],
            label_en=body["label_en"],
            unit=units[body["unit"]] if body["unit"] else None,
            quality=body.get("quality", "estimated"),
            needs_span=bool(body.get("needs_span", False)),
            note_tr=body.get("note_tr", "").strip(),
        )

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

        undeclared = [d for d in body.get("dims", ()) if d not in dimensions]
        if undeclared:
            raise KeyError(
                "indicator '"
                + key
                + "' names undeclared dimension(s): "
                + ", ".join(undeclared)
            )

        views = tuple(body.get("views", ("table", "line")))
        unknown = [v for v in views if v not in VIEWS]
        if unknown:
            raise KeyError(
                "indicator '"
                + key
                + "' names unknown view(s): "
                + ", ".join(unknown)
                + " (known: "
                + ", ".join(VIEWS)
                + ")"
            )

        indicators[key] = Indicator(
            indicator_id=key,
            label_tr=body["label_tr"],
            label_en=body["label_en"],
            topic=topics[body["topic"]],
            unit=units[body["unit"]],
            frequency=body["frequency"],
            dims=tuple(body.get("dims", ())),
            views=views,
            definition_tr=body.get("definition_tr", "").strip(),
        )

    return Dictionary(
        topics=topics,
        units=units,
        dimensions=dimensions,
        groupings=groupings,
        comparisons=comparisons,
        ratios=ratios,
        bases=bases,
        derivations=derivations,
        indicators=indicators,
    )


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
