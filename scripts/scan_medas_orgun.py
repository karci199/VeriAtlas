import pathlib
import runpy
import sys

TOPIC = "Örgün Eğitim İstatistikleri"

if __name__ == "__main__":
    here = pathlib.Path(__file__).resolve().parent
    sys.argv = ["scan_medas_topic.py", TOPIC, *sys.argv[1:]]
    runpy.run_path(str(here / "scan_medas_topic.py"), run_name="__main__")
