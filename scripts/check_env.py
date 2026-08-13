"""Anahtarin dogru yerde ve okunabilir oldugunu dogrular.

Calistirma:  uv run python scripts/check_env.py
"""

import sys

sys.path.insert(0, "src")

from veri.config import ROOT, settings  # noqa: E402

key = settings.evds_api_key

print(f".env yolu   : {ROOT / '.env'}")
print(f"dosya var mi: {(ROOT / '.env').exists()}")

if not key:
    print("\nSONUC: EVDS_API_KEY bos. .env dosyasini acip anahtari yapistirin.")
elif key == "BURAYA_YAPISTIR":
    print("\nSONUC: Yer tutucu hala duruyor. BURAYA_YAPISTIR yerine anahtari yazin.")
else:
    print(f"anahtar     : okundu, {len(key)} karakter (icerik gosterilmiyor)")
    print("\nSONUC: Anahtar okundu. Hazir.")
