#!/bin/bash
# KGM il yol envanteri PDF'lerinin Wayback kopyalarini indirir; arsiv kapaliysa bekleyip yeniden dener.
cd C:/veri-ham/kgm/wayback
base="kgm.gov.tr/SiteCollectionDocuments/KGMdocuments/Istatistikler/DevletIlYolEnvanter"
for f in IllereGoreDevletVeIlYollari IllereGoreDevletYollari IllereGoreIlYollari YillaraGoreDevletYollari YillaraGoreIlYoluUzunlugu SatihYolAgiUzunlugu; do
  for try in 1 2 3 4 5 6; do
    curl -s --max-time 90 "https://web.archive.org/cdx/search/cdx?url=$base/$f.pdf&output=txt&fl=timestamp,digest,statuscode&collapse=digest&filter=statuscode:200" > cdx_$f.txt
    if head -c 1 cdx_$f.txt | grep -q '[0-9]'; then break; fi
    rm -f cdx_$f.txt; sleep 60
  done
  [ -f cdx_$f.txt ] || { echo "CDX alinamadi $f"; continue; }
  while read ts dg st; do
    out="${f}_${ts}.pdf"
    [ -s "$out" ] && head -c 4 "$out" | grep -q '%PDF' && continue
    for try in 1 2 3 4 5 6; do
      curl -sL --max-time 120 -o "$out" "https://web.archive.org/web/${ts}id_/https://www.$base/$f.pdf"
      head -c 4 "$out" | grep -q '%PDF' && { echo "ok $out"; break; }
      sleep 45
    done
    head -c 4 "$out" | grep -q '%PDF' || { echo "BASARISIZ $out"; rm -f "$out"; }
  done < cdx_$f.txt
done
echo BITTI
