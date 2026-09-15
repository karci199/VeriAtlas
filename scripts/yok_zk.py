"""Headless client for YÖK İstatistik (istatistik.yok.gov.tr), a ZK 8 application.

The page ships its widget tree as JavaScript (`zkmx([...])`): every widget with its uuid and
label. A click is a form POST to `/zkau` (`dtid`, `cmd_0`, `uuid_0`, `data_0`); the answer is
JSON whose commands carry the new widgets (same JavaScript notation) and, for an export
button, a `download` command with a session-bound URL. Uuids are made per session, so widgets
are found by label, never hard-coded.
"""

from __future__ import annotations

import re

import httpx

BASE = "https://istatistik.yok.gov.tr"
CLICK = '{"pageX":10,"pageY":10,"which":1,"x":5,"y":5}'
WIDGET = re.compile(r"\['(zul\.[\w.]+)','(\w+)',\{((?:[^{}]|\{[^{}]*\})*)\}")
LABEL = re.compile(r"(?:label|value):'((?:[^'\\]|\\.)*)'")
SRC = re.compile(r"src:'((?:[^'\\]|\\.)*)'")


def unescape(text: str) -> str:
    """JavaScript string escapes (\\xE7, \\u011F, \\x2F) to characters."""
    return re.sub(
        r"\\x([0-9A-Fa-f]{2})|\\u([0-9A-Fa-f]{4})",
        lambda m: chr(int(m.group(1) or m.group(2), 16)),
        text,
    ).replace("\\'", "'")


class YokStat:
    def __init__(self) -> None:
        self.client = httpx.Client(
            headers={"User-Agent": "Mozilla/5.0"}, timeout=120, follow_redirects=True
        )
        page = self.client.get(BASE + "/").text
        self.dtid = re.search(r"dt:'([^']+)'", page).group(1)
        self.text = page
        # ZK numbers requests; a repeated number is answered with the previous reply.
        self.sid = 0

    def widgets(self, text: str | None = None) -> list[tuple[str, str, str, str]]:
        """(type, uuid, label, src) in document order."""
        out = []
        for kind, uuid, props in WIDGET.findall(
            text if text is not None else self.text
        ):
            label = LABEL.search(props)
            src = SRC.search(props)
            out.append(
                (
                    kind,
                    uuid,
                    unescape(label.group(1)) if label else "",
                    unescape(src.group(1)) if src else "",
                )
            )
        return out

    def next_sid(self) -> int:
        self.sid += 1
        return self.sid

    def click(self, uuid: str) -> str:
        response = self.client.post(
            BASE + "/zkau",
            data={
                "dtid": self.dtid,
                "cmd_0": "onClick",
                "uuid_0": uuid,
                "data_0": CLICK,
            },
            headers={
                "ZK-SID": str(self.next_sid()),
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        response.raise_for_status()
        self.text = self.text + "\n" + response.text
        return response.text

    def find(self, label: str, kind: str = "") -> str:
        for k, uuid, text, _ in reversed(self.widgets()):
            if text == label and kind in k:
                return uuid
        raise KeyError(f"YÖK İstatistik: {label!r} bulunamadı")

    def excel(self, label: str, answer: str) -> tuple[str, bytes]:
        """Click the xls icon beside a table label in `answer`; return (file name, bytes)."""
        found = self.widgets(answer)
        index = next(
            (i for i, (_, _, text, _) in enumerate(found) if text.strip() == label),
            None,
        )
        if index is None:
            raise KeyError(f"tablo yok: {label!r}")
        icon = next(
            uuid for _, uuid, _, src in found[index + 1 :] if src.endswith("xls.png")
        )
        reply = self.click(icon)
        # The answer is JavaScript object notation, not JSON; the download command is plain.
        found_url = re.search(r'\["download",\s*\[\s*["\']([^"\']+)["\']', reply)
        if not found_url:
            raise ValueError(f"indirme komutu yok: {reply[:200]}")
        url = unescape(found_url.group(1)).replace(r"\/", "/")
        data = self.client.get(httpx.URL(BASE + "/").join(url))
        data.raise_for_status()
        return url.rsplit("/", 1)[-1], data.content
