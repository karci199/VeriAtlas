"""A small headless client for TÜİK's ZK 3 election application.

The application is meant to be driven from a browser, one report at a time. It answers
plain HTTP just as well, which is the whole point: no browser, no supervision, a report
every few seconds instead of every minute.

Two things make it awkward and both are handled here:

  * component ids are regenerated per session, so nothing may be hard-coded — listboxes
    are found by their header text, radios and buttons by their label, exactly as a
    person would
  * the server answers an event with DOM commands. `outer` replaces a subtree; the
    `z.chchg` marker means "this widget's children changed" and must be followed by a
    `redraw` request to receive them. Rather than keep a real DOM, redrawn fragments are
    appended and later ones shadow earlier ones.

Rewritten from scratch on 2026-09-07: the original lived in the data directory and was
deleted with it. Tools belong in the repository, data outside it.
"""

from __future__ import annotations

import http.cookiejar
import re
import urllib.parse
import urllib.request

BASE = "https://biruni.tuik.gov.tr/secimdagitimapp/"
UA = "Mozilla/5.0"

RE_DTID = re.compile(r'z\.dtid="([^"]+)"')
RE_OUTER = re.compile(
    r"<c>outer</c>\s*<d>[^<]*</d>\s*<d><!\[CDATA\[(.*?)\]\]></d>", re.DOTALL
)
RE_REDIRECT = re.compile(r"<c>redirect</c>\s*<d>(?:<!\[CDATA\[)?([^<\]]+)", re.DOTALL)
RE_CHCHG = re.compile(r"<d>(z_\w+)</d>\s*<d>z\.chchg</d>")
RE_LISTBOX = re.compile(
    r'<div id="(z_[\w]+)!head".*?z\.type="Lhr"[^>]*>([^<]{2,60})</th>', re.DOTALL
)
RE_ITEM = re.compile(
    r'<tr id="(z_[\w]+)" z\.type="Lit"[^>]*>\s*<td[^>]*>(.*?)</td>', re.DOTALL
)
RE_RADIO = re.compile(
    r'<span id="(z_[\w]+)" z\.type="zul\.widget\.Radio".*?<label[^>]*>(.*?)</label>',
    re.DOTALL,
)
RE_BUTTON = re.compile(
    r'<button[^>]*id="(z_[\w]+)"[^>]*z\.type="zul\.widget\.Button"[^>]*>\s*(.*?)\s*</button>',
    re.DOTALL,
)
RE_SPAN = re.compile(r'<span id="(z_[\w]+)"[^>]*>([^<]{3,70})</span>')


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()


class ZK:
    """One session on one page of the application."""

    def __init__(self, page: str = "secim.zul", timeout: int = 120):
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.opener.addheaders = [("User-Agent", UA)]
        # The section pages are served inside a session that has seen the front page; asked
        # for cold they answer an empty document.
        if page != "secim.zul":
            self.opener.open(BASE, timeout=timeout).read()
        html = (
            self.opener.open(BASE + page, timeout=timeout)
            .read()
            .decode("utf-8", "replace")
        )
        self.fragments = [html]
        self.dtid = RE_DTID.search(html).group(1)
        self.redirect: str | None = None

    # -- transport ---------------------------------------------------------
    def event(self, uuid: str, command: str, data: str | None = None) -> str:
        fields = [("dtid", self.dtid), ("cmd.0", command), ("uuid.0", uuid)]
        if data is not None:
            fields.append(("data.0", data))
        request = urllib.request.Request(
            BASE + "zkau",
            data=urllib.parse.urlencode(fields).encode(),
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "ZK-SID": "1",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": UA,
            },
        )
        body = (
            self.opener.open(request, timeout=self.timeout)
            .read()
            .decode("utf-8", "replace")
        )
        self.fragments.extend(RE_OUTER.findall(body))
        found = RE_REDIRECT.search(body)
        if found:
            self.redirect = found.group(1).strip()
        return body

    def settle(self, body: str, depth: int = 0) -> None:
        """Follow `z.chchg` markers with redraw requests until the tree stops changing."""
        for uuid in dict.fromkeys(RE_CHCHG.findall(body)):
            if depth < 6:
                self.settle(self.event(uuid, "redraw"), depth + 1)

    @property
    def html(self) -> str:
        return "\n".join(self.fragments)

    # -- finding things ----------------------------------------------------
    def listboxes(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for uuid, header in RE_LISTBOX.findall(self.html):
            out.setdefault(text_of(header), []).append(uuid)
        return out

    def items(self, listbox: str) -> dict[str, str]:
        """{label: item uuid} for one listbox — a later fragment shadows an earlier one."""
        out: dict[str, str] = {}
        for fragment in self.fragments:
            marker = f'id="{listbox}'
            if marker not in fragment:
                continue
            body = fragment[fragment.find(marker) :]
            for uuid, cell in RE_ITEM.findall(body):
                label = text_of(cell)
                if label:
                    out[label] = uuid
        return out

    def options(self, header: str) -> tuple[str | None, dict[str, str]]:
        """The populated listbox under this header: (uuid, {label: item uuid})."""
        best: tuple[str | None, dict[str, str]] = (None, {})
        for uuid in self.listboxes().get(header, []):
            found = self.items(uuid)
            if len(found) > len(best[1]):
                best = (uuid, found)
        return best

    def widgets(self, kind: str) -> dict[str, str]:
        pattern = RE_RADIO if kind == "Radio" else RE_BUTTON
        return {text_of(label): uuid for uuid, label in pattern.findall(self.html)}

    # -- acting ------------------------------------------------------------
    def pick(self, header: str, label: str, exact: bool = False) -> str:
        listbox, found = self.options(header)
        key = label if label in found else None
        if key is None and not exact:
            key = next((k for k in found if k.startswith(label)), None)
        if key is None:
            raise KeyError(f"{header!r}: {label!r} yok ({len(found)} oge)")
        self.settle(self.event(listbox, "onSelect", found[key]))
        return key

    def check(self, label: str) -> None:
        radios = self.widgets("Radio")
        uuid = radios.get(label) or next(
            (v for k, v in radios.items() if k.startswith(label)), None
        )
        if uuid is None:
            raise KeyError(f"radyo yok: {label!r}")
        self.settle(self.event(uuid, "onCheck", "true"))

    def click(self, label: str) -> None:
        buttons = self.widgets("Button")
        uuid = buttons.get(label) or next(
            (v for k, v in buttons.items() if k.startswith(label)), None
        )
        if uuid is None:
            raise KeyError(f"dugme yok: {label!r}")
        self.redirect = None
        self.settle(self.event(uuid, "onClick"))

    def menu(self, label: str) -> str:
        """Front-page menu items are spans, not buttons; a click answers a page name."""
        for uuid, text in RE_SPAN.findall(self.html):
            if text_of(text).startswith(label):
                self.redirect = None
                self.event(uuid, "onClick")
                return self.redirect or ""
        raise KeyError(f"menu ogesi yok: {label!r}")
