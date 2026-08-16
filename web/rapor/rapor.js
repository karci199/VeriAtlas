/* One report page for every area. The area comes from the hash — `#a=TR-34` — and its
 * payload from `public/rapor/<id>.json`, which `scripts/build_report_data.py` writes.
 *
 * The page draws; it does not compute. Every number here was worked out next to the fact
 * table, where the tests are. What lives in this file is the reading of those numbers:
 * which two series belong on one axis, where a band goes, what a sentence says when a
 * value crosses a line.
 */

const NS = "http://www.w3.org/2000/svg";

const sayi = new Intl.NumberFormat("tr-TR");
const ondalik = (n) => new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: n, maximumFractionDigits: n,
});
const sikisik = new Intl.NumberFormat("tr-TR", {notation: "compact", maximumFractionDigits: 1});
const bir = ondalik(1);
const iki = ondalik(2);

/** Signed, because a change of −1,4 and one of 1,4 are opposite findings and the reader
 *  should not have to look at a neighbouring column to tell which this is. */
function imzali(value, basamak = 1) {
    const yazi = ondalik(basamak).format(Math.abs(value));
    return (value > 0 ? "+" : value < 0 ? "−" : "") + yazi;
}

/** Signed percent, written the way Turkish writes it: the sign, then %, then the number.
 *  "%+22,0" is what you get by pasting a sign in front of a percent that already had one
 *  built into the template, and it reads as a typo. */
function imzaliYuzde(value, basamak = 1) {
    return (value >= 0 ? "+" : "−") + "%" + ondalik(basamak).format(Math.abs(value));
}

/** The ablative suffix a year takes: 2009'dan, 2007'den, 2013'ten, 2025'ten.
 *
 *  Turkish harmony runs on the *sound* of the number, not its digits, so the suffix is
 *  decided by the last spoken word — the units where there are any, the tens otherwise.
 *  Left to a single hard-coded "'den" the page says "2009'den", which is the kind of
 *  mistake a reader trusts the numbers less for. */
const BIRLER = ["", "den", "den", "ten", "ten", "ten", "dan", "den", "den", "dan"];
const ONLAR = ["dan", "dan", "den", "dan", "tan", "den", "tan", "ten", "den", "dan"];
function ablatif(yil) {
    const birler = yil % 10;
    return "'" + (birler ? BIRLER[birler] : ONLAR[Math.floor(yil / 10) % 10]);
}

function el(ad, ozellikler = {}, icerik) {
    const dugum = document.createElement(ad);
    for (const [k, v] of Object.entries(ozellikler)) {
        if (k === "class") dugum.className = v;
        else if (k.startsWith("data-")) dugum.setAttribute(k, v);
        else if (k in dugum) dugum[k] = v;
        else dugum.setAttribute(k, v);
    }
    if (icerik !== undefined) dugum.textContent = icerik;
    return dugum;
}

function svgEl(ad, ozellikler = {}, icerik) {
    const dugum = document.createElementNS(NS, ad);
    for (const [k, v] of Object.entries(ozellikler)) dugum.setAttribute(k, v);
    if (icerik !== undefined) dugum.textContent = icerik;
    return dugum;
}

/** A year-keyed object as sorted [year, value] pairs. JSON gives string keys; every axis
 *  in this file is numeric, and "10" sorting before "9" is the classic way an axis comes
 *  out shuffled while every value on it is right. */
function noktalar(nesne) {
    return Object.entries(nesne || {})
        .map(([y, v]) => [Number(y), v])
        .sort((a, b) => a[0] - b[0]);
}

const ilk = (nesne) => noktalar(nesne)[0];
const son = (nesne) => noktalar(nesne).at(-1);

// region Çizim

/** A line chart with a shared x of years, a hover crosshair, and toggleable series.
 *
 *  `seriler`: [{ad, alan, renk, kesik, eksen}] — `eksen: "sag"` puts a series on its own
 *  right-hand scale. Two scales on one frame is a thing to do sparingly and only where
 *  the pairing is the point (a count against the rate computed from it); the axis label
 *  says which side a series belongs to, so the reader is never guessing.
 */
function cizgiGrafik(kutu, {seriler, bantlar = [], birim = "", birimSag = "", sutun}) {
    const W = 900, H = 380, sol = 58, sag = seriler.some(s => s.eksen === "sag") ? 62 : 24;
    const ust = 28, alt = 42;
    const ic = {g: W - sol - sag, y: H - ust - alt};

    const yillar = [...new Set(seriler.flatMap(s => noktalar(s.veri).map(([y]) => y)))]
        .sort((a, b) => a - b);
    if (!yillar.length) return null;

    const acik = new Map(seriler.map(s => [s.ad, s.kapali !== true]));
    const xOf = (yil) => sol + (ic.g * (yil - yillar[0])) / Math.max(1, yillar.at(-1) - yillar[0]);

    function olcek(taraf) {
        const degerler = seriler
            .filter(s => (s.eksen === "sag") === (taraf === "sag") && acik.get(s.ad))
            .flatMap(s => noktalar(s.veri).map(([, v]) => v));
        if (!degerler.length) return null;
        let en = Math.min(...degerler), ust2 = Math.max(...degerler);
        const pay = (ust2 - en) * 0.12 || Math.abs(ust2) * 0.1 || 1;
        // A count axis starts at zero — the height of a bar is the number it stands for,
        // and a cropped baseline makes a 3% rise look like a doubling. A rate axis does
        // not: it is read as a level, and zero is nowhere near the data.
        if (taraf === "sag" || seriler.some(s => s.sifirdan && acik.get(s.ad))) en = Math.min(0, en);
        else en -= pay;
        return {en, ust: ust2 + pay};
    }

    const svg = svgEl("svg", {viewBox: `0 0 ${W} ${H}`, role: "img"});
    let imlec, noktaDugum = [], okuma;

    function yOf(deger, taraf) {
        const o = olcek(taraf) || {en: 0, ust: 1};
        return ust + ic.y - ((deger - o.en) / (o.ust - o.en)) * ic.y;
    }

    function ciz() {
        svg.textContent = "";

        for (const band of bantlar) {
            const x0 = xOf(band.baslangic) - 12, x1 = xOf(band.bitis) + 12;
            svg.append(svgEl("rect", {class: "band", x: x0, y: ust, width: x1 - x0, height: ic.y}));
            svg.append(svgEl("text", {
                class: "band-yazi", x: (x0 + x1) / 2, y: ust - 9, "text-anchor": "middle",
            }, band.ad));
        }

        const solOlcek = olcek("sol");
        if (solOlcek) {
            for (const deger of adimlar(solOlcek)) {
                const y = yOf(deger, "sol");
                svg.append(svgEl("line", {class: "kilavuz", x1: sol, x2: W - sag, y1: y, y2: y}));
                svg.append(svgEl("text", {
                    class: "eksen-yazi", x: sol - 10, y: y + 4, "text-anchor": "end",
                }, kisa(deger)));
            }
            svg.append(svgEl("text", {
                class: "eksen-yazi", x: sol - 10, y: ust - 10, "text-anchor": "end",
            }, birim));
        }
        const sagOlcek = olcek("sag");
        if (sagOlcek) {
            for (const deger of adimlar(sagOlcek)) {
                svg.append(svgEl("text", {
                    class: "eksen-yazi", x: W - sag + 10, y: yOf(deger, "sag") + 4,
                }, kisa(deger)));
            }
            svg.append(svgEl("text", {class: "eksen-yazi", x: W - sag + 10, y: ust - 10}, birimSag));
        }

        if (sutun && acik.get(sutun.ad)) {
            const veri = noktalar(sutun.veri);
            const en = Math.max(...veri.map(([, v]) => v));
            const genislik = Math.max(6, (ic.g / veri.length) * 0.62);
            for (const [yil, v] of veri) {
                const h = (v / en) * ic.y * 0.5;
                svg.append(svgEl("rect", {
                    class: "sutun", x: xOf(yil) - genislik / 2, width: genislik,
                    y: ust + ic.y - h, height: h, fill: sutun.renk, opacity: .22,
                }));
            }
        }

        for (const seri of seriler) {
            if (!acik.get(seri.ad)) continue;
            const veri = noktalar(seri.veri);
            if (!veri.length) continue;
            const d = veri.map(([yil, v], i) =>
                (i ? "L" : "M") + xOf(yil) + " " + yOf(v, seri.eksen)).join(" ");
            if (seri.dolgu) {
                const taban = ust + ic.y;
                svg.append(svgEl("path", {
                    class: "alan-dolgu", fill: seri.renk,
                    d: d + ` L${xOf(veri.at(-1)[0])} ${taban} L${xOf(veri[0][0])} ${taban} Z`,
                }));
            }
            svg.append(svgEl("path", {
                class: "seri", d, stroke: seri.renk,
                "stroke-dasharray": seri.kesik ? "5 4" : "none",
            }));
        }

        const her = yillar.length > 12 ? 2 : 1;
        yillar.forEach((yil, i) => {
            if (i % her) return;
            svg.append(svgEl("text", {
                class: "eksen-yazi", x: xOf(yil), y: H - 14, "text-anchor": "middle",
            }, yil));
        });

        imlec = svgEl("line", {class: "imlec", y1: ust, y2: ust + ic.y, opacity: 0});
        svg.append(imlec);
        noktaDugum = seriler.map(seri => {
            const nokta = svgEl("circle", {class: "nokta", r: 4.5, opacity: 0, fill: seri.renk});
            svg.append(nokta);
            return [seri, nokta];
        });
    }

    function adimlar({en, ust: tavan}) {
        const ham = (tavan - en) / 4;
        const buyukluk = 10 ** Math.floor(Math.log10(ham));
        const adim = [1, 2, 2.5, 5, 10].map(k => k * buyukluk).find(k => k >= ham) || ham;
        const cikti = [];
        for (let v = Math.ceil(en / adim) * adim; v <= tavan; v += adim) cikti.push(v);
        return cikti;
    }

    function kisa(v) {
        // Turkish's own compact notation — "1,2 Mn", "580 B" — rather than an English
        // suffix bolted onto a Turkish-formatted number.
        if (Math.abs(v) >= 1e4) return sikisik.format(v);
        if (Number.isInteger(v)) return sayi.format(v);
        return iki.format(v).replace(",00", "");
    }

    function oku(yil) {
        imlec.setAttribute("x1", xOf(yil));
        imlec.setAttribute("x2", xOf(yil));
        imlec.setAttribute("opacity", 1);
        const parcalar = [`<b>${yil}</b>`];
        for (const [seri, nokta] of noktaDugum) {
            const deger = seri.veri[yil];
            if (deger === undefined || !acik.get(seri.ad)) {
                nokta.setAttribute("opacity", 0);
                continue;
            }
            nokta.setAttribute("cx", xOf(yil));
            nokta.setAttribute("cy", yOf(deger, seri.eksen));
            nokta.setAttribute("opacity", 1);
            parcalar.push(`${seri.ad} <b>${seri.bicim ? seri.bicim(deger) : kisa(deger)}</b>`);
        }
        okuma.innerHTML = parcalar.join(" · ");
    }

    const ustSatir = el("div", {class: "grafik-ust"});
    for (const seri of [...seriler, ...(sutun ? [sutun] : [])]) {
        const dugme = el("button", {class: "anahtar", type: "button"});
        dugme.setAttribute("aria-pressed", String(acik.get(seri.ad) ?? seri.acik ?? false));
        if (sutun && seri === sutun) acik.set(seri.ad, seri.acik ?? false);
        const isaret = el("span", {class: "isaret" + (seri.kesik ? " kesik" : "") +
                                          (seri === sutun ? " kutu" : "")});
        isaret.style.background = seri.kesik ? "none" : seri.renk;
        isaret.style.color = seri.renk;
        dugme.append(isaret, document.createTextNode(seri.ad));
        dugme.addEventListener("click", () => {
            acik.set(seri.ad, !acik.get(seri.ad));
            dugme.setAttribute("aria-pressed", String(acik.get(seri.ad)));
            ciz();
            oku(yillar.at(-1));
        });
        ustSatir.append(dugme);
    }
    ustSatir.append(el("span", {class: "bosluk"}));
    okuma = el("span", {class: "okuma"});
    ustSatir.append(okuma);

    kutu.append(ustSatir, svg);
    ciz();
    oku(yillar.at(-1));

    svg.addEventListener("pointermove", (olay) => {
        const kutuOlcu = svg.getBoundingClientRect();
        const oranX = ((olay.clientX - kutuOlcu.left) / kutuOlcu.width) * W;
        const yil = yillar.reduce((en, y) =>
            Math.abs(xOf(y) - oranX) < Math.abs(xOf(en) - oranX) ? y : en, yillar[0]);
        oku(yil);
    });
    svg.addEventListener("pointerleave", () => oku(yillar.at(-1)));
    return svg;
}

/** The pyramid, with a year slider. One year at a time and the ghost of the first year
 *  behind it — the shape of the change is the finding, and two outlines say it where one
 *  bar chart per decade cannot. */
function piramit(kutu, {piramit: veri, bantlar}) {
    const yillar = Object.keys(veri).map(Number).sort((a, b) => a - b);
    const W = 900, H = 420, orta = W / 2, bosluk = 54, ust = 26, alt = 34;
    const satir = (H - ust - alt) / bantlar.length;
    const kanat = (W - bosluk) / 2 - 20;

    const en = Math.max(...yillar.flatMap(y =>
        bantlar.flatMap(b => [veri[y]?.[b]?.male || 0, veri[y]?.[b]?.female || 0])));
    const ilkYil = yillar[0];

    const svg = svgEl("svg", {viewBox: `0 0 ${W} ${H}`, role: "img"});
    const okuma = el("span", {class: "okuma"});

    function ciz(yil) {
        svg.textContent = "";
        const toplam = bantlar.reduce((t, b) =>
            t + (veri[yil]?.[b]?.male || 0) + (veri[yil]?.[b]?.female || 0), 0);

        bantlar.forEach((band, i) => {
            const y = ust + (bantlar.length - 1 - i) * satir;
            for (const [sex, yon, renk] of [["male", -1, "var(--kehribar)"],
                                            ["female", 1, "var(--karsi)"]]) {
                const simdi = veri[yil]?.[band]?.[sex] || 0;
                const once = veri[ilkYil]?.[band]?.[sex] || 0;
                const g = (simdi / en) * kanat;
                const g0 = (once / en) * kanat;
                const x = yon < 0 ? orta - bosluk / 2 - g : orta + bosluk / 2;
                const x0 = yon < 0 ? orta - bosluk / 2 - g0 : orta + bosluk / 2;
                if (yil !== ilkYil) {
                    svg.append(svgEl("rect", {
                        x: x0, y: y + 1.5, width: g0, height: satir - 3,
                        fill: "none", stroke: "var(--cizgi-acik)", "stroke-width": 1,
                    }));
                }
                svg.append(svgEl("rect", {
                    x, y: y + 1.5, width: g, height: satir - 3, fill: renk, opacity: .82,
                }));
            }
            svg.append(svgEl("text", {
                class: "eksen-yazi", x: orta, y: y + satir / 2 + 4, "text-anchor": "middle",
            }, band));
        });

        svg.append(svgEl("text", {class: "eksen-yazi", x: orta - bosluk / 2 - 6, y: ust - 10,
                                  "text-anchor": "end"}, "erkek"));
        svg.append(svgEl("text", {class: "eksen-yazi", x: orta + bosluk / 2 + 6, y: ust - 10},
                        "kadın"));
        okuma.innerHTML = `<b>${yil}</b> · ${sayi.format(toplam)} kişi` +
            (yil === ilkYil ? "" : ` · ince çerçeve ${ilkYil}`);
    }

    const ustSatir = el("div", {class: "grafik-ust"});
    ustSatir.append(el("span", {class: "okuma"}, "Yaş piramidi"), el("span", {class: "bosluk"}), okuma);

    const kaydirici = el("div", {class: "kaydirici"});
    const girdi = el("input", {type: "range", min: yillar[0], max: yillar.at(-1),
                               value: yillar.at(-1), step: 1});
    const cikti = el("output", {}, String(yillar.at(-1)));
    girdi.addEventListener("input", () => {
        cikti.textContent = girdi.value;
        ciz(Number(girdi.value));
    });
    kaydirici.append(el("span", {}, "Yıl"), girdi, cikti);

    kutu.append(ustSatir, svg, kaydirici);
    ciz(yillar.at(-1));
}

/** Two age profiles facing each other: who arrives, who leaves. The net line on top is
 *  the answer — a province can take in more people than it loses and still be emptying
 *  of twenty-year-olds. */
function gocProfili(kutu, bolum, yil) {
    const bantlar = bolum.bantlar;
    const gelen = bolum.gelen[yil] || {};
    const giden = bolum.giden[yil] || {};
    const W = 900, H = 320, sol = 46, sag = 20, ust = 26, alt = 40;
    const ic = {g: W - sol - sag, y: H - ust - alt};
    const en = Math.max(...bantlar.map(b => Math.max(gelen[b] || 0, giden[b] || 0)), 1);
    const genislik = (ic.g / bantlar.length) * 0.38;

    const svg = svgEl("svg", {viewBox: `0 0 ${W} ${H}`, role: "img"});
    const taban = ust + ic.y * 0.72;

    bantlar.forEach((band, i) => {
        const x = sol + (ic.g * (i + 0.5)) / bantlar.length;
        const hG = ((gelen[band] || 0) / en) * (taban - ust);
        const hK = ((giden[band] || 0) / en) * (H - alt - taban);
        svg.append(svgEl("rect", {x: x - genislik, y: taban - hG, width: genislik,
                                  height: hG, fill: "var(--iyi)", opacity: .8}));
        svg.append(svgEl("rect", {x, y: taban, width: genislik, height: hK,
                                  fill: "var(--uyari)", opacity: .8}));
        svg.append(svgEl("text", {class: "eksen-yazi", x, y: H - 12,
                                  "text-anchor": "middle"}, band));
    });
    svg.append(svgEl("line", {class: "taban", x1: sol, x2: W - sag, y1: taban, y2: taban}));
    svg.append(svgEl("text", {class: "eksen-yazi", x: sol, y: ust - 10}, "gelen ↑"));
    svg.append(svgEl("text", {class: "eksen-yazi", x: sol, y: H - alt + 24}, "giden ↓"));

    const ustSatir = el("div", {class: "grafik-ust"});
    ustSatir.append(el("span", {class: "okuma"}, `Göçün yaş profili · ${yil}`));
    kutu.append(ustSatir, svg);
}

// endregion

// region Sayfa

function kutuYap(ana) {
    const kutu = el("figure", {class: "grafik-kutu"});
    kutu.style.margin = "1.75rem 0 0";
    ana.append(kutu);
    return kutu;
}

function bolumYap(ana, no, baslik, giris) {
    const bolum = el("section", {id: "b" + no});
    bolum.append(el("p", {class: "bolum-no"}, no + " — " + baslik.etiket));
    bolum.append(el("h2", {}, baslik.yazi));
    if (giris) {
        const p = el("p", {class: "giris"});
        p.innerHTML = giris;
        bolum.append(p);
    }
    ana.append(bolum);
    return bolum;
}

function cikarim(bolum, html) {
    const kutu = el("div", {class: "cikarim"});
    kutu.innerHTML = html;
    bolum.append(kutu);
}

function ciz(veri) {
    const ana = document.getElementById("govde");
    ana.textContent = "";
    const b = veri.bolumler;
    const icindekiler = [];

    // region Başlık
    const basliklar = el("header");
    const kunye = el("p", {class: "kunye"});
    kunye.innerHTML = `Demografi raporu <span class="ayrac">/</span> ` +
        `${duzeyAdi(veri.alan.duzey)} <span class="ayrac">/</span> ` +
        `Kaynak: TÜİK ADNKS, çekim 2026-08`;
    basliklar.append(kunye);

    const yillar = b.nufus ? noktalar(b.nufus.toplam).map(([y]) => y) : [];
    const h1 = el("h1");
    h1.innerHTML = veri.alan.ad +
        (yillar.length ? ` <span class="yil">${yillar[0]} – ${yillar.at(-1)}</span>` : "");
    basliklar.append(h1);

    const kartlar = el("dl", {class: "kartlar"});
    if (b.nufus) {
        const [ilkYil, ilkDeger] = ilk(b.nufus.toplam);
        const [sonYil, sonDeger] = son(b.nufus.toplam);
        kartlar.append(kart("Nüfus", sayi.format(sonDeger),
            `${ilkYil}${ablatif(ilkYil)} beri ${imzaliYuzde((sonDeger / ilkDeger - 1) * 100)}`,
            sonDeger < ilkDeger));
        void sonYil;
    }
    if (b.yas) {
        const [, pay] = son(b.yas.paylar["65+"]);
        const [, ilkPay] = ilk(b.yas.paylar["65+"]);
        kartlar.append(kart("65 yaş üstü payı", "%" + iki.format(pay),
            imzali(pay - ilkPay, 2) + " puan"));
    }
    if (b.yasam?.["0"]) {
        const k = son(b.yasam["0"].female)?.[1];
        const e = son(b.yasam["0"].male)?.[1];
        if (k && e) {
            kartlar.append(kart("Doğuşta yaşam süresi", bir.format((k + e) / 2) + " yıl",
                `K ${bir.format(k)} · E ${bir.format(e)}`));
        }
    }
    if (b.dogurganlik) {
        const [ilkYil, ilkDeger] = ilk(b.dogurganlik.dogum);
        const [, sonDeger] = son(b.dogurganlik.dogum);
        kartlar.append(kart("Yıllık doğum", sayi.format(sonDeger),
            `${ilkYil}${ablatif(ilkYil)} beri ${imzaliYuzde((sonDeger / ilkDeger - 1) * 100)}`,
            sonDeger < ilkDeger));
    }
    basliklar.append(kartlar);
    ana.append(basliklar);
    // endregion

    let no = 0;
    const sonraki = () => String(++no).padStart(2, "0");

    // region 01 Nüfus
    if (b.nufus) {
        const n = sonraki();
        const topla = (nesne) => noktalar(nesne).reduce((t, [, v]) => t + v, 0);
        const dogalToplam = topla(b.nufus.dogal);
        const kalanToplam = topla(b.nufus.kalan);
        const bolum = bolumYap(ana, n,
            {etiket: "NÜFUS", yazi: nufusBaslik(dogalToplam, kalanToplam)},
            `Nüfusun değişimi iki kuvvetin toplamıdır: <strong>doğal artış</strong> ` +
            `(doğan eksi ölen) ve geri kalan — ki büyük kısmı göçtür. İkisi ters yöne ` +
            `gidebilir, ve gittiğinde tek bir artış oranı bunu gizler.`);
        icindekiler.push([n, "Nüfus"]);
        cizgiGrafik(kutuYap(bolum), {
            birim: "kişi",
            seriler: [
                {ad: "Nüfus", veri: b.nufus.toplam, renk: "var(--kehribar)", dolgu: true},
            ],
        });
        cizgiGrafik(kutuYap(bolum), {
            birim: "kişi/yıl",
            seriler: [
                {ad: "Doğal artış", veri: b.nufus.dogal, renk: "var(--iyi)", sifirdan: true},
                {ad: "Kalan (göç vb.)", veri: b.nufus.kalan, renk: "var(--uyari)", sifirdan: true},
            ],
        });
        const araYil = noktalar(b.nufus.dogal)[0]?.[0];
        const bitisYil = son(b.nufus.dogal)?.[0];
        cikarim(bolum, nufusCikarim(dogalToplam, kalanToplam, araYil, bitisYil));
    }
    // endregion

    // region 02 Yaş yapısı
    if (b.yas) {
        const n = sonraki();
        const [ilkYil, ilkPay] = ilk(b.yas.paylar["65+"]);
        const [sonYil, sonPay] = son(b.yas.paylar["65+"]);
        const [, cocukIlk] = ilk(b.yas.paylar["0-14"]);
        const [, cocukSon] = son(b.yas.paylar["0-14"]);
        const bolum = bolumYap(ana, n,
            {etiket: "YAŞ YAPISI", yazi: "Piramidin tabanı daralıyor, tepesi genişliyor"},
            `${ilkYil}'de yüz kişiden ${iki.format(ilkPay)}'i 65 yaşın üstündeydi, ` +
            `${sonYil}'te <strong>${iki.format(sonPay)}</strong>. Çocuk payı aynı sürede ` +
            `%${iki.format(cocukIlk)}'ten %${iki.format(cocukSon)}'e indi. Kaydırıcıyı ` +
            `oynatınca ilk yılın silueti ince çerçeve olarak yerinde kalıyor.`);
        icindekiler.push([n, "Yaş yapısı"]);
        piramit(kutuYap(bolum), b.yas);
        cizgiGrafik(kutuYap(bolum), {
            birim: "%",
            seriler: [
                {ad: "0-14", veri: b.yas.paylar["0-14"], renk: "var(--iyi)"},
                {ad: "15-64", veri: b.yas.paylar["15-64"], renk: "var(--metin-sonuk)"},
                {ad: "65+", veri: b.yas.paylar["65+"], renk: "var(--kehribar)"},
                ...(Object.keys(b.yas.ortanca_yas).length
                    ? [{ad: "Ortanca yaş", veri: b.yas.ortanca_yas, renk: "var(--karsi)",
                        eksen: "sag", kesik: true}]
                    : []),
            ],
            birimSag: "yaş",
        });
    }
    // endregion

    // region 03 Ölümlülük
    if (b.olum) {
        const n = sonraki();
        const [ilkYil, kabaIlk] = ilk(b.olum.kaba);
        const [sonYil, kabaSon] = son(b.olum.kaba);
        const [, stdSon] = son(b.olum.standart);
        const [, sayiIlk] = ilk(b.olum.sayi);
        const [, sayiSon] = son(b.olum.sayi);
        const bolum = bolumYap(ana, n, {
            etiket: "ÖLÜMLÜLÜK",
            yazi: `Ölüm sayısı ${imzaliYuzde((sayiSon / sayiIlk - 1) * 100, 0)}, ölümlülük ` +
                  `${imzaliYuzde((stdSon / kabaIlk - 1) * 100, 0)}`,
        },
            `${ilkYil} yılında ${sayi.format(sayiIlk)} kişi öldü, ${sonYil} yılında ` +
            `${sayi.format(sayiSon)}. Bu artışa bakıp ölümlülüğün arttığını söylemek ` +
            `yanlış olur: nüfus yaşlandı ve ölümlerin çoğu yaşlılıkta olur. Her yılın ` +
            `yaş-cinsiyet hızlarını <strong>${b.olum.standart_yil}'un nüfus yapısına</strong> ` +
            `uygulayınca geriye ölümlülüğün kendisi kalıyor.`);
        icindekiler.push([n, "Ölümlülük"]);
        cizgiGrafik(kutuYap(bolum), {
            birim: "‰",
            bantlar: [{ad: "pandemi", baslangic: 2020, bitis: 2021}],
            seriler: [
                {ad: "Kaba ölüm hızı", veri: b.olum.kaba, renk: "var(--kehribar)",
                 bicim: v => iki.format(v) + "‰"},
                {ad: "Yaşa göre standart", veri: b.olum.standart, renk: "var(--karsi)",
                 kesik: true, bicim: v => iki.format(v) + "‰"},
            ],
            sutun: {ad: "Ölüm sayısı", veri: b.olum.sayi, renk: "var(--kehribar-koyu)",
                    acik: false},
        });
        cikarim(bolum,
            `İki çizgi ${b.olum.standart_yil}'da aynı noktadan başlıyor — standart yıl o. ` +
            `Sonra ayrılıyorlar, ve aradaki mesafe <b>yaşlanmanın ölüm sayısına eklediği ` +
            `yük</b>. ${sonYil}'te kaba hız <b>${iki.format(kabaSon)}‰</b>, gerçek ` +
            `ölümlülük <b>${iki.format(stdSon)}‰</b>.`);

        // Fazla ölüm
        const fazla = {};
        const beklenen = {};
        const gerceklesen = {};
        for (const [yil, kayit] of noktalar(b.olum.fazla)) {
            if (yil < b.olum.fazla_taban) continue;
            beklenen[yil] = kayit.beklenen;
            gerceklesen[yil] = kayit.gerceklesen;
            fazla[yil] = kayit.gerceklesen - kayit.beklenen;
        }
        const kutu = kutuYap(bolum);
        cizgiGrafik(kutu, {
            birim: "ölüm",
            seriler: [
                {ad: `Beklenen (${b.olum.fazla_taban} ölümlülüğüyle)`, veri: beklenen,
                 renk: "var(--karsi)", kesik: true},
                {ad: "Gerçekleşen", veri: gerceklesen, renk: "var(--kehribar)"},
            ],
        });
        const topluFazla = Object.entries(fazla)
            .filter(([y]) => Number(y) <= 2021).reduce((t, [, v]) => t + v, 0);
        const sonFazla = son(fazla)?.[1] ?? 0;
        cikarim(bolum,
            `${b.olum.fazla_taban}'un yaş-cinsiyet ölümlülüğü sabit tutulup her yılın kendi ` +
            `nüfusuna uygulanınca beklenen ölüm çıkıyor. 2020-2021'de ` +
            `<b>${sayi.format(Math.round(topluFazla))}</b> fazla ölüm. ` +
            (sonFazla < 0
                ? `${son(fazla)[0]}'te ise <b>${sayi.format(Math.abs(Math.round(sonFazla)))}</b> ` +
                  `<b>eksik</b>: ölümlülük ${b.olum.fazla_taban}'un altına indi.`
                : ""));

        const gruplar = kutuYap(bolum);
        cizgiGrafik(gruplar, {
            birim: "‰",
            seriler: [
                {ad: "65+", veri: b.olum.gruplar["65+"], renk: "var(--kehribar)",
                 bicim: v => iki.format(v) + "‰"},
                {ad: "15-64", veri: b.olum.gruplar["15-64"], renk: "var(--metin-sonuk)",
                 eksen: "sag", bicim: v => iki.format(v) + "‰"},
                {ad: "0-14", veri: b.olum.gruplar["0-14"], renk: "var(--iyi)",
                 eksen: "sag", bicim: v => iki.format(v) + "‰"},
            ],
            birimSag: "‰",
        });
        cikarim(bolum,
            `Yaş gruplarının hızı ayrı eksenlerde: 65+ soldaki eksende, çünkü ` +
            `<b>on beş kat</b> büyük. Aynı eksene konsa diğer iki çizgi tabanda düz ` +
            `görünür ve hiçbir şey anlatmazdı.`);
    }
    // endregion

    // region 04 Doğurganlık
    if (b.dogurganlik) {
        const n = sonraki();
        const d = b.dogurganlik;
        const [ilkYil, dogumIlk] = ilk(d.dogum);
        const [sonYil, dogumSon] = son(d.dogum);
        const kadinIlk = d.kadin_15_49[ilkYil];
        const kadinSon = d.kadin_15_49[sonYil];
        const gdhIlk = d.gdh[ilkYil], gdhSon = d.gdh[sonYil];
        const bolum = bolumYap(ana, n,
            {etiket: "DOĞURGANLIK", yazi: "Doğum düşüşü, sayının gösterdiğinden derin"},
            `Doğum sayısı ${ilkYil}-${sonYil} arasında ` +
            `${imzaliYuzde((dogumSon / dogumIlk - 1) * 100)} değişti. Ama doğurgan çağdaki ` +
            `kadın sayısı aynı sürede ${imzaliYuzde((kadinSon / kadinIlk - 1) * 100)} ` +
            `değişti — yani paydası büyüyen bir kesirin payına bakıyoruz. ` +
            `<strong>Kadın başına</strong> değişim ` +
            `${imzaliYuzde((gdhSon / gdhIlk - 1) * 100)}.`);
        icindekiler.push([n, "Doğurganlık"]);
        cizgiGrafik(kutuYap(bolum), {
            birim: "‰",
            birimSag: "doğum",
            seriler: [
                {ad: "Genel doğurganlık hızı", veri: d.gdh, renk: "var(--kehribar)",
                 bicim: v => iki.format(v) + "‰"},
                {ad: "Doğum sayısı", veri: d.dogum, renk: "var(--metin-sonuk)",
                 eksen: "sag", kesik: true},
            ],
        });
        if (Object.keys(d.bebek_olum).length) {
            cizgiGrafik(kutuYap(bolum), {
                birim: "‰",
                seriler: [
                    {ad: "Bebek ölüm hızı", veri: d.bebek_olum, renk: "var(--uyari)",
                     dolgu: true, bicim: v => bir.format(v) + "‰"},
                ],
            });
        }
    }
    // endregion

    // region 05 Yaşam süresi
    if (b.yasam) {
        const n = sonraki();
        const bolum = bolumYap(ana, n,
            {etiket: "YAŞAM SÜRESİ", yazi: "Beklenen ömür, doğuşta ve 65 yaşında"},
            `Dönemin ölüm hızları hiç değişmezse beklenen yıl sayısı. Bir öngörü değil, ` +
            `bugünkü ölümlülüğün tek sayıya indirilmiş hâli. <strong>65 yaşındaki biri ` +
            `için beklenen süre ayrı hesaplanır</strong> — bebek ölümlerini geride ` +
            `bırakmıştır, o yüzden doğuştakinden farklıdır.`);
        icindekiler.push([n, "Yaşam süresi"]);
        const seriler = [];
        if (b.yasam["0"]) {
            seriler.push({ad: "Doğuşta, kadın", veri: b.yasam["0"].female, renk: "var(--karsi)",
                          bicim: v => bir.format(v) + " yıl"});
            seriler.push({ad: "Doğuşta, erkek", veri: b.yasam["0"].male, renk: "var(--kehribar)",
                          bicim: v => bir.format(v) + " yıl"});
        }
        cizgiGrafik(kutuYap(bolum), {birim: "yıl", seriler});
        if (b.yasam["65"]) {
            cizgiGrafik(kutuYap(bolum), {
                birim: "yıl",
                seriler: [
                    {ad: "65 yaşında, kadın", veri: b.yasam["65"].female, renk: "var(--karsi)",
                     bicim: v => bir.format(v) + " yıl"},
                    {ad: "65 yaşında, erkek", veri: b.yasam["65"].male, renk: "var(--kehribar)",
                     bicim: v => bir.format(v) + " yıl"},
                ],
            });
            const k = son(b.yasam["65"].female)?.[1], e = son(b.yasam["65"].male)?.[1];
            if (k && e) {
                cikarim(bolum,
                    `65 yaşına gelen bir kadını ortalama <b>${bir.format(k)}</b> yıl, bir ` +
                    `erkeği <b>${bir.format(e)}</b> yıl bekliyor. Aradaki ` +
                    `<b>${bir.format(k - e)}</b> yıl, yaşlılıkta dulluğun neden ağırlıklı ` +
                    `olarak kadınların meselesi olduğunun yarısı; öteki yarısı kadınların ` +
                    `kendilerinden büyük biriyle evlenmesi.`);
            }
        }
    }
    // endregion

    // region 06 Göç
    if (b.goc) {
        const n = sonraki();
        const bolum = bolumYap(ana, n, {etiket: "GÖÇ", yazi: gocBaslik(b.goc)},
            b.goc.bantlar
                ? `Gelen ve giden, <strong>yaşa göre</strong>. Bir yerin nüfusu doğal ` +
                  `artışı artı olduğu hâlde düşüyorsa cevap burada: hangi yaş gidiyor.`
                : `Ülke düzeyinde iller arası göç tanımsızdır — bir ilden ötekine taşınmak ` +
                  `ülkeye giriş değildir. Burada <strong>yurt dışıyla</strong> olan akış var.`);
        icindekiler.push([n, "Göç"]);
        if (b.goc.bantlar) {
            const yillar = Object.keys(b.goc.gelen).map(Number).sort((a, b2) => a - b2);
            gocProfili(kutuYap(bolum), b.goc, yillar.at(-1));
        }
        if (b.goc.yurtdisi && Object.keys(b.goc.yurtdisi.gelen).length) {
            cizgiGrafik(kutuYap(bolum), {
                birim: "kişi",
                seriler: [
                    {ad: "Yurt dışından gelen", veri: b.goc.yurtdisi.gelen, renk: "var(--iyi)"},
                    {ad: "Yurt dışına giden", veri: b.goc.yurtdisi.giden, renk: "var(--uyari)"},
                ],
            });
        }
    }
    // endregion

    // region 07 Evlilik
    if (b.evlilik) {
        const n = sonraki();
        const e = b.evlilik;
        const [ilkYil, evIlk] = ilk(e.evlenme_hizi) || [];
        const [sonYil, evSon] = son(e.evlenme_hizi) || [];
        const [, boIlk] = ilk(e.bosanma_hizi) || [];
        const [, boSon] = son(e.bosanma_hizi) || [];
        const bolum = bolumYap(ana, n,
            {etiket: "EVLİLİK", yazi: "Evlilik azalıyor, boşanma artıyor, yaş yükseliyor"},
            `Sayılar değil hızlar: nüfus büyürken sabit kalan bir evlenme sayısı aslında ` +
            `düşüştür. ${ilkYil}-${sonYil} arasında kaba evlenme hızı ` +
            `<strong>${iki.format(evIlk)}‰ → ${iki.format(evSon)}‰</strong>, boşanma ` +
            `<strong>${iki.format(boIlk)}‰ → ${iki.format(boSon)}‰</strong>.`);
        icindekiler.push([n, "Evlilik"]);
        cizgiGrafik(kutuYap(bolum), {
            birim: "‰",
            seriler: [
                {ad: "Evlenme hızı", veri: e.evlenme_hizi, renk: "var(--kehribar)",
                 bicim: v => iki.format(v) + "‰"},
                {ad: "Boşanma hızı", veri: e.bosanma_hizi, renk: "var(--uyari)",
                 bicim: v => iki.format(v) + "‰"},
            ],
        });
        if (e.ilk_evlenme_yasi?.male) {
            cizgiGrafik(kutuYap(bolum), {
                birim: "yaş",
                seriler: [
                    {ad: "İlk evlenme yaşı, erkek", veri: e.ilk_evlenme_yasi.male,
                     renk: "var(--kehribar)", bicim: v => bir.format(v)},
                    {ad: "İlk evlenme yaşı, kadın", veri: e.ilk_evlenme_yasi.female,
                     renk: "var(--karsi)", bicim: v => bir.format(v)},
                ],
            });
        }
        if (e.medeni_pay?.female) {
            bolum.append(medeniTablo(e.medeni_pay));
            const dulK = son(e.medeni_pay.female["Eşi öldü"])?.[1];
            const dulE = son(e.medeni_pay.male["Eşi öldü"])?.[1];
            if (dulK && dulE) {
                cikarim(bolum,
                    `Eşi ölmüş kadın oranı <b>%${iki.format(dulK)}</b>, erkek ` +
                    `<b>%${iki.format(dulE)}</b> — <b>${bir.format(dulK / dulE)}</b> katı. ` +
                    `Medeni durum toplamda yayımlanınca bu fark görünmez.`);
            }
        }
    }
    // endregion

    // region 08 Hanehalkı
    if (b.hane) {
        const n = sonraki();
        const [ilkYil, ilkBoy] = ilk(b.hane.buyukluk);
        const [sonYil, sonBoy] = son(b.hane.buyukluk);
        const bolum = bolumYap(ana, n,
            {etiket: "HANEHALKI", yazi: "Hane küçülüyor, hane sayısı artıyor"},
            `Ortalama hanehalkı ${ilkYil}'de ${iki.format(ilkBoy)} kişiydi, ${sonYil}'te ` +
            `<strong>${iki.format(sonBoy)}</strong>. Aynı nüfus daha çok eve bölünüyor: ` +
            `konut talebinin nüfus artışından bağımsız bir bileşeni var ve o bu satırda.`);
        icindekiler.push([n, "Hanehalkı"]);
        cizgiGrafik(kutuYap(bolum), {
            birim: "kişi",
            birimSag: "hane",
            seriler: [
                {ad: "Ortalama hanehalkı", veri: b.hane.buyukluk, renk: "var(--kehribar)",
                 bicim: v => iki.format(v) + " kişi"},
                ...(Object.keys(b.hane.sayi).length
                    ? [{ad: "Hane sayısı", veri: b.hane.sayi, renk: "var(--karsi)",
                        eksen: "sag", kesik: true}]
                    : []),
            ],
        });
    }
    // endregion

    if (veri.eksik.length) {
        const not = el("div", {class: "eksik-not"});
        not.innerHTML = "<b>Bu düzeyde olmayanlar:</b> " +
            veri.eksik.map(eksikAdi).join(", ") +
            ". Eksik değil — kaynak bu düzeyde yayımlamıyor.";
        ana.append(not);
    }

    const alt = el("footer");
    alt.append(
        el("span", {}, `veriatlas · ${veri.alan.ad} · ${duzeyAdi(veri.alan.duzey)}`),
        el("span", {}, "Ölüm ve doğum ikametgaha, evlenme olayın yerine göre"),
        el("span", {}, "Standartlaştırılmış hız bizim hesabımızdır, TÜİK yayımı değildir"),
    );
    ana.append(alt);

    const menu = document.getElementById("icindekiler");
    menu.textContent = "";
    for (const [numara, ad] of icindekiler) {
        menu.append(el("a", {href: "#b" + numara}, ad));
    }
}

function kart(baslik, deger, alt, dusus) {
    const kutu = el("div", {class: "kart"});
    kutu.append(el("dt", {}, baslik));
    const dd = el("dd", {}, deger);
    if (alt) dd.append(el("span", {class: "alt" + (dusus ? " dusus" : "")}, alt));
    kutu.append(dd);
    return kutu;
}

function medeniTablo(paylar) {
    const kutu = el("div", {class: "tablo-kutu"});
    const tablo = el("table");
    const durumlar = Object.keys(paylar.female);
    const yil = son(paylar.female[durumlar[0]])[0];
    const bas = el("thead");
    const satir = el("tr");
    satir.append(el("th", {}, `Medeni durum · ${yil}`), el("th", {}, "Kadın"),
                 el("th", {}, "Erkek"), el("th", {}, "Fark"));
    bas.append(satir);
    tablo.append(bas);
    const govde = el("tbody");
    for (const durum of durumlar) {
        const k = son(paylar.female[durum])?.[1] ?? 0;
        const e = son(paylar.male[durum])?.[1] ?? 0;
        const tr = el("tr");
        tr.append(el("td", {}, durum), el("td", {}, "%" + iki.format(k)),
                  el("td", {}, "%" + iki.format(e)), el("td", {}, imzali(k - e, 2) + " puan"));
        govde.append(tr);
    }
    tablo.append(govde);
    kutu.append(tablo);
    return kutu;
}

/** The headline reads the *period*, not the last year.
 *
 *  A place can have a negative year inside two decades of positive natural increase, and
 *  the finding worth a heading is which of the two forces carried the period. Zonguldak
 *  is exactly that case: births beat deaths across the span and the population still
 *  fell, which is a sentence about migration and not about one year's dip. */
function nufusBaslik(dogal, kalan) {
    const toplam = dogal + kalan;
    if (dogal > 0 && toplam < 0) return "Doğan ölenden çok, buna rağmen nüfus düşüyor";
    if (dogal < 0 && toplam > 0) return "Ölen doğandan çok, nüfusu göç ayakta tutuyor";
    if (dogal < 0 && toplam < 0) return "Hem doğal artış hem nüfus eksi";
    return "Nüfus ve onu hareket ettiren iki kuvvet";
}

function nufusCikarim(dogal, kalan, ilkYil, sonYil) {
    const arasi = ilkYil && sonYil ? `${ilkYil}-${sonYil} arasında` : "Dönem boyunca";
    const toplam = dogal + kalan;
    if (dogal > 0 && toplam < 0) {
        return `${arasi} doğal artış <b>${imzali(dogal, 0)}</b> kişi, geri kalan ` +
               `<b>${imzali(kalan, 0)}</b>. Doğan ölenden fazla, buna rağmen nüfus ` +
               `azalmış — <b>giden</b>, doğanın açtığı farkı fazlasıyla kapatıyor.`;
    }
    if (dogal < 0 && toplam > 0) {
        return `${arasi} doğal artış <b>${imzali(dogal, 0)}</b> kişi — ölen doğandan ` +
               `fazla. Nüfusun artması tamamen <b>gelenler</b> sayesinde.`;
    }
    return `${arasi} doğal artış <b>${imzali(dogal, 0)}</b> kişi, geri kalan ` +
           `<b>${imzali(kalan, 0)}</b>.`;
}

function gocBaslik(goc) {
    return goc.bantlar ? "Kim geliyor, kim gidiyor" : "Yurt dışıyla olan akış";
}

const DUZEY = {
    country: "Ülke düzeyi", province: "İl", region: "Coğrafi bölge",
    nuts1: "İBBS-1", nuts2: "İBBS-2", district: "İlçe",
};
const duzeyAdi = (d) => DUZEY[d] || d;

const EKSIK = {
    nufus: "nüfus", yas: "yaş yapısı", olum: "yaşa göre ölüm",
    dogurganlik: "doğurganlık", yasam: "yaşam süresi", goc: "göç",
    evlilik: "evlilik ve medeni durum", hane: "hanehalkı",
};
const eksikAdi = (ad) => EKSIK[ad] || ad;

// endregion

async function yukle(areaId) {
    const govde = document.getElementById("govde");
    govde.textContent = "";
    govde.append(el("p", {class: "ozet"}, "Yükleniyor…"));
    try {
        const cevap = await fetch(`../../public/rapor/${areaId}.json`);
        if (!cevap.ok) throw new Error(cevap.status);
        ciz(await cevap.json());
        window.scrollTo({top: 0});
    } catch (hata) {
        govde.textContent = "";
        govde.append(el("h1", {}, "Bu alanın raporu yok"));
        govde.append(el("p", {class: "ozet"},
            `${areaId} için henüz bir sayfa üretilmedi. ` +
            `scripts/build_report_data.py ${areaId} komutu üretir.`));
    }
}

function alanId() {
    const eslesme = /a=([A-Z0-9-]+)/.exec(location.hash);
    return eslesme ? eslesme[1] : "TR";
}

window.addEventListener("hashchange", () => yukle(alanId()));
yukle(alanId());
