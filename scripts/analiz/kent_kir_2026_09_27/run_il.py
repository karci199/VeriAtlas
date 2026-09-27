"""Run the whole urban/rural/semt/age pipeline for one province.

usage: run_il.py 16 [--skip-buildings] [--draws 200]
env:   KK_YIL (base year, default 2024), KK_DIR (output dir, default C:/veri-ham/analiz/kent_kir/<plate>)

Steps, each a script in this folder taking the plate as first argument:
  kent_il        building clusters -> kent_<p>_mahalle.csv (needs the Microsoft tiles; ~5 min)
  birlestir      five signals -> kent_<p>_son.csv
  ikili          binary urban/rural, district table
  semt           semt of every neighbourhood + semt_<p>.csv
  semt_profil    population, children, mean age, education per semt
  secim_kentkir  election results by class / semt / district
  secmen_oran, secmen_iliski   registered voters vs 18+ residents
  tarihsel       census 1965-2000 + ADNKS 2007-2012 urban/rural series
  yas_mc         median age with Monte Carlo (kent/kır, semt, mahalle)
"""

import subprocess, sys, time
from pathlib import Path

plate = sys.argv[1]
skip_b = "--skip-buildings" in sys.argv
draws = sys.argv[sys.argv.index("--draws") + 1] if "--draws" in sys.argv else "200"
HERE = Path(__file__).parent
PY = "C:/veri/.venv/Scripts/python.exe"
steps = ([] if skip_b else [("kent_il", [])]) + [("birlestir", []), ("ikili", []), ("semt", []), ("semt_profil", []), ("secim_kentkir", []),
                                                 ("secmen_oran", []), ("secmen_iliski", []), ("tarihsel", []), ("secim_tek_parti", []), ("yas_mc", [draws])]
t0 = time.time()
for name, extra in steps:
    t1 = time.time()
    r = subprocess.run([PY, str(HERE / f"{name}.py"), plate, *extra], capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = "\n".join((r.stdout or "").strip().splitlines()[-3:])
    print(f"[{name}] {time.time() - t1:.0f} sn | {tail}", flush=True)
    if r.returncode:
        print(r.stderr[-3000:]); sys.exit(f"{name} başarısız")
print("il", plate, "bitti", round(time.time() - t0), "sn")
