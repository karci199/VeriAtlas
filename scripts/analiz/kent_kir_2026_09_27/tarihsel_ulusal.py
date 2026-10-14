"""National run of the first half of tarihsel.py (typed settlements 1965-2000 and 2007-2012).

usage: tarihsel_ulusal.py <plate>   (writes tarihsel_<plate>.csv under KK_DIR)
The second half of tarihsel.py (carry-back of today's building class) needs the per-province
kent_<plate>_son.csv and is not run here.
"""
import sys
from pathlib import Path

src = (Path(__file__).parent / "tarihsel.py").read_text(encoding="utf-8")
cut = src.index("# TÜİK's own split")
sys.argv = [str(Path(__file__).parent / "tarihsel.py"), sys.argv[1]]
exec(compile(src[:cut], "tarihsel.py", "exec"), {"__name__": "__main__", "__file__": str(Path(__file__).parent / "tarihsel.py")})
