#!/bin/bash
# Wayback Machine copies of KGM files that the site overwrites every year.
# Usage: fetch_kgm_wayback.sh [path under kgm.gov.tr/SiteCollectionDocuments/KGMdocuments/ ...]
# Every distinct version (by digest) is saved as <name>_<timestamp>.<ext> in raw/kgm/wayback;
# when the archive answers "temporarily offline" the request waits and retries.
cd C:/veri-ham/kgm/wayback
base="kgm.gov.tr/SiteCollectionDocuments/KGMdocuments"
files=("$@")
[ ${#files[@]} -eq 0 ] && files=(Istatistikler/DevletIlYolEnvanter/IllereGoreDevletVeIlYollari.pdf)
for path in "${files[@]}"; do
  name=$(basename "$path"); stem="${name%.*}"; ext="${name##*.}"
  for try in 1 2 3 4 5 6; do
    curl -s --max-time 90 "https://web.archive.org/cdx/search/cdx?url=$base/$path&output=txt&fl=timestamp,digest&collapse=digest&filter=statuscode:200" > "cdx_$stem.txt"
    head -c 1 "cdx_$stem.txt" | grep -q '[0-9]' && break
    rm -f "cdx_$stem.txt"; sleep 60
  done
  [ -f "cdx_$stem.txt" ] || { echo "CDX alinamadi $path"; continue; }
  while read ts dg; do
    out="${stem}_${ts}.${ext}"
    [ -s "$out" ] && ! head -c 200 "$out" | grep -qi '<html' && continue
    for try in 1 2 3 4 5 6; do
      curl -sL --max-time 180 -o "$out" "https://web.archive.org/web/${ts}id_/https://www.$base/$path"
      [ -s "$out" ] && ! head -c 200 "$out" | grep -qi '<html' && { echo "ok $out"; break; }
      sleep 45
    done
    [ -s "$out" ] && ! head -c 200 "$out" | grep -qi '<html' || { echo "BASARISIZ $out"; rm -f "$out"; }
  done < "cdx_$stem.txt"
done
echo BITTI
