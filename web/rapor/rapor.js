/* One report page for every area. The area comes from the hash — `#a=TR-34` — and its
 * payload from `public/rapor/<id>.json`, which `scripts/build_report_data.py` writes.
 *
 * The page draws; it does not compute the demography. Every rate and every share was
 * worked out next to the fact table, where the tests are. What this file computes is only
 * the *readings* of a series a reader can ask for on the spot — year-on-year change,
 * change since the first year — because those are a property of the line already drawn,
 * not a new measurement.
 */

const NS = "http://www.w3.org/2000/svg";

const sayi = new Intl.NumberFormat("tr-TR");
const sikisik = new Intl.NumberFormat("tr-TR", {notation: "compact", maximumFractionDigits: 1});
const ondalik = (n) => new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: n, maximumFractionDigits: n,
});
const bir = ondalik(1);
const iki = ondalik(2);

function imzali(value, basamak = 1) {
    const yazi = ondalik(basamak).format(Math.abs(value));
    return (value > 0 ? "+" : value < 0 ? "−" : "") + yazi;
}

/** Signed percent the way Turkish writes it: sign, then %, then the number. */
function imzaliYuzde(value, basamak = 1) {
    return (value >= 0 ? "+" : "−") + "%" + ondalik(basamak).format(Math.abs(value));
}

/** The ablative suffix a year takes: 2009'dan, 2007'den, 2013'ten.
 *
 *  Turkish harmony runs on the sound of the number, so the suffix follows the last spoken
 *  word — the units where there are any, the tens otherwise. */
const BIRLER = ["", "den", "den", "ten", "ten", "ten", "dan", "den", "den", "dan"];
const ONLAR = ["dan", "dan", "den", "dan", "tan", "den", "tan", "ten", "den", "dan"];
const ablatif = (yil) => "'" + (yil % 10 ? BIRLER[yil % 10] : ONLAR[Math.floor(yil / 10) % 10]);

function el(ad, ozellikler = {}, icerik) {
    const dugum = document.createElement(ad);
    for (const [k, v] of Object.entries(ozellikler)) {
        if (k === "class") dugum.className = v;
        else if (k in dugum && k !== "list") dugum[k] = v;
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

/** A year-keyed object as sorted [year, value] pairs. JSON keys are strings, and "10"
 *  sorting before "9" is the classic way an axis comes out shuffled while every value on
 *  it is right. */
function noktalar(nesne) {
    return Object.entries(nesne || {}).map(([y, v]) => [Number(y), v]).sort((a, b) => a[0] - b[0]);
}
const ilk = (nesne) => noktalar(nesne)[0];
const son = (nesne) => noktalar(nesne).at(-1);
const topla = (nesne) => noktalar(nesne).reduce((t, [, v]) => t + v, 0);

// region Kipler — bir serinin okunma biçimleri

/** The four ways a reader asked to see any series. They are readings of one line, not
 *  four measurements, so they live here rather than in four payload fields — and the
 *  chart keeps its own axis honest by re-scaling when the mode changes.
 *
 *  `fark` is in the series' own unit and `puan` is the same thing said out loud when that
 *  unit is already a percent: a share going 8% → 12% moved four *points*, and calling
 *  that "+4%" is the most common way a share is misread. */
const KIPLER = [
    {ad: "mutlak", etiket: "Mutlak"},
    {ad: "yillik", etiket: "Yıllık değişim %"},
    {ad: "ilkyil", etiket: "İlk yıla göre %"},
    {ad: "fark", etiket: "İlk yıla göre fark"},
];

function kipUygula(veri, kip, yuzdeMi) {
    const dizi = noktalar(veri);
    if (!dizi.length || kip === "mutlak") return veri;
    const cikti = {};
    if (kip === "yillik") {
        for (let i = 1; i < dizi.length; i += 1) {
            const [yil, v] = dizi[i], onceki = dizi[i - 1][1];
            if (onceki) cikti[yil] = ((v / onceki) - 1) * 100;
        }
        return cikti;
    }
    const [, taban] = dizi[0];
    for (const [yil, v] of dizi) {
        if (kip === "fark") cikti[yil] = v - taban;
        else if (taban) cikti[yil] = ((v / taban) - 1) * 100;
    }
    return cikti;
}

const kipBirimi = (kip, birim) =>
    kip === "mutlak" ? birim
    : kip === "fark" ? (birim === "%" ? "puan" : birim)
    : "%";

// endregion

// region Çizgi grafik

/** A line chart: shared x of years, a cursor balloon, toggleable series, four modes.
 *
 *  `eksen: "sag"` gives a series its own right-hand scale. Two scales on one frame is for
 *  the case where the pairing *is* the point — a count against the rate computed from it —
 *  and the axis label says which side a series belongs to.
 */
function cizgiGrafik(ana, {ad, seriler, bantlar = [], birim = "", birimSag = "",
                           sutun, kipler = true, not}) {
    const kutu = el("figure", {class: "grafik-kutu"});
    kutu.style.margin = "1.5rem 0 0";
    const W = 900, H = 360, sol = 62, ust = 26, alt = 40;
    const sag = seriler.some(s => s.eksen === "sag") ? 66 : 22;
    const ic = {g: W - sol - sag, y: H - ust - alt};

    let kip = "mutlak";
    const acik = new Map([...seriler, ...(sutun ? [sutun] : [])]
        .map(s => [s.ad, s.acik !== false]));

    const svg = svgEl("svg", {viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": ad || ""});
    const balon = el("div", {class: "balon"});
    let imlec, noktaDugum = [], yillar = [];

    const gecerli = (seri) => kipUygula(seri.veri, kip, seri.birim === "%");

    function hesapla() {
        yillar = [...new Set(seriler.flatMap(s => noktalar(gecerli(s)).map(([y]) => y)))]
            .sort((a, b) => a - b);
    }

    const xOf = (yil) =>
        sol + (ic.g * (yil - yillar[0])) / Math.max(1, yillar.at(-1) - yillar[0]);

    function olcek(taraf) {
        const degerler = seriler
            .filter(s => (s.eksen === "sag") === (taraf === "sag") && acik.get(s.ad))
            .flatMap(s => noktalar(gecerli(s)).map(([, v]) => v));
        if (!degerler.length) return null;
        let en = Math.min(...degerler);
        const tavan = Math.max(...degerler);
        const pay = (tavan - en) * 0.12 || Math.abs(tavan) * 0.1 || 1;
        // A mode that can go negative needs zero on the frame — a change of −3% and one of
        // +3% are opposite findings and a cropped axis hides which side of the line the
        // series is on.
        if (kip !== "mutlak" || taraf === "sag" || seriler.some(s => s.sifirdan && acik.get(s.ad))) {
            return {en: Math.min(0, en - pay * 0.4), ust: Math.max(0, tavan + pay)};
        }
        return {en: en - pay, ust: tavan + pay};
    }

    const yOf = (deger, taraf) => {
        const o = olcek(taraf) || {en: 0, ust: 1};
        return ust + ic.y - ((deger - o.en) / (o.ust - o.en)) * ic.y;
    };

    function adimlar({en, ust: tavan}) {
        const ham = (tavan - en) / 4;
        const buyukluk = 10 ** Math.floor(Math.log10(Math.abs(ham) || 1));
        const adim = [1, 2, 2.5, 5, 10].map(k => k * buyukluk).find(k => k >= ham) || ham;
        const cikti = [];
        for (let v = Math.ceil(en / adim) * adim; v <= tavan; v += adim) cikti.push(v);
        return cikti;
    }

    function kisa(v) {
        if (kip !== "mutlak" && kip !== "fark") {
            // Decimals follow the span, not the value: a percent axis running −1,5 to
            // +1,5 printed at zero decimals repeats "−1 −1 0 +1" and labels two
            // different gridlines the same.
            const o = olcek("sol");
            const genlik = o ? o.ust - o.en : 10;
            return imzali(v, genlik < 6 ? 1 : 0);
        }
        if (Math.abs(v) >= 1e4) return sikisik.format(v);
        if (Number.isInteger(v)) return sayi.format(v);
        return iki.format(v).replace(",00", "");
    }

    function ciz() {
        hesapla();
        svg.textContent = "";
        if (!yillar.length) return;

        for (const band of bantlar) {
            const x0 = xOf(band.baslangic) - 11, x1 = xOf(band.bitis) + 11;
            if (!Number.isFinite(x0)) continue;
            svg.append(svgEl("rect", {class: "band", x: x0, y: ust, width: x1 - x0, height: ic.y}));
            svg.append(svgEl("text", {class: "band-yazi", x: (x0 + x1) / 2, y: ust - 8,
                                      "text-anchor": "middle"}, band.ad));
        }

        const solOlcek = olcek("sol");
        if (solOlcek) {
            for (const deger of adimlar(solOlcek)) {
                const y = yOf(deger, "sol");
                const sifir = Math.abs(deger) < 1e-9;
                svg.append(svgEl("line", {class: sifir ? "taban" : "kilavuz",
                                          x1: sol, x2: W - sag, y1: y, y2: y}));
                svg.append(svgEl("text", {class: "eksen-yazi", x: sol - 9, y: y + 4,
                                          "text-anchor": "end"}, kisa(deger)));
            }
            svg.append(svgEl("text", {class: "eksen-yazi", x: sol - 9, y: ust - 9,
                                      "text-anchor": "end"}, kipBirimi(kip, birim)));
        }
        const sagOlcek = olcek("sag");
        if (sagOlcek) {
            for (const deger of adimlar(sagOlcek)) {
                svg.append(svgEl("text", {class: "eksen-yazi", x: W - sag + 9,
                                          y: yOf(deger, "sag") + 4}, kisa(deger)));
            }
            svg.append(svgEl("text", {class: "eksen-yazi", x: W - sag + 9, y: ust - 9},
                             kipBirimi(kip, birimSag)));
        }

        if (sutun && acik.get(sutun.ad) && kip === "mutlak") {
            const veri = noktalar(sutun.veri);
            const enBuyuk = Math.max(...veri.map(([, v]) => v));
            const genislik = Math.max(6, (ic.g / veri.length) * 0.6);
            for (const [yil, v] of veri) {
                const h = (v / enBuyuk) * ic.y * 0.5;
                svg.append(svgEl("rect", {x: xOf(yil) - genislik / 2, width: genislik,
                                          y: ust + ic.y - h, height: h,
                                          fill: sutun.renk, opacity: .2}));
            }
        }

        for (const seri of seriler) {
            if (!acik.get(seri.ad)) continue;
            const veri = noktalar(gecerli(seri));
            if (!veri.length) continue;
            const d = veri.map(([yil, v], i) =>
                (i ? "L" : "M") + xOf(yil) + " " + yOf(v, seri.eksen)).join(" ");
            if (seri.dolgu && kip === "mutlak") {
                const taban = yOf((olcek(seri.eksen) || {en: 0}).en, seri.eksen);
                svg.append(svgEl("path", {class: "alan-dolgu", fill: seri.renk,
                    d: `${d} L${xOf(veri.at(-1)[0])} ${taban} L${xOf(veri[0][0])} ${taban} Z`}));
            }
            svg.append(svgEl("path", {class: "seri", d, stroke: seri.renk,
                "stroke-dasharray": seri.kesik ? "5 4" : "none"}));
        }

        const her = yillar.length > 12 ? 2 : 1;
        yillar.forEach((yil, i) => {
            if (i % her) return;
            svg.append(svgEl("text", {class: "eksen-yazi", x: xOf(yil), y: H - 13,
                                      "text-anchor": "middle"}, yil));
        });

        imlec = svgEl("line", {class: "imlec", y1: ust, y2: ust + ic.y, opacity: 0});
        svg.append(imlec);
        noktaDugum = seriler.map(seri => {
            const nokta = svgEl("circle", {class: "nokta", r: 4.5, opacity: 0, fill: seri.renk});
            svg.append(nokta);
            return [seri, nokta];
        });
    }

    function bicimle(seri, deger) {
        const b = kipBirimi(kip, seri.birim ?? birim);
        if (kip === "yillik" || kip === "ilkyil") return imzaliYuzde(deger);
        if (kip === "fark") return imzali(deger, Math.abs(deger) < 100 ? 2 : 0) + (b ? " " + b : "");
        return (seri.bicim ? seri.bicim(deger) : kisa(deger)) + (seri.bicim ? "" : (b ? " " + b : ""));
    }

    function oku(yil, olay) {
        imlec.setAttribute("x1", xOf(yil));
        imlec.setAttribute("x2", xOf(yil));
        imlec.setAttribute("opacity", 1);
        balon.textContent = "";
        balon.append(el("span", {class: "yil"}, String(yil)));
        let bulundu = false;
        for (const [seri, nokta] of noktaDugum) {
            const deger = gecerli(seri)[yil];
            if (deger === undefined || !acik.get(seri.ad)) {
                nokta.setAttribute("opacity", 0);
                continue;
            }
            bulundu = true;
            nokta.setAttribute("cx", xOf(yil));
            nokta.setAttribute("cy", yOf(deger, seri.eksen));
            nokta.setAttribute("opacity", 1);
            const satir = el("div", {class: "satir"});
            const benek = el("span", {class: "benek"});
            benek.style.background = seri.renk;
            satir.append(benek, el("span", {}, seri.ad + " "), el("b", {}, bicimle(seri, deger)));
            balon.append(satir);
        }
        balon.classList.toggle("gorunur", bulundu);
        if (olay) {
            const kutuOlcu = svg.getBoundingClientRect();
            const x = olay.clientX - kutuOlcu.left;
            balon.style.left = Math.min(kutuOlcu.width - balon.offsetWidth - 8,
                                        Math.max(8, x + 14)) + "px";
            balon.style.top = (olay.clientY - kutuOlcu.top - balon.offsetHeight - 12) + "px";
        }
    }

    // Üst satır: ad ve seri anahtarları
    const ustSatir = el("div", {class: "grafik-ust"});
    if (ad) ustSatir.append(el("span", {class: "grafik-ad"}, ad));
    for (const seri of [...seriler, ...(sutun ? [sutun] : [])]) {
        const dugme = el("button", {class: "anahtar", type: "button"});
        dugme.setAttribute("aria-pressed", String(acik.get(seri.ad)));
        const isaret = el("span", {class: "isaret" + (seri === sutun ? " kutu" : "")});
        isaret.style.background = seri.renk;
        dugme.append(isaret, document.createTextNode(seri.ad));
        dugme.addEventListener("click", () => {
            acik.set(seri.ad, !acik.get(seri.ad));
            dugme.setAttribute("aria-pressed", String(acik.get(seri.ad)));
            ciz();
        });
        ustSatir.append(dugme);
    }
    kutu.append(ustSatir);

    if (kipler) {
        const satir = el("div", {class: "kipler"});
        for (const {ad: kipAdi, etiket} of KIPLER) {
            const dugme = el("button", {class: "kip", type: "button"}, etiket);
            dugme.setAttribute("aria-pressed", String(kipAdi === kip));
            dugme.addEventListener("click", () => {
                kip = kipAdi;
                for (const kardes of satir.children) {
                    kardes.setAttribute("aria-pressed", String(kardes === dugme));
                }
                ciz();
            });
            satir.append(dugme);
        }
        kutu.append(satir);
    }

    kutu.append(svg, balon);
    if (not) kutu.append(el("div", {class: "kaydirici"}, not));
    ciz();

    svg.addEventListener("pointermove", (olay) => {
        const kutuOlcu = svg.getBoundingClientRect();
        const oranX = ((olay.clientX - kutuOlcu.left) / kutuOlcu.width) * W;
        const yil = yillar.reduce((en, y) =>
            Math.abs(xOf(y) - oranX) < Math.abs(xOf(en) - oranX) ? y : en, yillar[0]);
        oku(yil, olay);
    });
    svg.addEventListener("pointerleave", () => {
        balon.classList.remove("gorunur");
        imlec?.setAttribute("opacity", 0);
        for (const [, nokta] of noktaDugum) nokta.setAttribute("opacity", 0);
    });

    ana.append(kutu);
    return kutu;
}

// endregion

// region Piramit

function piramit(ana, {piramit: veri, bantlar}) {
    const kutu = el("figure", {class: "grafik-kutu"});
    kutu.style.margin = "1.5rem 0 0";
    const yillar = Object.keys(veri).map(Number).sort((a, b) => a - b);
    const W = 900, H = 440, orta = W / 2, bosluk = 58, ust = 30, alt = 30;
    const satir = (H - ust - alt) / bantlar.length;
    const kanat = (W - bosluk) / 2 - 24;
    const enBuyuk = Math.max(...yillar.flatMap(y =>
        bantlar.flatMap(b => [veri[y]?.[b]?.male || 0, veri[y]?.[b]?.female || 0])));
    const ilkYil = yillar[0];

    const svg = svgEl("svg", {viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Yaş piramidi"});
    const balon = el("div", {class: "balon"});
    let suAnki = yillar.at(-1);

    function ciz(yil) {
        suAnki = yil;
        svg.textContent = "";
        const toplam = bantlar.reduce((t, b) =>
            t + (veri[yil]?.[b]?.male || 0) + (veri[yil]?.[b]?.female || 0), 0);

        bantlar.forEach((band, i) => {
            const y = ust + (bantlar.length - 1 - i) * satir;
            for (const [sex, yon, renk] of [["male", -1, "var(--vurgu)"],
                                            ["female", 1, "var(--karsi)"]]) {
                const simdi = veri[yil]?.[band]?.[sex] || 0;
                const once = veri[ilkYil]?.[band]?.[sex] || 0;
                const g = (simdi / enBuyuk) * kanat;
                const g0 = (once / enBuyuk) * kanat;
                const x = yon < 0 ? orta - bosluk / 2 - g : orta + bosluk / 2;
                const x0 = yon < 0 ? orta - bosluk / 2 - g0 : orta + bosluk / 2;
                if (yil !== ilkYil) {
                    svg.append(svgEl("rect", {x: x0, y: y + 1.5, width: g0, height: satir - 3,
                        fill: "none", stroke: "var(--cizgi-acik)", "stroke-width": 1}));
                }
                const cubuk = svgEl("rect", {x, y: y + 1.5, width: g, height: satir - 3,
                                             fill: renk, opacity: .85});
                cubuk.dataset.band = band;
                cubuk.dataset.sex = sex;
                cubuk.dataset.kisi = simdi;
                cubuk.dataset.once = once;
                cubuk.dataset.pay = toplam ? (simdi / toplam) * 100 : 0;
                svg.append(cubuk);
            }
            svg.append(svgEl("text", {class: "eksen-yazi", x: orta,
                y: y + satir / 2 + 4, "text-anchor": "middle"}, band));
        });

        svg.append(svgEl("text", {class: "eksen-yazi", x: orta - bosluk / 2 - 6, y: ust - 12,
                                  "text-anchor": "end"}, "erkek"));
        svg.append(svgEl("text", {class: "eksen-yazi", x: orta + bosluk / 2 + 6, y: ust - 12},
                        "kadın"));
        svg.append(svgEl("text", {class: "eksen-yazi", x: W - 8, y: ust - 12,
            "text-anchor": "end"}, `${sayi.format(toplam)} kişi` +
            (yil === ilkYil ? "" : ` · ince çerçeve ${ilkYil}`)));
    }

    svg.addEventListener("pointermove", (olay) => {
        const hedef = olay.target;
        if (!(hedef instanceof SVGRectElement) || !hedef.dataset.band) {
            balon.classList.remove("gorunur");
            return;
        }
        const {band, sex, kisi, once, pay} = hedef.dataset;
        balon.textContent = "";
        balon.append(el("span", {class: "yil"},
            `${band} yaş · ${sex === "male" ? "erkek" : "kadın"} · ${suAnki}`));
        const satirlar = [
            [`${sayi.format(Number(kisi))} kişi`, true],
            [`nüfusun %${iki.format(Number(pay))}'i`, false],
        ];
        if (suAnki !== ilkYil && Number(once)) {
            satirlar.push([`${ilkYil}: ${sayi.format(Number(once))} · ` +
                `${imzaliYuzde((Number(kisi) / Number(once) - 1) * 100)}`, false]);
        }
        for (const [yazi, kalin] of satirlar) {
            const satirEl = el("div", {class: "satir"});
            satirEl.append(kalin ? el("b", {}, yazi) : el("span", {}, yazi));
            balon.append(satirEl);
        }
        balon.classList.add("gorunur");
        const kutuOlcu = svg.getBoundingClientRect();
        balon.style.left = Math.min(kutuOlcu.width - balon.offsetWidth - 8,
            Math.max(8, olay.clientX - kutuOlcu.left + 14)) + "px";
        balon.style.top = Math.max(4, olay.clientY - kutuOlcu.top - balon.offsetHeight - 10) + "px";
    });
    svg.addEventListener("pointerleave", () => balon.classList.remove("gorunur"));

    const ustSatir = el("div", {class: "grafik-ust"});
    ustSatir.append(el("span", {class: "grafik-ad"}, "Yaş piramidi"),
                    el("span", {class: "bosluk"}),
                    el("span", {class: "kip"}, "çubuğun üstüne gelin"));
    const kaydirici = el("div", {class: "kaydirici"});
    const girdi = el("input", {type: "range", min: yillar[0], max: yillar.at(-1),
                               value: yillar.at(-1), step: 1});
    const cikti = el("output", {}, String(yillar.at(-1)));
    girdi.addEventListener("input", () => {
        cikti.textContent = girdi.value;
        ciz(Number(girdi.value));
    });
    kaydirici.append(el("span", {}, "Yıl"), girdi, cikti);

    kutu.append(ustSatir, svg, balon, kaydirici);
    ciz(yillar.at(-1));
    ana.append(kutu);
}

// endregion

// region Göç profili

function gocProfili(ana, bolum) {
    const kutu = el("figure", {class: "grafik-kutu"});
    kutu.style.margin = "1.5rem 0 0";
    const yillar = Object.keys(bolum.gelen).map(Number).sort((a, b) => a - b);
    const bantlar = bolum.bantlar;
    const W = 900, H = 340, sol = 30, sag = 20, ust = 26, alt = 42;
    const ic = {g: W - sol - sag, y: H - ust - alt};
    const svg = svgEl("svg", {viewBox: `0 0 ${W} ${H}`, role: "img",
                              "aria-label": "Göçün yaş profili"});
    const balon = el("div", {class: "balon"});
    const taban = ust + ic.y * 0.55;

    function ciz(yil) {
        svg.textContent = "";
        const gelen = bolum.gelen[yil] || {}, giden = bolum.giden[yil] || {};
        const enBuyuk = Math.max(...bantlar.map(b =>
            Math.max(gelen[b] || 0, giden[b] || 0)), 1);
        const genislik = (ic.g / bantlar.length) * 0.34;

        bantlar.forEach((band, i) => {
            const x = sol + (ic.g * (i + 0.5)) / bantlar.length;
            const hG = ((gelen[band] || 0) / enBuyuk) * (taban - ust);
            const hK = ((giden[band] || 0) / enBuyuk) * (H - alt - taban);
            for (const [h, y0, renk, tur, deger] of [
                [hG, taban - hG, "var(--iyi)", "gelen", gelen[band] || 0],
                [hK, taban, "var(--uyari)", "giden", giden[band] || 0],
            ]) {
                const cubuk = svgEl("rect", {
                    x: tur === "gelen" ? x - genislik : x, y: y0,
                    width: genislik, height: h, fill: renk, opacity: .85});
                cubuk.dataset.band = band;
                cubuk.dataset.tur = tur;
                cubuk.dataset.deger = deger;
                cubuk.dataset.net = (gelen[band] || 0) - (giden[band] || 0);
                svg.append(cubuk);
            }
            svg.append(svgEl("text", {class: "eksen-yazi", x, y: H - 12,
                                      "text-anchor": "middle"}, band));
        });
        svg.append(svgEl("line", {class: "taban", x1: sol, x2: W - sag, y1: taban, y2: taban}));
        svg.append(svgEl("text", {class: "eksen-yazi", x: sol, y: ust - 8}, "gelen ↑"));
        svg.append(svgEl("text", {class: "eksen-yazi", x: sol, y: H - alt + 26}, "giden ↓"));
    }

    svg.addEventListener("pointermove", (olay) => {
        const hedef = olay.target;
        if (!(hedef instanceof SVGRectElement) || !hedef.dataset.band) {
            balon.classList.remove("gorunur");
            return;
        }
        const {band, tur, deger, net} = hedef.dataset;
        balon.textContent = "";
        balon.append(el("span", {class: "yil"}, `${band} yaş`));
        const s1 = el("div", {class: "satir"});
        s1.append(el("span", {}, tur === "gelen" ? "Gelen" : "Giden"),
                  el("b", {}, sayi.format(Number(deger))));
        const s2 = el("div", {class: "satir"});
        s2.append(el("span", {}, "Net"), el("b", {}, imzali(Number(net), 0)));
        balon.append(s1, s2);
        balon.classList.add("gorunur");
        const kutuOlcu = svg.getBoundingClientRect();
        balon.style.left = Math.min(kutuOlcu.width - balon.offsetWidth - 8,
            Math.max(8, olay.clientX - kutuOlcu.left + 14)) + "px";
        balon.style.top = Math.max(4, olay.clientY - kutuOlcu.top - balon.offsetHeight - 10) + "px";
    });
    svg.addEventListener("pointerleave", () => balon.classList.remove("gorunur"));

    const ustSatir = el("div", {class: "grafik-ust"});
    ustSatir.append(el("span", {class: "grafik-ad"}, "Göçün yaş profili"));
    const kaydirici = el("div", {class: "kaydirici"});
    const girdi = el("input", {type: "range", min: yillar[0], max: yillar.at(-1),
                               value: yillar.at(-1), step: 1});
    const cikti = el("output", {}, String(yillar.at(-1)));
    girdi.addEventListener("input", () => {
        cikti.textContent = girdi.value;
        ciz(Number(girdi.value));
    });
    kaydirici.append(el("span", {}, "Yıl"), girdi, cikti);

    kutu.append(ustSatir, svg, balon, kaydirici);
    ciz(yillar.at(-1));
    ana.append(kutu);
}

// endregion

// region Harita

let geometri = null;

/** Provinces as one path each, in a viewBox fitted to Türkiye's bounding box.
 *
 *  Latitude is *not* scaled by cos(φ) here: at Türkiye's latitudes an equirectangular
 *  plot is stretched about a third too tall, so the country would look wrong to anyone
 *  who has seen the map. The y scale carries that factor. */
function haritaCiz(hedef, {vurgula, renk, tiklama}) {
    if (!geometri) return null;
    const kutular = geometri.features.flatMap(f => noktaListesi(f).flat());
    const xler = kutular.map(p => p[0]), yler = kutular.map(p => p[1]);
    const enX = Math.min(...xler), buyukX = Math.max(...xler);
    const enY = Math.min(...yler), buyukY = Math.max(...yler);
    const orta = ((enY + buyukY) / 2) * Math.PI / 180;
    const oran = Math.cos(orta);
    const W = 1000;
    const H = W * ((buyukY - enY) / ((buyukX - enX) * oran));

    const svg = svgEl("svg", {viewBox: `0 0 ${W} ${H}`, role: "img",
                              "aria-label": "Türkiye haritası"});
    const xOf = (lon) => ((lon - enX) / (buyukX - enX)) * W;
    const yOf = (lat) => H - ((lat - enY) / (buyukY - enY)) * H;

    for (const ozellik of geometri.features) {
        const d = noktaListesi(ozellik).map(halka =>
            halka.map(([lon, lat], i) => (i ? "L" : "M") + xOf(lon).toFixed(1) + " " +
                yOf(lat).toFixed(1)).join(" ") + " Z").join(" ");
        const yol = svgEl("path", {class: "il", d,
            fill: renk ? renk(ozellik.properties.area_id) : "var(--yuzey-alt)"});
        if (ozellik.properties.area_id === vurgula) yol.classList.add("bu");
        const baslik = svgEl("title", {}, ozellik.properties.name_tr);
        yol.append(baslik);
        if (tiklama) {
            yol.addEventListener("click", () => tiklama(ozellik.properties.area_id));
        }
        svg.append(yol);
    }
    hedef.append(svg);
    return svg;
}

function noktaListesi(ozellik) {
    const g = ozellik.geometry;
    if (g.type === "Polygon") return g.coordinates;
    return g.coordinates.flat();
}

// endregion

// region Sıralama

/** Rank, the top five and the bottom five, and the map that shows the whole distribution.
 *
 *  "En iyi / en kötü" only where a direction exists. A province with a high share of
 *  over-65s is not winning or losing at anything, and labelling that column "best" would
 *  be the page inventing a judgement the data does not carry. */
function siralamaBolumu(ana, alan, siralama, dizin) {
    if (!siralama || alan.duzey !== "province") return null;
    const adlar = Object.fromEntries(dizin.map(r => [r.area_id, r.ad]));
    const anahtarlar = Object.keys(siralama);
    let secili = "yasli_pay";

    const bolum = el("section", {id: "b-siralama"});
    bolum.append(el("p", {class: "bolum-no"}, "SIRALAMA"));
    bolum.append(el("h2", {}, "81 il içinde nerede duruyor"));
    const giris = el("p", {class: "giris"});
    giris.innerHTML = "Bir ilin kendi serisi ne kadar hareket ettiğini söyler, " +
        "<strong>sıra</strong> nereye düştüğünü. Ölçüyü değiştirin: harita ve iki " +
        "liste birlikte güncelleniyor.";
    bolum.append(giris);

    const ustSatir = el("div", {class: "siralama-ust"});
    const secim = el("select", {"aria-label": "Ölçü seç"});
    for (const anahtar of anahtarlar) {
        secim.append(el("option", {value: anahtar}, siralama[anahtar].ad));
    }
    secim.value = secili;
    const rozet = el("span", {class: "rozet"});
    ustSatir.append(secim, rozet);
    bolum.append(ustSatir);

    const govde = el("div", {class: "siralama-govde"});
    const haritaKutu = el("div", {class: "harita-kutu"});
    const listeler = el("div", {style: "display:grid;gap:1rem"});
    govde.append(haritaKutu, listeler);
    bolum.append(govde);
    ana.append(bolum);

    /** A value in its measure's own notation. Turkish puts the percent sign in front, so
     *  a shared helper is the only way the badge, the legend and the two lists cannot
     *  disagree about it — and they did: the legend read "3,80 %". */
    function bicimDeger(olcu, v) {
        const yazi = ondalik(olcu.basamak).format(v);
        return olcu.birim === "%" ? "%" + yazi : yazi + " " + olcu.birim;
    }

    function yenile() {
        const olcu = siralama[secili];
        const sirali = Object.entries(olcu.deger).sort((a, b) => b[1] - a[1]);
        const yer = sirali.findIndex(([id]) => id === alan.area_id) + 1;
        const benim = olcu.deger[alan.area_id];
        const degerler = sirali.map(([, v]) => v);
        const enAz = Math.min(...degerler), enCok = Math.max(...degerler);

        rozet.textContent = benim === undefined
            ? "bu ilde yok"
            : `${sirali.length} il içinde ${yer}. · ${bicimDeger(olcu, benim)}`;

        haritaKutu.textContent = "";
        haritaCiz(haritaKutu, {
            vurgula: alan.area_id,
            renk: (id) => {
                const v = olcu.deger[id];
                if (v === undefined) return "var(--yuzey-alt)";
                const t = (v - enAz) / (enCok - enAz || 1);
                return `color-mix(in oklab, var(--vurgu) ${Math.round(12 + t * 78)}%, var(--yuzey-alt))`;
            },
            tiklama: (id) => { location.hash = "a=" + id; },
        });
        const lejant = el("div", {class: "lejant"});
        lejant.append(el("span", {}, bicimDeger(olcu, enAz)));
        for (let i = 0; i < 5; i += 1) {
            const kutucuk = el("span", {class: "kutucuk"});
            kutucuk.style.background =
                `color-mix(in oklab, var(--vurgu) ${12 + (i / 4) * 78}%, var(--yuzey-alt))`;
            lejant.append(kutucuk);
        }
        lejant.append(el("span", {}, bicimDeger(olcu, enCok)),
                      el("span", {class: "bosluk"}),
                      el("span", {}, "bir ile tıklayın"));
        haritaKutu.append(lejant);

        listeler.textContent = "";
        const yon = olcu.yon;
        const ustBaslik = yon === "dusuk" ? "En yüksek 5 (en kötü)"
            : yon === "yuksek" ? "En yüksek 5 (en iyi)" : "En yüksek 5";
        const altBaslik = yon === "dusuk" ? "En düşük 5 (en iyi)"
            : yon === "yuksek" ? "En düşük 5 (en kötü)" : "En düşük 5";
        listeler.append(liste(ustBaslik, sirali.slice(0, 5), 1),
                        liste(altBaslik, sirali.slice(-5).reverse(), sirali.length, true));

        function liste(baslik, kayitlar, baslangic, tersNumara) {
            const kutu = el("div", {class: "liste"});
            kutu.append(el("h3", {}, baslik));
            const ol = el("ol");
            kayitlar.forEach(([id, v], i) => {
                const li = el("li");
                if (id === alan.area_id) li.classList.add("bu");
                li.append(
                    el("span", {class: "no"}, String(tersNumara ? baslangic - i : baslangic + i)),
                    el("span", {class: "ad"}, adlar[id] || id),
                    el("span", {class: "deger"}, bicimDeger(olcu, v)));
                ol.append(li);
            });
            kutu.append(ol);
            return kutu;
        }
    }

    secim.addEventListener("change", () => { secili = secim.value; yenile(); });
    yenile();
    return ["SIRALAMA", "Sıralama", "b-siralama"];
}

// endregion

// region Sayfa

function bolumYap(ana, no, etiket, baslik, giris) {
    const bolum = el("section", {id: "b" + no});
    bolum.append(el("p", {class: "bolum-no"}, no + " — " + etiket));
    bolum.append(el("h2", {}, baslik));
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

function kart(baslik, deger, altHtml) {
    const kutu = el("div", {class: "kart"});
    kutu.append(el("dt", {}, baslik));
    const dd = el("dd", {}, deger);
    if (altHtml) {
        const alt = el("span", {class: "alt"});
        alt.innerHTML = altHtml;
        dd.append(alt);
    }
    kutu.append(dd);
    return kutu;
}

const DUZEY = {country: "Ülke", province: "İl", region: "Coğrafi bölge",
               nuts1: "İBBS-1", nuts2: "İBBS-2", district: "İlçe"};
const EKSIK = {nufus: "nüfus", yas: "yaş yapısı", olum: "yaşa göre ölüm",
               dogurganlik: "doğurganlık", yasam: "yaşam süresi", goc: "göç",
               evlilik: "evlilik ve medeni durum", hane: "hanehalkı"};

function altBaslikYaz(b) {
    /* One sentence that says what this place's two decades were, chosen from the data.
       A subtitle that is the same on eighty-one pages is a subtitle nobody reads. */
    if (!b.nufus) return "Nüfusun on dokuz yılı";
    const dogal = topla(b.nufus.dogal), kalan = topla(b.nufus.kalan);
    const [, ilkN] = ilk(b.nufus.toplam), [, sonN] = son(b.nufus.toplam);
    const buyume = (sonN / ilkN - 1) * 100;
    const yasli = b.yas ? son(b.yas.paylar["65+"])[1] - ilk(b.yas.paylar["65+"])[1] : 0;
    if (dogal > 0 && kalan < 0 && sonN < ilkN) {
        return "Doğan ölenden çok, buna rağmen nüfus eridi: gidenin hikâyesi";
    }
    if (dogal < 0 && sonN > ilkN) return "Ölen doğandan çok; nüfusu gelenler ayakta tutuyor";
    if (yasli > 6) return "Hızla yaşlanan bir nüfus";
    if (buyume > 30) return "Hızla büyüyen, hâlâ genç bir nüfus";
    if (buyume < 0) return "Küçülen bir nüfus";
    return "Büyüyen ama yaşlanan bir nüfus";
}

function ciz(veri, siralama, dizin) {
    const ana = document.getElementById("govde");
    ana.textContent = "";
    const b = veri.bolumler;
    const ray = [];

    // region Başlık
    const basliklar = el("header");
    const kunye = el("p", {class: "kunye"});
    kunye.innerHTML = `Demografi raporu <span class="ayrac">/</span> ` +
        `${DUZEY[veri.alan.duzey] || veri.alan.duzey} <span class="ayrac">/</span> ` +
        `TÜİK ADNKS · çekim 2026-08`;
    basliklar.append(kunye);

    const yillar = b.nufus ? noktalar(b.nufus.toplam).map(([y]) => y) : [];
    const basSatir = el("div", {class: "bas-satir"});
    const solBas = el("div", {style: "flex:1 1 22rem"});
    const h1 = el("h1");
    h1.innerHTML = veri.alan.ad +
        (yillar.length ? ` <span class="yil" style="color:var(--metin-sonuk);font-weight:400">` +
            `${yillar[0]}–${yillar.at(-1)}</span>` : "");
    solBas.append(h1, el("p", {class: "alt-baslik"}, altBaslikYaz(b)));
    basSatir.append(solBas);

    if (veri.alan.duzey === "province") {
        const mini = el("div", {class: "mini-harita"});
        basSatir.append(mini);
        haritaCiz(mini, {vurgula: veri.alan.area_id,
                         renk: (id) => id === veri.alan.area_id
                             ? "var(--vurgu)" : "var(--yuzey-alt)"});
    }
    basliklar.append(basSatir);

    const kartlar = el("dl", {class: "kartlar"});
    if (b.nufus) {
        const [ilkYil, ilkDeger] = ilk(b.nufus.toplam);
        const [sonYil, sonDeger] = son(b.nufus.toplam);
        const degisim = (sonDeger / ilkDeger - 1) * 100;
        kartlar.append(kart(`Nüfus · ${sonYil}`, sayi.format(sonDeger),
            `${ilkYil}: ${sayi.format(ilkDeger)}<br>` +
            `${sonYil - ilkYil} yılda <b class="${degisim < 0 ? "dusus" : ""}">` +
            `${imzaliYuzde(degisim)}</b> (${imzali(sonDeger - ilkDeger, 0)} kişi)`));
    }
    if (b.yas) {
        const [ilkYil, ilkPay] = ilk(b.yas.paylar["65+"]);
        const [sonYil, pay] = son(b.yas.paylar["65+"]);
        kartlar.append(kart(`65 yaş üstü payı · ${sonYil}`, "%" + iki.format(pay),
            `${ilkYil}: %${iki.format(ilkPay)}<br>` +
            `<b>${imzali(pay - ilkPay, 2)} puan</b> (${imzaliYuzde((pay / ilkPay - 1) * 100)})`));
    }
    if (b.yasam?.["0"]) {
        const k = son(b.yasam["0"].female), e = son(b.yasam["0"].male);
        if (k && e) {
            kartlar.append(kart(`Doğuşta yaşam süresi · ${k[0]}`,
                bir.format((k[1] + e[1]) / 2) + " yıl",
                `Kadın <b>${bir.format(k[1])} yıl</b> · Erkek <b>${bir.format(e[1])} yıl</b><br>` +
                `aradaki fark ${bir.format(k[1] - e[1])} yıl`));
        }
    }
    if (b.dogurganlik) {
        const [ilkYil, ilkDeger] = ilk(b.dogurganlik.dogum);
        const [sonYil, sonDeger] = son(b.dogurganlik.dogum);
        const gdhIlk = b.dogurganlik.gdh[ilkYil], gdhSon = b.dogurganlik.gdh[sonYil];
        kartlar.append(kart(`Yıllık doğum · ${sonYil}`, sayi.format(sonDeger),
            `${ilkYil}: ${sayi.format(ilkDeger)} → ` +
            `<b class="${sonDeger < ilkDeger ? "dusus" : ""}">` +
            `${imzaliYuzde((sonDeger / ilkDeger - 1) * 100)}</b><br>` +
            (gdhIlk && gdhSon
                ? `kadın başına <b>${imzaliYuzde((gdhSon / gdhIlk - 1) * 100)}</b>` : "")));
    }
    basliklar.append(kartlar);
    ana.append(basliklar);
    // endregion

    let no = 0;
    const sonraki = () => String(++no).padStart(2, "0");

    // region 01 Nüfus
    if (b.nufus) {
        const n = sonraki();
        const dogalToplam = topla(b.nufus.dogal), kalanToplam = topla(b.nufus.kalan);
        const araYil = noktalar(b.nufus.dogal)[0]?.[0], bitisYil = son(b.nufus.dogal)?.[0];
        const bolum = bolumYap(ana, n, "NÜFUS", nufusBaslik(dogalToplam, kalanToplam),
            "Nüfusun değişimi iki kuvvetin toplamıdır: <strong>doğal artış</strong> " +
            "(doğan eksi ölen) ve geri kalan — ki büyük kısmı göçtür. İkisi ters yöne " +
            "gidebilir, ve gittiğinde tek bir artış oranı bunu gizler.");
        ray.push([n, "Nüfus"]);
        cizgiGrafik(bolum, {ad: "Nüfus", birim: "kişi",
            seriler: [{ad: "Nüfus", veri: b.nufus.toplam, renk: "var(--vurgu)", dolgu: true}]});
        cizgiGrafik(bolum, {ad: "Yıllık bileşenler", birim: "kişi/yıl", kipler: false,
            seriler: [
                {ad: "Doğal artış", veri: b.nufus.dogal, renk: "var(--iyi)", sifirdan: true},
                {ad: "Kalan (göç vb.)", veri: b.nufus.kalan, renk: "var(--uyari)", sifirdan: true},
            ]});
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
        const bolum = bolumYap(ana, n, "YAŞ YAPISI",
            "Piramidin tabanı daralıyor, tepesi genişliyor",
            `${ilkYil}'de yüz kişiden ${iki.format(ilkPay)}'i 65 yaşın üstündeydi, ` +
            `${sonYil}'te <strong>${iki.format(sonPay)}</strong>. Çocuk payı aynı sürede ` +
            `%${iki.format(cocukIlk)}'ten %${iki.format(cocukSon)}'e indi. Kaydırıcıyı ` +
            `oynatın: ilk yılın silueti ince çerçeve olarak yerinde kalıyor, çubuğun ` +
            `üstüne gelince o bandın sayısı ve payı çıkıyor.`);
        ray.push([n, "Yaş yapısı"]);
        piramit(bolum, b.yas);

        // Mutlak ve oran ayrı grafikte: biri kaç kişi, öteki yüzde kaç, ve ikisi aynı
        // eksende yan yana konunca büyük olan ötekini ezer.
        const sayilar = {};
        for (const grup of ["0-14", "15-64", "65+"]) {
            sayilar[grup] = {};
            for (const [yil, pay] of noktalar(b.yas.paylar[grup])) {
                const toplamNufus = b.nufus?.toplam?.[yil];
                if (toplamNufus) sayilar[grup][yil] = Math.round((pay / 100) * toplamNufus);
            }
        }
        if (Object.keys(sayilar["65+"]).length) {
            cizgiGrafik(bolum, {ad: "Yaş grupları — kişi sayısı", birim: "kişi",
                seriler: [
                    {ad: "0-14", veri: sayilar["0-14"], renk: "var(--iyi)"},
                    {ad: "15-64", veri: sayilar["15-64"], renk: "var(--metin-sonuk)"},
                    {ad: "65+", veri: sayilar["65+"], renk: "var(--vurgu)"},
                ]});
        }
        cizgiGrafik(bolum, {ad: "Yaş grupları — pay", birim: "%",
            seriler: [
                {ad: "0-14", veri: b.yas.paylar["0-14"], renk: "var(--iyi)", birim: "%"},
                {ad: "15-64", veri: b.yas.paylar["15-64"], renk: "var(--metin-sonuk)", birim: "%"},
                {ad: "65+", veri: b.yas.paylar["65+"], renk: "var(--vurgu)", birim: "%"},
            ]});
        if (Object.keys(b.yas.ortanca_yas).length) {
            cizgiGrafik(bolum, {ad: "Ortanca yaş", birim: "yaş",
                seriler: [{ad: "Ortanca yaş", veri: b.yas.ortanca_yas, renk: "var(--karsi)",
                           bicim: v => bir.format(v) + " yaş"}]});
        }
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
        const bolum = bolumYap(ana, n, "ÖLÜMLÜLÜK",
            `Ölüm sayısı ${imzaliYuzde((sayiSon / sayiIlk - 1) * 100, 0)}, ` +
            `ölümlülük ${imzaliYuzde((stdSon / kabaIlk - 1) * 100, 0)}`,
            `${ilkYil} yılında ${sayi.format(sayiIlk)} kişi öldü, ${sonYil} yılında ` +
            `${sayi.format(sayiSon)}. Bu artışa bakıp ölümlülüğün arttığını söylemek ` +
            `yanlış olur: nüfus yaşlandı ve ölümlerin çoğu yaşlılıkta olur.`);
        ray.push([n, "Ölümlülük"]);

        const acikla = el("details");
        acikla.append(el("summary", {}, "“Yaşa göre standartlaştırılmış hız” ne demek?"));
        const p1 = el("p");
        p1.innerHTML =
            `İki ili, ya da bir ilin iki farklı yılını karşılaştırırken sorun şu: ölüm ` +
            `riski yaşla birlikte katlanarak artar, ve iki nüfusun yaş dağılımı aynı ` +
            `değildir. Yaşlı bir nüfusta ölüm oranı, herkes daha sağlıklı olsa bile ` +
            `yüksek çıkar.`;
        const p2 = el("p");
        p2.innerHTML =
            `Standartlaştırma bunu ortadan kaldırır. Her yaş grubunun kendi ölüm hızı ` +
            `hesaplanır, sonra bu hızlar <b>ortak bir nüfusun</b> yaş dağılımıyla ` +
            `ağırlıklandırılır — burada ${b.olum.standart_yil} Türkiye'si. Sorulan soru ` +
            `şu: <i>“Nüfus ${b.olum.standart_yil}'daki gibi olsaydı, bu yılın ölüm ` +
            `hızlarıyla kaç kişi ölürdü?”</i> Geriye yalnız ölümlülüğün kendisi kalır.`;
        const p3 = el("p");
        p3.innerHTML =
            `Bu yüzden iki çizgi ${b.olum.standart_yil}'da çakışır — o yıl standart ` +
            `nüfusun kendisidir — ve sonra ayrılır. Aradaki mesafe <b>yaşlanmanın ` +
            `payıdır</b>. Kaba hız TÜİK'in yayımladığıdır; standartlaştırılmış hız bizim ` +
            `hesabımızdır ve karşılaştırma içindir, "kaç kişi öldü" sorusunun cevabı ` +
            `değildir.`;
        acikla.append(p1, p2, p3);
        bolum.append(acikla);

        cizgiGrafik(bolum, {ad: "Ölüm hızı", birim: "‰",
            bantlar: [{ad: "pandemi", baslangic: 2020, bitis: 2021}],
            seriler: [
                {ad: "Kaba ölüm hızı", veri: b.olum.kaba, renk: "var(--vurgu)",
                 bicim: v => iki.format(v) + "‰"},
                {ad: "Yaşa göre standart", veri: b.olum.standart, renk: "var(--karsi)",
                 kesik: true, bicim: v => iki.format(v) + "‰"},
            ],
            sutun: {ad: "Ölüm sayısı", veri: b.olum.sayi, renk: "var(--vurgu-koyu)", acik: false}});
        cikarim(bolum,
            `${sonYil}'te kaba hız <b>${iki.format(kabaSon)}‰</b>, yaşa göre ` +
            `standartlaştırılmış hız <b>${iki.format(stdSon)}‰</b>. Aradaki ` +
            `<b>${iki.format(kabaSon - stdSon)}‰</b>, tamamen nüfusun yaşlanmasıdır.`);

        const beklenen = {}, gerceklesen = {}, fazla = {};
        for (const [yil, kayit] of noktalar(b.olum.fazla)) {
            if (yil < b.olum.fazla_taban) continue;
            beklenen[yil] = kayit.beklenen;
            gerceklesen[yil] = kayit.gerceklesen;
            fazla[yil] = kayit.gerceklesen - kayit.beklenen;
        }
        cizgiGrafik(bolum, {ad: "Beklenen ve gerçekleşen ölüm", birim: "ölüm", kipler: false,
            seriler: [
                {ad: `Beklenen (${b.olum.fazla_taban} ölümlülüğüyle)`, veri: beklenen,
                 renk: "var(--karsi)", kesik: true},
                {ad: "Gerçekleşen", veri: gerceklesen, renk: "var(--vurgu)"},
            ]});
        const pandemi = Object.entries(fazla)
            .filter(([y]) => Number(y) >= 2020 && Number(y) <= 2021)
            .reduce((t, [, v]) => t + v, 0);
        const sonFazla = son(fazla)?.[1] ?? 0;
        cikarim(bolum,
            `${b.olum.fazla_taban}'un yaş-cinsiyet ölümlülüğü sabit tutulup her yılın ` +
            `kendi nüfusuna uygulanınca "beklenen ölüm" çıkıyor. 2020-2021'de ` +
            `<b>${imzali(pandemi, 0)}</b> fazla ölüm. ` +
            (sonFazla < 0
                ? `${son(fazla)[0]}'te <b>${sayi.format(Math.abs(Math.round(sonFazla)))} ` +
                  `eksik</b>: ölümlülük ${b.olum.fazla_taban}'un altına indi.`
                : ""));

        cizgiGrafik(bolum, {ad: "Yaş gruplarında ölüm hızı", birim: "‰", birimSag: "‰",
            seriler: [
                {ad: "65+", veri: b.olum.gruplar["65+"], renk: "var(--vurgu)",
                 bicim: v => iki.format(v) + "‰"},
                {ad: "15-64", veri: b.olum.gruplar["15-64"], renk: "var(--metin-sonuk)",
                 eksen: "sag", bicim: v => iki.format(v) + "‰"},
                {ad: "0-14", veri: b.olum.gruplar["0-14"], renk: "var(--iyi)",
                 eksen: "sag", bicim: v => iki.format(v) + "‰"},
            ]});
        cikarim(bolum, "65+ soldaki eksende, öteki ikisi sağdakinde: aralarında " +
            "<b>on beş kat</b> var ve aynı eksende çizilseler alttaki iki çizgi düz " +
            "bir zemin gibi görünürdü.");
    }
    // endregion

    // region 04 Doğurganlık
    if (b.dogurganlik) {
        const n = sonraki();
        const d = b.dogurganlik;
        const [ilkYil, dogumIlk] = ilk(d.dogum);
        const [sonYil, dogumSon] = son(d.dogum);
        const kadinIlk = d.kadin_15_49[ilkYil], kadinSon = d.kadin_15_49[sonYil];
        const gdhIlk = d.gdh[ilkYil], gdhSon = d.gdh[sonYil];
        const bolum = bolumYap(ana, n, "DOĞURGANLIK",
            "Doğum düşüşü, sayının gösterdiğinden derin",
            `Doğum sayısı ${ilkYil}-${sonYil} arasında ` +
            `${imzaliYuzde((dogumSon / dogumIlk - 1) * 100)} değişti. Ama doğurgan ` +
            `çağdaki kadın sayısı aynı sürede ` +
            `${imzaliYuzde((kadinSon / kadinIlk - 1) * 100)} değişti — yani paydası ` +
            `büyüyen bir kesirin payına bakıyoruz. <strong>Kadın başına</strong> değişim ` +
            `${imzaliYuzde((gdhSon / gdhIlk - 1) * 100)}.`);
        ray.push([n, "Doğurganlık"]);
        cizgiGrafik(bolum, {ad: "Doğurganlık", birim: "‰", birimSag: "doğum",
            seriler: [
                {ad: "Genel doğurganlık hızı", veri: d.gdh, renk: "var(--vurgu)",
                 bicim: v => iki.format(v) + "‰"},
                {ad: "Doğum sayısı", veri: d.dogum, renk: "var(--metin-sonuk)",
                 eksen: "sag", kesik: true},
            ],
            not: "Genel doğurganlık hızı: 15-49 yaş arası bin kadın başına doğum."});
        if (Object.keys(d.bebek_olum).length) {
            cizgiGrafik(bolum, {ad: "Bebek ölüm hızı", birim: "‰",
                seriler: [{ad: "Bebek ölüm hızı", veri: d.bebek_olum, renk: "var(--uyari)",
                           dolgu: true, bicim: v => bir.format(v) + "‰"}],
                not: "Bin canlı doğum başına, ilk yıl içinde ölen bebek sayısı."});
        }
    }
    // endregion

    // region 05 Yaşam süresi
    if (b.yasam) {
        const n = sonraki();
        const bolum = bolumYap(ana, n, "YAŞAM SÜRESİ",
            "Beklenen ömür, doğuşta ve 65 yaşında",
            "Dönemin ölüm hızları hiç değişmezse beklenen yıl sayısı. Bir öngörü değil, " +
            "bugünkü ölümlülüğün tek sayıya indirilmiş hâli. <strong>65 yaşındaki biri " +
            "için beklenen süre ayrı hesaplanır</strong> — bebek ölümlerini geride " +
            "bırakmıştır, o yüzden doğuştakinden farklıdır.");
        ray.push([n, "Yaşam süresi"]);
        if (b.yasam["0"]) {
            cizgiGrafik(bolum, {ad: "Doğuşta beklenen yaşam süresi", birim: "yıl",
                seriler: [
                    {ad: "Kadın", veri: b.yasam["0"].female, renk: "var(--karsi)",
                     bicim: v => bir.format(v) + " yıl"},
                    {ad: "Erkek", veri: b.yasam["0"].male, renk: "var(--vurgu)",
                     bicim: v => bir.format(v) + " yıl"},
                ]});
        }
        if (b.yasam["65"]) {
            cizgiGrafik(bolum, {ad: "65 yaşında beklenen kalan ömür", birim: "yıl",
                seriler: [
                    {ad: "Kadın", veri: b.yasam["65"].female, renk: "var(--karsi)",
                     bicim: v => bir.format(v) + " yıl"},
                    {ad: "Erkek", veri: b.yasam["65"].male, renk: "var(--vurgu)",
                     bicim: v => bir.format(v) + " yıl"},
                ]});
            const k = son(b.yasam["65"].female)?.[1], e = son(b.yasam["65"].male)?.[1];
            if (k && e) {
                cikarim(bolum, `65 yaşına gelen bir kadını ortalama <b>${bir.format(k)}</b> ` +
                    `yıl, bir erkeği <b>${bir.format(e)}</b> yıl bekliyor. Aradaki ` +
                    `<b>${bir.format(k - e)} yıl</b>, yaşlılıkta dulluğun neden ağırlıklı ` +
                    `olarak kadınların meselesi olduğunun yarısı; öteki yarısı kadınların ` +
                    `kendilerinden büyük biriyle evlenmesi.`);
            }
        }
    }
    // endregion

    // region 06 Göç
    if (b.goc) {
        const n = sonraki();
        const bolum = bolumYap(ana, n, "GÖÇ",
            b.goc.bantlar ? "Kim geliyor, kim gidiyor" : "Yurt dışıyla olan akış",
            b.goc.bantlar
                ? "Gelen ve giden, <strong>yaşa göre</strong>. Bir yerin nüfusu doğal " +
                  "artışı artı olduğu hâlde düşüyorsa cevap burada: hangi yaş gidiyor."
                : "Ülke düzeyinde iller arası göç tanımsızdır — bir ilden ötekine taşınmak " +
                  "ülkeye giriş değildir. Burada <strong>yurt dışıyla</strong> olan akış var.");
        ray.push([n, "Göç"]);
        if (b.goc.bantlar) {
            gocProfili(bolum, b.goc);
            if (Object.keys(b.goc.net || {}).length) {
                cizgiGrafik(bolum, {ad: "Net göç", birim: "kişi", kipler: false,
                    seriler: [{ad: "Net göç", veri: b.goc.net, renk: "var(--karsi)",
                               sifirdan: true}]});
            }
        }
        if (b.goc.yurtdisi && Object.keys(b.goc.yurtdisi.gelen).length) {
            cizgiGrafik(bolum, {ad: "Yurt dışı göçü", birim: "kişi",
                seriler: [
                    {ad: "Yurt dışından gelen", veri: b.goc.yurtdisi.gelen, renk: "var(--iyi)"},
                    {ad: "Yurt dışına giden", veri: b.goc.yurtdisi.giden, renk: "var(--uyari)"},
                ]});
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
        const bolum = bolumYap(ana, n, "EVLİLİK",
            "Evlilik azalıyor, boşanma artıyor, yaş yükseliyor",
            `Sayılar değil hızlar: nüfus büyürken sabit kalan bir evlenme sayısı aslında ` +
            `düşüştür. ${ilkYil}-${sonYil} arasında kaba evlenme hızı ` +
            `<strong>${iki.format(evIlk)}‰ → ${iki.format(evSon)}‰</strong>, boşanma ` +
            `<strong>${iki.format(boIlk)}‰ → ${iki.format(boSon)}‰</strong>.`);
        ray.push([n, "Evlilik"]);
        cizgiGrafik(bolum, {ad: "Evlenme ve boşanma hızı", birim: "‰",
            seriler: [
                {ad: "Evlenme hızı", veri: e.evlenme_hizi, renk: "var(--vurgu)",
                 bicim: v => iki.format(v) + "‰"},
                {ad: "Boşanma hızı", veri: e.bosanma_hizi, renk: "var(--uyari)",
                 bicim: v => iki.format(v) + "‰"},
            ],
            not: "Bin kişi başına. Evlenme olayın yerine göre sayılır, ikametgaha göre değil."});
        if (e.ilk_evlenme_yasi?.male) {
            cizgiGrafik(bolum, {ad: "Ortalama ilk evlenme yaşı", birim: "yaş",
                seriler: [
                    {ad: "Erkek", veri: e.ilk_evlenme_yasi.male, renk: "var(--vurgu)",
                     bicim: v => bir.format(v)},
                    {ad: "Kadın", veri: e.ilk_evlenme_yasi.female, renk: "var(--karsi)",
                     bicim: v => bir.format(v)},
                ]});
        }
        if (e.medeni_pay?.female) {
            bolum.append(medeniTablo(e.medeni_pay));
            const dulK = son(e.medeni_pay.female["Eşi öldü"])?.[1];
            const dulE = son(e.medeni_pay.male["Eşi öldü"])?.[1];
            if (dulK && dulE) {
                cikarim(bolum, `Eşi ölmüş kadın oranı <b>%${iki.format(dulK)}</b>, erkek ` +
                    `<b>%${iki.format(dulE)}</b> — <b>${bir.format(dulK / dulE)} katı</b>. ` +
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
        const bolum = bolumYap(ana, n, "HANEHALKI",
            "Hane küçülüyor, hane sayısı artıyor",
            `Ortalama hanehalkı ${ilkYil}'de ${iki.format(ilkBoy)} kişiydi, ${sonYil}'te ` +
            `<strong>${iki.format(sonBoy)}</strong>. Aynı nüfus daha çok eve bölünüyor: ` +
            `konut talebinin nüfus artışından bağımsız bir bileşeni var ve o bu satırda.`);
        ray.push([n, "Hanehalkı"]);
        cizgiGrafik(bolum, {ad: "Hanehalkı", birim: "kişi", birimSag: "hane",
            seriler: [
                {ad: "Ortalama hanehalkı", veri: b.hane.buyukluk, renk: "var(--vurgu)",
                 bicim: v => iki.format(v) + " kişi"},
                ...(Object.keys(b.hane.sayi).length
                    ? [{ad: "Hane sayısı", veri: b.hane.sayi, renk: "var(--karsi)",
                        eksen: "sag", kesik: true}] : []),
            ]});
    }
    // endregion

    const sira = siralamaBolumu(ana, veri.alan, siralama, dizin);
    if (sira) ray.push(["★", sira[1]]);

    if (veri.eksik.length) {
        const not = el("div", {class: "eksik-not"});
        not.innerHTML = "<b>Bu düzeyde olmayanlar:</b> " +
            veri.eksik.map(a => EKSIK[a] || a).join(", ") +
            ". Eksik değil — kaynak bu düzeyde yayımlamıyor.";
        ana.append(not);
    }

    const alt = el("footer");
    alt.append(
        el("span", {}, `veriatlas · ${veri.alan.ad} · ${DUZEY[veri.alan.duzey]}`),
        el("span", {}, "Ölüm ve doğum ikametgaha, evlenme olayın yerine göre"),
        el("span", {}, "Standartlaştırılmış hız bizim hesabımızdır"),
    );
    ana.append(alt);

    rayCiz(ray);
}

function rayCiz(bolumler) {
    const ray = document.getElementById("ray");
    ray.textContent = "";
    const ol = el("ol");
    for (const [no, ad] of bolumler) {
        const hedef = no === "★" ? "b-siralama" : "b" + no;
        const bag = el("a", {href: "#" + hedef});
        bag.dataset.hedef = hedef;
        bag.append(el("span", {class: "kare"}, no), el("span", {}, ad));
        ol.append(bag);
    }
    ray.append(ol);
    izle();
}

/** Which section the reader is in, and everything above it marked as passed — the rail is
 *  a progress bar, so a section already read should not look the same as one not reached. */
function izle() {
    const baglar = [...document.querySelectorAll("#ray a")];
    const gozlemci = new IntersectionObserver((girisler) => {
        for (const giris of girisler) {
            if (!giris.isIntersecting) continue;
            const sira = baglar.findIndex(a => a.dataset.hedef === giris.target.id);
            baglar.forEach((bag, i) => {
                bag.classList.toggle("etkin", i === sira);
                bag.classList.toggle("gecildi", i < sira);
            });
        }
    }, {rootMargin: "-20% 0px -70% 0px"});
    for (const bag of baglar) {
        const hedef = document.getElementById(bag.dataset.hedef);
        if (hedef) gozlemci.observe(hedef);
    }
}

function medeniTablo(paylar) {
    const kutu = el("div", {class: "tablo-kutu"});
    const tablo = el("table");
    const durumlar = Object.keys(paylar.female);
    const yil = son(paylar.female[durumlar[0]])[0];
    const bas = el("thead"), satir = el("tr");
    satir.append(el("th", {}, `Medeni durum · ${yil}`), el("th", {}, "Kadın"),
                 el("th", {}, "Erkek"), el("th", {}, "Fark"));
    bas.append(satir);
    const govde = el("tbody");
    for (const durum of durumlar) {
        const k = son(paylar.female[durum])?.[1] ?? 0;
        const e = son(paylar.male[durum])?.[1] ?? 0;
        const tr = el("tr");
        tr.append(el("td", {}, durum), el("td", {}, "%" + iki.format(k)),
                  el("td", {}, "%" + iki.format(e)), el("td", {}, imzali(k - e, 2) + " puan"));
        govde.append(tr);
    }
    tablo.append(bas, govde);
    kutu.append(tablo);
    return kutu;
}

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

// endregion

// region Yükleme

let siralamaVerisi = null, dizinVerisi = [];

async function hazirlik() {
    const [geo, sira, dizin] = await Promise.all([
        fetch("../../public/areas.geojson").then(c => c.json()).catch(() => null),
        fetch("../../public/rapor/siralama.json").then(c => c.json()).catch(() => null),
        fetch("../../public/rapor/dizin.json").then(c => c.json()).catch(() => []),
    ]);
    geometri = geo;
    siralamaVerisi = sira;
    dizinVerisi = dizin;
}

async function yukle(areaId) {
    const govde = document.getElementById("govde");
    govde.textContent = "";
    govde.append(el("p", {class: "giris"}, "Yükleniyor…"));
    try {
        const cevap = await fetch(`../../public/rapor/${areaId}.json`);
        if (!cevap.ok) throw new Error(String(cevap.status));
        ciz(await cevap.json(), siralamaVerisi, dizinVerisi);
        window.scrollTo({top: 0});
    } catch {
        govde.textContent = "";
        govde.append(el("h1", {}, "Bu alanın raporu yok"));
        govde.append(el("p", {class: "giris"},
            `${areaId} için sayfa üretilmedi. scripts/build_report_data.py ${areaId} üretir.`));
    }
}

const alanId = () => (/a=([A-Z0-9-]+)/.exec(location.hash) || [, "TR"])[1];

window.addEventListener("hashchange", () => yukle(alanId()));
hazirlik().then(() => yukle(alanId()));

// endregion
