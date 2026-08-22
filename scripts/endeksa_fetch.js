/**
 * Endeksa district dump — run inside a logged-in endeksa.com tab.
 *
 * Usage (browser console or Claude's javascript_tool), on a page such as
 *   https://www.endeksa.com/tr/analiz/turkiye/bursa/iznik/demografi
 *
 *   endeksaFetch.start()            // detects CityId/CountyId from the page cache
 *   endeksaFetch.start({cityId: 6, countyId: 2034})   // or pass explicitly
 *   endeksaFetch.status()           // progress
 *   endeksaFetch.download()         // user's own browser: saves <district>.json
 *   endeksaFetch.chunk(i, 60000)    // Claude's panel: pull the JSON string in slices
 *
 * Output object (window.__endeksa):
 *   { meta, county, quarters{DistrictId: ...}, election{county, quarters},
 *     fellows{county, quarters}, geo }
 *
 * Notes — see docs/endeksa.md:
 *   - demography/Values and geo/map are AES-encrypted; the page's
 *     window.encodeResponse decrypts. election and fellowcountryman are plain.
 *   - Requests are throttled (DELAY_MS); bursts get the session cut for minutes.
 *   - Quarters with HouseholdCount == 0 are placeholders (no neighbourhood data).
 */
(function () {
  const DELAY_MS = 2800;
  const RETRY_MS = 6000;
  const RETRIES = 3;
  const BASE = "https://app.endeksa.com";

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const token = () => localStorage.getItem("accessToken").replace(/^"|"$/g, "");
  const parse = (text) => {
    try {
      return JSON.parse(text);
    } catch (e) {
      return JSON.parse(window.encodeResponse(JSON.parse(text)));
    }
  };

  async function get(path, params) {
    const q = Object.entries(params)
      .map(([k, v]) => k + "=" + encodeURIComponent(v))
      .join("&");
    const url = BASE + path + "?" + q;
    let lastErr;
    for (let i = 0; i < RETRIES; i++) {
      try {
        const r = await fetch(url, { headers: { Authorization: "Bearer " + token() } });
        if (!r.ok) throw new Error("HTTP " + r.status);
        return parse(await r.text());
      } catch (e) {
        lastErr = e;
        await sleep(RETRY_MS);
      }
    }
    throw lastErr;
  }

  function detectIds() {
    const key = Object.keys(localStorage).find((k) =>
      /Demographies\.data\..*demography\/Values\?CityId=\d+&CountryId=1&CountyId=\d+&Level=2$/.test(k)
    );
    if (!key) return null;
    const m = key.match(/CityId=(\d+)&CountryId=1&CountyId=(\d+)/);
    return { cityId: +m[1], countyId: +m[2] };
  }

  const state = { running: false, step: "", done: 0, total: 0, failed: [] };

  async function start(opts) {
    const ids = opts && opts.cityId ? opts : detectIds();
    if (!ids) throw new Error("CityId/CountyId not found — open the district demography page first or pass ids");
    const { cityId, countyId } = ids;
    const base = { CityId: cityId, CountryId: 1, CountyId: countyId };
    const out = {
      meta: { cityId, countyId, fetched: new Date().toISOString().slice(0, 10), url: location.href },
      county: null, quarters: {}, election: { county: null, quarters: {} },
      fellows: { county: null, quarters: {} }, geo: null,
    };
    window.__endeksa = out;
    Object.assign(state, { running: true, done: 0, failed: [], step: "county" });

    out.county = await get("/demography/Values", { ...base, Level: 2 });
    const subs = out.county.SubRegionals || [];
    const ids3 = subs.map((s) => s.DistrictId);
    state.total = ids3.length * 3 + 3;
    await sleep(DELAY_MS);

    const steps = [
      ["quarters", "/demography/Values", (o) => o.quarters],
      ["election", "/election", (o) => o.election.quarters],
      ["fellows", "/fellowcountryman", (o) => o.fellows.quarters],
    ];
    for (const [name, path, slot] of steps) {
      state.step = name;
      for (const id of ids3) {
        try {
          slot(out)[id] = await get(path, { ...base, DistrictId: id, Level: 3 });
        } catch (e) {
          state.failed.push(name + ":" + id);
        }
        state.done++;
        await sleep(DELAY_MS);
      }
    }
    state.step = "county election/fellows/geo";
    try { out.election.county = await get("/election", { ...base, Level: 2 }); } catch (e) { state.failed.push("election:county"); }
    state.done++; await sleep(DELAY_MS);
    try { out.fellows.county = await get("/fellowcountryman", { ...base, Level: 2 }); } catch (e) { state.failed.push("fellows:county"); }
    state.done++; await sleep(DELAY_MS);
    try {
      out.geo = await get("/geo/map", {
        cityId, countryId: 1, countyId, districtId: ids3[0], level: 2, subGeometries: true,
      });
    } catch (e) { state.failed.push("geo"); }
    state.done++;
    state.running = false;
    state.step = "done";
    return status();
  }

  function status() {
    return JSON.stringify({ ...state, quarters: Object.keys((window.__endeksa || {}).quarters || {}).length });
  }

  function json() {
    return JSON.stringify(window.__endeksa);
  }

  function chunk(i, size) {
    size = size || 60000;
    const s = json();
    // pad so the tool result is persisted to a file instead of the context
    return { n: Math.ceil(s.length / size), text: s.slice(i * size, (i + 1) * size) + " ".repeat(80000) };
  }

  function download() {
    const s = json();
    const m = window.__endeksa.meta;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([s], { type: "application/json" }));
    a.download = "endeksa-" + m.cityId + "-" + m.countyId + ".json";
    a.click();
  }

  window.endeksaFetch = { start, status, json, chunk, download, detectIds };
  return "endeksaFetch ready: " + JSON.stringify(detectIds());
})();
