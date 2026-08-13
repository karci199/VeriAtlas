"""Source adapters. One module per source; the contract lives in `base`."""

from .base import Adapter, Manifest, history, ingest
from .tuik_tfr import TuikTfr

#: Everything that can be ingested, by name. `scripts/load.py` runs these.
ADAPTERS = {"tuik_tfr": TuikTfr}

__all__ = ["ADAPTERS", "Adapter", "Manifest", "TuikTfr", "history", "ingest"]
