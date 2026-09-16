"""Mobile churn rates by operator, read off the chart image of the BTK market report.

"Şekil 4-14 Mobil İşletmecilerin Abone Kayıp Oranları (Churn Rate), %" prints a data table
under the chart, monthly for the last twelve months — but the whole figure is an image, so
the numbers are not in the text layer. The page was rendered (`scripts/fetch_btk_pdfs.py`
keeps the PDFs; pypdfium2 at scale 4) and the table transcribed by eye.

So far only the 2026-Q1 report is transcribed: March 2025 … March 2026. Every first-quarter
report carries the previous twelve months, so reading one report a year would extend this
back to about 2016; the overlapping March would check the transcription.
"""

from __future__ import annotations

# (year, month) -> {operator: churn %}, as printed in the 2026-Q1 report
CHURN = {
    (2025, 3): {"tt_mobil": 2.2, "vodafone": 2.2, "turkcell": 1.9},
    (2025, 4): {"tt_mobil": 2.5, "vodafone": 2.3, "turkcell": 2.2},
    (2025, 5): {"tt_mobil": 2.5, "vodafone": 2.4, "turkcell": 2.3},
    (2025, 6): {"tt_mobil": 2.2, "vodafone": 2.3, "turkcell": 2.0},
    (2025, 7): {"tt_mobil": 2.1, "vodafone": 2.4, "turkcell": 2.5},
    (2025, 8): {"tt_mobil": 1.8, "vodafone": 2.3, "turkcell": 2.7},
    (2025, 9): {"tt_mobil": 1.8, "vodafone": 3.0, "turkcell": 2.5},
    (2025, 10): {"tt_mobil": 2.5, "vodafone": 2.4, "turkcell": 2.5},
    (2025, 11): {"tt_mobil": 2.4, "vodafone": 2.6, "turkcell": 2.2},
    (2025, 12): {"tt_mobil": 3.6, "vodafone": 3.6, "turkcell": 3.4},
    (2026, 1): {"tt_mobil": 2.1, "vodafone": 1.8, "turkcell": 1.6},
    (2026, 2): {"tt_mobil": 1.5, "vodafone": 1.6, "turkcell": 1.7},
    (2026, 3): {"tt_mobil": 1.5, "vodafone": 2.0, "turkcell": 1.6},
}
# The report's own sentence states March 2026 as TT Mobil 1,5, Vodafone 2,0, Turkcell 1,6 —
# it matches the last column, which checks the reading of the table.
SENTENCE_CHECK = {"tt_mobil": 1.5, "vodafone": 2.0, "turkcell": 1.6}

if __name__ == "__main__":
    assert CHURN[(2026, 3)] == SENTENCE_CHECK
    print(len(CHURN), "ay")
