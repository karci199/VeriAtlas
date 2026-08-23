"""Unpack province boundary packs ferried out of the browser tab.

The Endeksa tab gzips each province's neighbourhood boundaries and base64-encodes them;
the tool result lands as a JSON file under the session's tool-results directory with
`{"pack": <plate>, "b64": "..."}` in its text. This finds every such file, writes
raw/endeksa/geo/TR-<plate>.json, and runs the export for it.

Run:  uv run python scripts/unpack_endeksa_packs.py <tool-results-dir>
"""

import base64
import gzip
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "endeksa" / "geo"


def main(results_dir: str) -> None:
    decoder = json.JSONDecoder()
    done = []
    for path in sorted(Path(results_dir).iterdir()):
        try:
            arr = json.loads(path.read_text(encoding="utf-8"))
            text = arr[0]["text"]
            start = min(i for i in (text.find("{"), text.find("[")) if i >= 0)
            obj, _ = decoder.raw_decode(text[start:])
        except (ValueError, KeyError, IndexError, TypeError):
            continue
        for pack in obj if isinstance(obj, list) else [obj]:
            if not (isinstance(pack, dict) and "pack" in pack and "b64" in pack):
                continue
            plate = int(pack["pack"])
            out = RAW / f"TR-{plate:02d}.json"
            if out.exists():
                continue
            data = gzip.decompress(base64.b64decode(pack["b64"].rstrip()))
            geo = json.loads(data)
            RAW.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            print(
                f"TR-{plate:02d}: {len(geo)} counties, {sum(len(v['features']) for v in geo.values())} polygons"
            )
            done.append(plate)
    for plate in done:
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "export_endeksa_geo.py"),
                f"TR-{plate:02d}",
            ],
            check=True,
        )


if __name__ == "__main__":
    main(sys.argv[1])
