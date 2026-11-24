#!/usr/bin/env python3
"""Build the 24-slide English PowerPoint deck with the Python standard library.

The output is a native OOXML .pptx package. No third-party slide library is
used. PowerPoint COM was avoided because the installed Office build shows a
product-activation dialog that rejects automation calls.
"""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "presentation" / "FinTech_API_Gateway.pptx"
SHOTS = ROOT / "screenshots"

EMU = 12700  # 1 point = 12700 EMU
SLIDE_W = 960
SLIDE_H = 540

BG = "090F1C"
CARD = "111C2E"
CARD2 = "17263E"
BORDER = "263954"
CYAN = "22D3EE"
AMBER = "F59E0B"
GREEN = "34D399"
RED = "F87171"
PURPLE = "A78BFA"
WHITE = "EBEFF5"
TEXT = "CBD5E1"
MUTED = "94A3B8"
DARK = "090F1C"

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


def e(value: float) -> int:
    return int(round(value * EMU))


def t(text: object) -> str:
    return escape(str(text))


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        handle.read(16)
        return struct.unpack(">II", handle.read(8))


class Slide:
    def __init__(self, index: int) -> None:
        self.index = index
        self.shapes: list[str] = []
        self.images: list[tuple[str, Path]] = []
        self._next_id = 2

    def _id(self) -> int:
        value = self._next_id
        self._next_id += 1
        return value

    def _text_body(
        self,
        text: str,
        size: float,
        color: str,
        bold: bool,
        align: str,
        font: str,
        anchor: str = "t",
    ) -> str:
        parts: list[str] = []
        for i, line in enumerate(str(text).split("\n")):
            if i:
                parts.append("<a:br/>")
            parts.append(
                '<a:r><a:rPr lang="en-US" sz="{}" b="{}">'
                '<a:solidFill><a:srgbClr val="{}"/></a:solidFill>'
                '<a:latin typeface="{}"/></a:rPr><a:t>{}</a:t></a:r>'.format(
                    int(round(size * 100)),
                    1 if bold else 0,
                    color,
                    t(font),
                    t(line),
                )
            )
        return (
            '<p:txBody><a:bodyPr wrap="square" lIns="0" rIns="0" tIns="0" '
            'bIns="0" anchor="{}"/><a:lstStyle/><a:p><a:pPr algn="{}"/>{}</a:p>'
            "</p:txBody>".format(anchor, align, "".join(parts))
        )

    def shape(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: str | None = None,
        line: str | None = None,
        radius: bool = False,
        oval: bool = False,
        text: str = "",
        size: float = 11,
        color: str = TEXT,
        bold: bool = False,
        align: str = "l",
        font: str = "Segoe UI",
        anchor: str = "t",
    ) -> None:
        sid = self._id()
        prst = "ellipse" if oval else ("roundRect" if radius else "rect")
        fill_xml = (
            '<a:solidFill><a:srgbClr val="{}"/></a:solidFill>'.format(fill)
            if fill
            else "<a:noFill/>"
        )
        line_xml = (
            '<a:ln w="12700"><a:solidFill><a:srgbClr val="{}"/></a:solidFill></a:ln>'.format(line)
            if line
            else "<a:ln><a:noFill/></a:ln>"
        )
        body = self._text_body(text, size, color, bold, align, font, anchor) if text else ""
        self.shapes.append(
            '<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="Shape {sid}"/>'
            '<p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
            '<a:prstGeom prst="{prst}"><a:avLst/></a:prstGeom>{fill}{line}</p:spPr>{body}</p:sp>'.format(
                sid=sid,
                x=e(x),
                y=e(y),
                w=e(w),
                h=e(h),
                prst=prst,
                fill=fill_xml,
                line=line_xml,
                body=body,
            )
        )

    def text(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        value: str,
        size: float = 11,
        color: str = TEXT,
        bold: bool = False,
        align: str = "l",
        font: str = "Segoe UI",
        anchor: str = "t",
    ) -> None:
        self.shape(
            x,
            y,
            w,
            h,
            text=value,
            size=size,
            color=color,
            bold=bold,
            align=align,
            font=font,
            anchor=anchor,
        )

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str = BORDER) -> None:
        if abs(y2 - y1) < 1:
            self.shape(min(x1, x2), y1, abs(x2 - x1), 1.5, fill=color)
        elif abs(x2 - x1) < 1:
            self.shape(x1, min(y1, y2), 1.5, abs(y2 - y1), fill=color)
        else:
            # Diagonal connectors are approximated with a thin rotated-free segment.
            self.shape(min(x1, x2), min(y1, y2), max(2, abs(x2 - x1)), 2, fill=color)

    def card(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        body: str,
        accent: str = CYAN,
    ) -> None:
        self.shape(x, y, w, h, fill=CARD, line=BORDER, radius=True)
        self.shape(x, y, 4, h, fill=accent)
        self.text(x + 16, y + 12, w - 28, 22, title, 14, accent, True)
        self.text(x + 16, y + 40, w - 28, h - 52, body, 10.5, TEXT)

    def bullets(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        items: list[str],
        size: float = 11,
        color: str = TEXT,
    ) -> None:
        bullet = "\u2022  "
        self.text(x, y, w, h, "\n".join(bullet + item for item in items), size, color)

    def code(self, x: float, y: float, w: float, h: float, value: str) -> None:
        self.shape(x, y, w, h, fill="050A14", line=BORDER, radius=True)
        self.text(x + 14, y + 12, w - 28, h - 24, value, 10, GREEN, font="Consolas")

    def picture(self, path: Path, x: float, y: float, max_w: float, max_h: float) -> None:
        if not path.is_file():
            self.shape(x, y, max_w, max_h, fill=CARD2, line=BORDER, radius=True)
            self.text(
                x,
                y + max_h / 2 - 10,
                max_w,
                20,
                "evidence png unavailable",
                10,
                MUTED,
                align="ctr",
            )
            return
        iw, ih = png_size(path)
        scale = min(max_w / iw, max_h / ih)
        pw, ph = iw * scale, ih * scale
        px, py = x + (max_w - pw) / 2, y + (max_h - ph) / 2
        rid = f"rId{len(self.images) + 2}"
        self.images.append((rid, path))
        sid = self._id()
        self.shapes.append(
            '<p:pic><p:nvPicPr><p:cNvPr id="{sid}" name="Evidence {sid}"/>'
            '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            '<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            '<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'.format(
                sid=sid,
                rid=rid,
                x=e(px),
                y=e(py),
                w=e(pw),
                h=e(ph),
            )
        )

    def xml(self) -> str:
        group = (
            '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sld xmlns:a="{a}" xmlns:r="{r}" xmlns:p="{p}">'
            "<p:cSld><p:spTree>{group}{shapes}</p:spTree></p:cSld>"
            "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
        ).format(
            a=A_NS,
            r=R_NS,
            p=P_NS,
            group=group,
            shapes="".join(self.shapes),
        )

    def rels_xml(self) -> str:
        rels = [
            '<Relationship Id="rId1" Type="{}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'.format(
                R_NS
            )
        ]
        for rid, path in self.images:
            rels.append(
                '<Relationship Id="{}" Type="{}/image" Target="../media/{}"/>'.format(
                    rid, R_NS, path.name
                )
            )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="{}">{}</Relationships>'.format(PKG_REL_NS, "".join(rels))
        )


def base_slide(slide: Slide, title: str, kicker: str, index: int, total: int) -> None:
    slide.shape(0, 0, SLIDE_W, SLIDE_H, fill=BG)
    slide.shape(0, 0, SLIDE_W, 5, fill=CYAN)
    slide.text(48, 20, 800, 18, kicker, 9.5, MUTED, True)
    slide.text(48, 42, 864, 44, title, 25, WHITE, True)
    slide.shape(48, 506, 864, 1, fill=BORDER)
    slide.text(48, 514, 600, 16, "Kong 3.9.1  |  FinTech API Gateway  |  Topic 17", 8.5, MUTED)
    slide.text(875, 514, 40, 16, f"{index:02d}", 9, CYAN, True, "r")
    slide.shape(0, 534, SLIDE_W * index / total, 6, fill=CYAN)


slides: list[Slide] = []
TOTAL = 24


def add(title: str, kicker: str) -> Slide:
    slide = Slide(len(slides) + 1)
    base_slide(slide, title, kicker, slide.index, TOTAL)
    slides.append(slide)
    return slide


# 01 — Title
s = add("FinTech API Gateway", "TOPIC 17  |  THEORETICAL + PRACTICAL PROTOTYPE")
s.text(48, 150, 700, 56, "Reverse Proxy Edge Gateway, Declarative DB-less", 28, CYAN, True)
s.text(48, 205, 700, 56, "Configuration, Token-Bucket Throttling & Resiliency", 28, AMBER, True)
s.text(48, 285, 760, 40, "Three Django / FastAPI upstreams. One Kong gateway. Verified evidence end to end.", 14, TEXT)
s.card(48, 360, 270, 90, "Team A", "Eya Derouiche\nContracts, topology, plugins", CYAN)
s.card(336, 360, 270, 90, "Team B", "Aya Fayachi\nDjango services, monitoring", GREEN)
s.card(624, 360, 270, 90, "Team C", "Wafe Bziouiche\nAnalyzer, alerts, metrics", PURPLE)
s.shape(800, 120, 120, 120, fill=CYAN, line=BORDER, oval=True)
s.text(800, 165, 120, 20, "KONG", 14, DARK, True, "ctr")

# 02 — Agenda
s = add("Roadmap of the presentation", "AGENDA")
agenda = [
    ("01", "Core concepts", "Gateway pattern, traffic direction, Kong entities"),
    ("02", "Algorithms", "Rate limiting and health-check circuit breaking"),
    ("03", "Custom diagrams", "Plugin phases, balancing ring, state diagram"),
    ("04", "Tools and install", "DB-less vs PostgreSQL, Compose, Admin API"),
    ("05", "Comparison matrix", "Kong vs Nginx vs Traefik / Envoy"),
    ("06", "Built system", "Steps 1-4, evidence, gates and next AI step"),
]
for i, (num, head, body) in enumerate(agenda):
    col, row = i % 2, i // 2
    accent = [CYAN, GREEN, AMBER, PURPLE, CYAN, GREEN][i]
    s.card(48 + col * 450, 110 + row * 125, 420, 100, head, num + "  " + body, accent)

# 03 — Definitions
s = add("Definitions & core concepts", "01  THEORY")
s.card(
    48, 110, 420, 160, "API Gateway Pattern",
    "A single edge entry point that centralises authentication, TLS, rate limiting, CORS, logging and routing. Backends keep focusing on business logic instead of repeating cross-cutting concerns.",
    CYAN,
)
s.card(
    492, 110, 420, 160, "North-South traffic",
    "Client-to-edge traffic: mobile apps, browsers or partners calling the public gateway on :8000 / :8443. Kong is the first service they reach.",
    GREEN,
)
s.card(
    48, 290, 420, 160, "East-West traffic",
    "Service-to-service traffic inside the cluster: n8n calling Alertmanager, Prometheus scraping Kong. Kong is not necessarily in every internal hop.",
    AMBER,
)
s.card(
    492, 290, 420, 160, "Why it matters here",
    "The professor's problem statement removes duplicated auth/TLS/limits from each Python service and places them in declarative Kong configuration.",
    PURPLE,
)

# 04 — Kong entities
s = add("Kong core entities used in this project", "01  THEORY")
entities = [
    ("Service", "accounts, payments, advisor, mock-upstream"),
    ("Route", "/api/accounts, /api/payments, /api/advisor, /mock"),
    ("Upstream", "round-robin virtual host for one service"),
    ("Target", "accounts-1:8000 and accounts-2:8000"),
    ("Consumer", "fintech-free and fintech-premium"),
    ("Plugin", "auth, limits, CORS, transform, logging, metrics"),
]
for i, (head, body) in enumerate(entities):
    col, row = i % 3, i // 3
    accent = [CYAN, GREEN, AMBER, PURPLE, CYAN, GREEN][i]
    s.card(48 + col * 296, 110 + row * 170, 272, 145, head, body, accent)

# 05 — Pipeline diagram
s = add("Custom diagram 1 - Kong plugin execution pipeline", "01  THEORY  /  DIAGRAM")
phases = ["certificate", "rewrite", "access", "header_filter", "body_filter", "log"]
for i, phase in enumerate(phases):
    x = 30 + i * 152
    s.shape(x, 140, 140, 54, fill=CARD2 if i == 4 else CARD, line=BORDER, radius=True)
    s.text(x, 152, 140, 20, phase, 11, CYAN, True, "ctr")
    if i < len(phases) - 1:
        s.line(x + 140, 167, x + 152, 167, AMBER)
s.text(48, 215, 864, 24, "TLS certificate -> early rewrite -> auth / rate limit -> response headers -> response body -> access-log write", 11, MUTED, align="ctr")
s.card(48, 270, 215, 140, "certificate", "TLS termination on :8443 with the demo localhost certificate (G5).", CYAN)
s.card(281, 270, 215, 140, "access", "key-auth, jwt, rate-limiting, token-bucket, request-size-limiting, CORS checks.", GREEN)
s.card(514, 270, 215, 140, "header_filter", "CORS + rate-limit headers: X-RateLimit-*, Retry-After, Kong-Request-ID.", AMBER)
s.card(747, 270, 165, 140, "log", "file-log writes C2 JSON lines to /var/log/kong/access.json.", PURPLE)

# 06 — Algorithms
s = add("Rate-limiting algorithms", "01  THEORY")
algos = [
    ("Fixed Window", "Counter resets at a fixed clock boundary.", "Built-in Kong: 10/min free, 100/min premium."),
    ("Sliding Window", "Weighted moving window smooths boundary bursts.", "Simulated in token_bucket_sim.py for theory."),
    ("Token Bucket", "Tokens refill at r/s; request consumes one token.", "Custom Kong plugin: 5@1/s and 50@10/s."),
    ("Leaky Bucket", "Requests drain at a constant output rate.", "Simulated for comparison; not deployed."),
]
for i, (head, mech, use) in enumerate(algos):
    s.card(48 + i * 222, 110, 198, 210, head, mech + "\n\nUsed here: " + use, [CYAN, GREEN, AMBER, PURPLE][i])
s.text(48, 350, 864, 70, "Key point: the built-in Kong plugin is fixed-window; the custom token-bucket plugin is deliberate because the professor names Token-Bucket Throttling in the core paradigm.", 12, TEXT)

# 07 — Health checks
s = add("Active / passive health checks = circuit breaking", "01  THEORY  /  RESILIENCY")
s.card(
    48, 110, 420, 180, "Active checks",
    "Every 5 s Kong requests /health on each target. Two successes mark a target healthy; two 5xx / TCP / timeout failures eject it from the ring.",
    CYAN,
)
s.card(
    492, 110, 420, 180, "Passive checks",
    "Real client traffic is inspected. Two 500/502/503/504, TCP failures or timeouts eject the target. HTTP 429 is NOT counted, so rate limiting cannot falsely open the circuit.",
    GREEN,
)
s.card(
    48, 310, 420, 130, "Kong-native behaviour",
    "No separate circuit-breaker plugin exists in this Kong OSS image. Upstream health checks + retries=2 provide the breaker behaviour.",
    AMBER,
)
s.card(
    492, 310, 420, 130, "Observability signal",
    "Prometheus alert KongCircuitOpen and n8n 10-circuit-open.json report the open state; they are signals, not the breaker itself.",
    PURPLE,
)

# 08 — Ring and state diagram
s = add("Custom diagram 2 - balancing ring & health state", "01  THEORY  /  DIAGRAM")
s.shape(70, 205, 110, 110, fill=CYAN, line=BORDER, oval=True)
s.text(70, 250, 110, 20, "KONG", 13, DARK, True, "ctr")
s.shape(245, 140, 100, 100, fill=GREEN, line=BORDER, oval=True)
s.text(245, 183, 100, 20, "accounts-1", 9, DARK, True, "ctr")
s.shape(245, 285, 100, 100, fill=AMBER, line=BORDER, oval=True)
s.text(245, 328, 100, 20, "accounts-2", 9, DARK, True, "ctr")
s.line(180, 250, 245, 190, CYAN)
s.line(180, 265, 245, 335, CYAN)
s.text(60, 400, 300, 40, "round-robin + weight 100/100 + retries=2", 10, MUTED, align="ctr")
states = [("HEALTHY", "receives traffic", GREEN), ("UNHEALTHY", "ejected from ring", RED), ("RECOVERED", "2 active successes", CYAN)]
for i, (head, body, accent) in enumerate(states):
    x = 430 + i * 170
    s.shape(x, 165, 145, 70, fill=accent, line=BORDER, radius=True)
    s.text(x, 180, 145, 20, head, 13, DARK, True, "ctr")
    s.text(x, 203, 145, 18, body, 9, DARK, align="ctr")
    if i < 2:
        s.line(x + 145, 200, x + 170, 200, TEXT)
s.text(430, 260, 484, 24, "2 failures (5xx / TCP / timeout) open the circuit. 429 is excluded.", 11, AMBER)
s.text(430, 292, 484, 24, "2 successful /health polls close it and restore the target.", 11, GREEN)

# 09 — Tools
s = add("Tools overview & installation stack", "02  TOOLS")
tools = [
    ("Kong OSS 3.9.1", "DB-less gateway, plugins, health checks"),
    ("Django", "Accounts + Payments services on PostgreSQL 16"),
    ("FastAPI", "Advisor service and verified analyzer"),
    ("Docker Compose", "core / monitoring / load / ai profiles"),
    ("k6 + Locust", "Concurrent load for chaos failover"),
    ("Prometheus + Alertmanager", "Metrics, 3 rules, inhibition, routing"),
    ("n8n", "3 active automation workflows"),
    ("PyJWT", "Demo token generator only; Kong validates"),
]
for i, (head, body) in enumerate(tools):
    col, row = i % 4, i // 4
    s.card(48 + col * 222, 110 + row * 170, 198, 145, head, body, [CYAN, GREEN, AMBER, PURPLE][i % 4])

# 10 — Install
s = add("DB-less installation steps (implemented)", "02  INSTALL")
s.code(
    48, 110, 864, 250,
    "# Windows PowerShell, from the repository root\n"
    "Copy-Item .env.example .env\n"
    "docker compose --profile core config\n"
    "docker compose --profile core up -d --build\n"
    "docker compose ps\n\n"
    "Invoke-RestMethod http://localhost:8000/mock/health\n"
    "docker compose exec kong kong config parse /etc/kong/kong.yml\n"
    "curl.exe http://127.0.0.1:8001/services\n"
    "curl.exe -X DELETE http://127.0.0.1:8001/services/mock-upstream   # 405",
)
s.card(48, 380, 420, 90, "Why DB-less?", "kong.yml is the single source of truth; no database migrations; CI can parse it deterministically.", CYAN)
s.card(492, 380, 420, 90, "Admin API rule", "Read-only in the demo. DELETE returns 405, proving configuration cannot drift from Git.", GREEN)

# 11 — DB-less vs Postgres
s = add("Kong DB-less vs PostgreSQL mode", "02  THEORY")
modes = [
    ["Aspect", "DB-less (implemented)", "PostgreSQL (theory only)"],
    ["Source of truth", "kong/kong.yml", "Kong database"],
    ["Admin API", "Read-only", "Read / write"],
    ["Bootstrap", "kong config parse + start", "kong migrations bootstrap"],
    ["Import", "YAML loaded at startup", "kong config db_import once"],
    ["Best fit", "Reproducible lab / CI / GitOps", "Long-lived dynamic platform"],
]
for r, row in enumerate(modes):
    y = 110 + r * 43
    widths = [180, 330, 354]
    x = 48
    for c, value in enumerate(row):
        fill = CYAN if r == 0 else (CARD if r % 2 == 0 else CARD2)
        color = DARK if r == 0 else (CYAN if c == 0 else TEXT)
        s.shape(x, y, widths[c], 43, fill=fill, line=BORDER)
        s.text(x + 6, y + 12, widths[c] - 12, 20, value, 10 if r == 0 else 9.5, color, r == 0 or c == 0)
        x += widths[c]
s.card(48, 392, 864, 80, "Decision DEC-022", "A/B/C chose theory only because the professor asks for an overview, not a practical DB-mode lab. C4 was patched 0.2.0 -> 0.2.1 to remove the unimplemented lab promise.", AMBER)

# 12 — Comparison matrix
s = add("Comparison matrix - Kong vs Nginx vs Traefik / Envoy", "02  THEORY")
matrix = [
    ["Criterion", "Kong OSS", "Nginx", "Traefik / Envoy"],
    ["Dynamic reload", "Declarative reload or DB Admin API", "Config reload", "Traefik auto; Envoy xDS"],
    ["Plugin ecosystem", "Lua hub + custom Lua", "Modules / OpenResty", "Middleware / filters"],
    ["L7 auth", "Key-Auth, JWT, ACL built in", "External or custom", "Middleware or ext_authz"],
    ["L7 rate limit", "Built-in + custom token bucket", "limit_req module", "Middleware or filters"],
    ["Footprint", "One gateway image; DB-less lean", "Very lean proxy", "Control + data plane"],
]
for r, row in enumerate(matrix):
    y = 110 + r * 50
    widths = [150, 238, 238, 238]
    x = 48
    for c, value in enumerate(row):
        fill = CYAN if r == 0 else (CARD if r % 2 == 0 else CARD2)
        color = DARK if r == 0 else (CYAN if c == 0 else TEXT)
        s.shape(x, y, widths[c], 50, fill=fill, line=BORDER)
        s.text(x + 6, y + 15, widths[c] - 12, 22, value, 10 if r == 0 else 9.5, color, r == 0 or c == 0)
        x += widths[c]
s.text(48, 430, 864, 40, "Conclusion: Kong is the best fit because auth, JWT, limits, CORS and transformation are first-class declarative plugins.", 11, CYAN, True)

# 13 — Built architecture
s = add("Illustrative built example - Enterprise FinTech API", "03  BUILT SYSTEM")
s.shape(48, 190, 110, 110, fill=CYAN, line=BORDER, oval=True)
s.text(48, 235, 110, 20, "Clients", 11, DARK, True, "ctr")
s.shape(210, 175, 140, 140, fill=AMBER, line=BORDER, oval=True)
s.text(210, 235, 140, 20, "KONG :8000", 12, DARK, True, "ctr")
s.line(158, 245, 210, 245, CYAN)
for i, (head, sub) in enumerate([("Accounts", "2 replicas"), ("Payments", "2 replicas"), ("Advisor", "2 replicas")]):
    y = 110 + i * 125
    s.shape(420, y, 100, 100, fill=GREEN, line=BORDER, oval=True)
    s.text(420, y + 38, 100, 20, head, 10, DARK, True, "ctr")
    s.text(530, y + 30, 120, 20, sub, 9, MUTED)
    s.line(350, 245, 420, y + 50, GREEN)
for y, head, color in [(110, "PostgreSQL 16", PURPLE), (235, "Prometheus", CYAN), (360, "n8n + Analyzer", AMBER)]:
    s.shape(700, y, 150, 100, fill=color, line=BORDER, oval=True)
    s.text(700, y + 38, 150, 20, head, 10, DARK, True, "ctr")
s.line(520, 160, 700, 180, PURPLE)
s.line(520, 245, 700, 310, CYAN)
s.line(520, 330, 700, 435, AMBER)
s.text(48, 440, 600, 40, "Plugins: key-auth - JWT - rate-limiting - token-bucket - CORS - transformer - correlation-ID", 10, MUTED)

# 14 — Step 1
s = add("Step 1 - declarative topology & load balancing", "04  PRACTICAL")
s.bullets(48, 110, 470, 250, [
    "KONG_DATABASE=off and /etc/kong/kong.yml",
    '_format_version: "3.0" with 3 services + mock route',
    "3 upstreams x 2 targets, round-robin, retries=2",
    "Django Accounts + Payments, FastAPI Advisor",
    "Admin API read-only; DELETE returns HTTP 405",
], 12)
s.picture(SHOTS / "01_compose_ps_kong_version.png", 550, 110, 362, 210)
s.text(550, 330, 362, 18, "Evidence 01 - compose ps + Kong 3.9.1", 9, MUTED, align="ctr")
s.card(48, 390, 864, 75, "Result", "Gate 0 topology and C1 routes verified; kong config parse succeeds in local shell and CI.", CYAN)

# 15 — Auth
s = add("Step 2 - Key-Auth & JWT at the edge", "04  PRACTICAL")
s.card(48, 110, 420, 150, "Accounts / Advisor - key-auth", "Header apikey. Consumers fintech-free and fintech-premium hold free-demo-key and premium-demo-key. Missing keys return 401 before Django.", CYAN)
s.card(492, 110, 420, 150, "Payments - jwt", "Authorization: Bearer <token>. Kong checks HS256 signature and the iss claim. make_jwt.py only generates a valid test token with the same secret.", GREEN)
s.picture(SHOTS / "19_layer2_auth_matrix.png", 270, 285, 420, 150)
s.text(270, 440, 420, 18, "Evidence 19 - auth matrix and plugin inventory", 9, MUTED, align="ctr")

# 16 — Plugins
s = add("Step 2 - throttling, transformation & headers", "04  PRACTICAL")
plugins = [
    ("rate-limiting", "Free 10/min, premium 100/min, limit_by=consumer"),
    ("token-bucket", "Payments: 5@1/s free, 50@10/s premium"),
    ("cors", "Exposes X-RateLimit-*, Retry-After, Kong-Request-ID"),
    ("request-transformer", "Accounts header/request transformation"),
    ("correlation-id", "Kong-Request-ID on every response"),
    ("request-size-limiting", "1024-byte guard -> HTTP 413"),
]
for i, (head, body) in enumerate(plugins):
    col, row = i % 2, i // 2
    s.card(48 + col * 440, 105 + row * 93, 420, 78, head, body, [CYAN, GREEN, AMBER, PURPLE, CYAN, GREEN][i])
s.picture(SHOTS / "20_layer2_rate_token_tls.png", 600, 390, 312, 85)

# 17 — Chaos
s = add("Step 3 - chaos failover with one replica offline", "04  PRACTICAL")
s.bullets(48, 110, 450, 240, [
    "Active /health checks + passive 5xx checks",
    "k6: 2 VUs for 45 s while accounts-2 is stopped",
    "accounts-2 -> UNHEALTHY; accounts-1 -> HEALTHY",
    "k6 checks 100.00%; failed requests 0.00%",
    "Locust cross-check: 0(0.00%) failures",
], 11.5)
s.picture(SHOTS / "24_layer3_chaos_failover.png", 530, 110, 382, 240)
s.card(48, 380, 864, 85, "Why this satisfies the professor", "The practical text asks for passive/active health-check failover under concurrent load with one replica offline. Evidence 24 captures exactly that, with recovery after restart.", AMBER)

# 18 — Automation
s = add("Step 4 - Prometheus -> Alertmanager -> n8n", "04  PRACTICAL")
alerts = [
    ("KongCircuitOpen", "5xx / upstream failure threshold", CYAN),
    ("Kong429Spike", "rate-limit spike from kong_http_status", AMBER),
    ("KongUpstreamTargetUnhealthy", "target health == unhealthy / dns_error", RED),
]
for i, (head, body, color) in enumerate(alerts):
    s.card(48, 110 + i * 92, 420, 78, head, body, color)
s.picture(SHOTS / "23_layer4_prometheus_m1.png", 500, 110, 412, 230)
s.card(500, 360, 412, 100, "n8n workflows", "00-alert-router, 10-circuit-open, 20-429-spike. All imported, activated and verified with 6/6 successful executions to the notify-sink.", PURPLE)

# 19 — Analyzer
s = add("Step 4 - grounded log analyzer", "04  PRACTICAL")
for i, name in enumerate(["read_logs", "filter_records", "aggregate", "verify_answer"]):
    x = 48 + i * 220
    s.shape(x, 115, 190, 58, fill=CARD, line=BORDER, radius=True)
    s.text(x, 132, 190, 20, name, 12, CYAN, True, "ctr")
    if i < 3:
        s.line(x + 190, 144, x + 220, 144, AMBER)
s.bullets(48, 205, 450, 210, [
    "Reads the Kong file-log mount from C2",
    "Citations [L1]...[L10] point to real log lines",
    "Stats: status, route, consumer, client IP, latency",
    'Unsupported question -> exact "No verified data"',
    "15/15 Advisor tests; evidence 22",
], 11)
s.picture(SHOTS / "22_layer5_verified_analyzer.png", 530, 205, 382, 210)

# 20 — AI roadmap
s = add("AI today and the approved real-AI next step", "05  AI ROADMAP")
s.card(48, 110, 420, 190, "Implemented today", "Deterministic grounded tool loop. No external model, no hallucination, fully reproducible. It satisfies grounded AI log analyzer as a tool-calling agent pattern, but it is not an LLM.", GREEN)
s.card(492, 110, 420, 190, "Approved next: Ollama hybrid", "LLM proposes the tool calls; read_logs/filter_records/aggregate remain deterministic; verify_answer rejects any answer without citations. No external network dependency.", PURPLE)
s.card(48, 325, 864, 120, "Why the verifier still matters", "An LLM can choose a tool, but only the tool output can create numbers and citations. This keeps the C1 contract, C2 grounding and the exact fallback intact.", AMBER)

# 21 — Contracts and gates
s = add("Contracts C1-C4 & gate discipline", "05  GOVERNANCE")
contracts = [
    ["Contract", "Version", "Purpose"],
    ["C1 API", "0.3.0", "Service interfaces and /analyze response"],
    ["C2 Log", "0.1.1", "Kong access-log fields and citation source"],
    ["C3 Metrics", "0.2.1", "Alert names, thresholds, labels, webhook"],
    ["C4 Naming", "0.2.1", "Ports, profiles, Compose, env, plan"],
]
for r, row in enumerate(contracts):
    y = 110 + r * 44
    widths = [180, 140, 544]
    x = 48
    for c, value in enumerate(row):
        fill = CYAN if r == 0 else (CARD if r % 2 == 0 else CARD2)
        color = DARK if r == 0 else (CYAN if c == 0 else TEXT)
        s.shape(x, y, widths[c], 44, fill=fill, line=BORDER)
        s.text(x + 6, y + 12, widths[c] - 12, 20, value, 10 if r == 0 else 9.5, color, r == 0 or c == 0)
        x += widths[c]
s.card(48, 355, 420, 105, "Approved PATCHes", "C3 0.2.0 -> 0.2.1 fixed health-state semantics. C4 0.2.0 -> 0.2.1 removed the DB-mode lab promise.", CYAN)
s.card(492, 355, 420, 105, "Gate rule", "No merge into main without explicit approval. Branch CI is green; main remains unchanged.", GREEN)

# 22 — CI
s = add("CI green gate & reproducibility", "05  GOVERNANCE")
s.bullets(48, 110, 470, 250, [
    "P3a: repository checks, secret scan, contract versions",
    "P3b: pytest, Kong parse, plugin mocks",
    "P3c: platform gates and image builds",
    "CI green gate: required status check on main",
    "Runs #23, #24, #25 and #27 all green",
], 12)
s.picture(SHOTS / "18_ci_red_green.png", 550, 110, 362, 210)
s.card(48, 390, 864, 75, "Branch invariants", "Working branch ci/prototype-pipeline; origin/main unchanged at 61ad184; no PR or merge from this branch.", AMBER)

# 23 — Evidence gallery
s = add("Evidence gallery - formal terminal PNGs", "05  EVIDENCE")
shots = [
    ("01_compose_ps_kong_version.png", "01 Topology"),
    ("19_layer2_auth_matrix.png", "19 Auth"),
    ("20_layer2_rate_token_tls.png", "20 Limits/TLS"),
    ("21_layer2_telemetry.png", "21 Telemetry"),
    ("22_layer5_verified_analyzer.png", "22 Analyzer"),
    ("23_layer4_prometheus_m1.png", "23 Metrics"),
    ("24_layer3_chaos_failover.png", "24 Chaos"),
    ("25_final_gate_audit.png", "25 Final Gate"),
]
for i, (name, caption) in enumerate(shots):
    col, row = i % 4, i // 4
    x, y = 48 + col * 222, 110 + row * 190
    s.picture(SHOTS / name, x, y, 198, 145)
    s.text(x, y + 150, 198, 18, caption, 9, CYAN, True, "ctr")

# 24 — Close
s = add("Final Gate result & what is next", "05  CLOSE")
s.card(48, 110, 420, 170, "Final Gate audit", "PASS WITH WARNINGS. 54/54 automated checks pass across contracts, topology, C1 auth, C2 logs, C3 alerts, C4 Compose, analyzer, evidence and CI.", GREEN)
s.card(492, 110, 420, 170, "Open WARN items", "Evidence 10, 11, 13, 14; LLM tool-calling spike record; Telegram test credentials; branch-protection re-read without token.", AMBER)
s.card(48, 305, 420, 140, "Immediate next", "Add Ollama as an approved optional tool proposer, keeping the deterministic verifier and C1/C2 contracts unchanged.", PURPLE)
s.card(492, 305, 420, 140, "Presentation close", "The prototype proves the gateway pattern end to end: declarative edge, auth, throttling, resiliency, automation and grounded verification.", CYAN)
s.text(48, 465, 864, 24, "Questions", 14, WHITE, True, "ctr")


def presentation_xml() -> str:
    ids = "".join(
        '<p:sldId id="{}" r:id="rId{}"/>'.format(256 + i, i + 2)
        for i in range(len(slides))
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:presentation xmlns:a="{a}" xmlns:r="{r}" xmlns:p="{p}">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        '<p:sldIdLst>{ids}</p:sldIdLst>'
        '<p:sldSz cx="{w}" cy="{h}" type="screen16x9"/>'
        '<p:notesSz cx="{h}" cy="{w}"/>'
        "</p:presentation>"
    ).format(a=A_NS, r=R_NS, p=P_NS, ids=ids, w=e(SLIDE_W), h=e(SLIDE_H))


def presentation_rels() -> str:
    rels = [
        '<Relationship Id="rId1" Type="{}/slideMaster" Target="slideMasters/slideMaster1.xml"/>'.format(R_NS)
    ]
    rels += [
        '<Relationship Id="rId{}" Type="{}/slide" Target="slides/slide{}.xml"/>'.format(i + 2, R_NS, i + 1)
        for i in range(len(slides))
    ]
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="{}">{}</Relationships>'.format(PKG_REL_NS, "".join(rels))
    )


SLIDE_MASTER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<p:sldMaster xmlns:a="{a}" xmlns:r="{r}" xmlns:p="{p}">'
    '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
    '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
    "</p:spTree></p:cSld>"
    '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" '
    'accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
    '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
    "</p:sldMaster>"
).format(a=A_NS, r=R_NS, p=P_NS)

SLIDE_MASTER_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="{}">'
    '<Relationship Id="rId1" Type="{}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
    '<Relationship Id="rId2" Type="{}/theme" Target="../theme/theme1.xml"/>'
    "</Relationships>"
).format(PKG_REL_NS, R_NS, R_NS)

SLIDE_LAYOUT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<p:sldLayout xmlns:a="{a}" xmlns:r="{r}" xmlns:p="{p}" type="blank" preserve="1">'
    '<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
    '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
    "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"
).format(a=A_NS, r=R_NS, p=P_NS)

SLIDE_LAYOUT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="{}">'
    '<Relationship Id="rId1" Type="{}/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
    "</Relationships>"
).format(PKG_REL_NS, R_NS)

THEME = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<a:theme xmlns:a="{a}" name="FinTech Dark">'
    "<a:themeElements>"
    '<a:clrScheme name="FinTech">'
    '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
    '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
    '<a:dk2><a:srgbClr val="111C2E"/></a:dk2><a:lt2><a:srgbClr val="CBD5E1"/></a:lt2>'
    '<a:accent1><a:srgbClr val="22D3EE"/></a:accent1><a:accent2><a:srgbClr val="34D399"/></a:accent2>'
    '<a:accent3><a:srgbClr val="F59E0B"/></a:accent3><a:accent4><a:srgbClr val="A78BFA"/></a:accent4>'
    '<a:accent5><a:srgbClr val="F87171"/></a:accent5><a:accent6><a:srgbClr val="94A3B8"/></a:accent6>'
    '<a:hlink><a:srgbClr val="22D3EE"/></a:hlink><a:folHlink><a:srgbClr val="A78BFA"/></a:folHlink>'
    "</a:clrScheme>"
    '<a:fontScheme name="FinTech"><a:majorFont><a:latin typeface="Segoe UI"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
    '<a:minorFont><a:latin typeface="Segoe UI"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>'
    '<a:fmtScheme name="FinTech">'
    '<a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
    '<a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
    '<a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
    '<a:ln w="28575"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
    '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>'
    '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>'
    "</a:fmtScheme></a:themeElements>"
    '<a:objectDefaults/><a:extraClrSchemeLst/></a:theme>'
).format(a=A_NS)

CORE = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
    'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    "<dc:title>FinTech API Gateway - Kong 3.9.1 Prototype</dc:title>"
    "<dc:subject>Topic 17 theoretical and practical presentation</dc:subject>"
    "<dc:creator>Eya Derouiche, Aya Fayachi, Wafe Bziouiche</dc:creator>"
    "<cp:lastModifiedBy>OpenCode</cp:lastModifiedBy>"
    "<dcterms:created xsi:type=\"dcterms:W3CDTF\">2026-11-24T00:00:00Z</dcterms:created>"
    "<dcterms:modified xsi:type=\"dcterms:W3CDTF\">2026-11-24T00:00:00Z</dcterms:modified>"
    "</cp:coreProperties>"
)

APP = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
    'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
    "<Application>Microsoft Office PowerPoint</Application><PresentationFormat>On-screen Show (16:9)</PresentationFormat>"
    "<Slides>{}</Slides><Notes>0</Notes><HiddenSlides>0</HiddenSlides></Properties>"
).format(len(slides))


def content_types() -> str:
    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    overrides += [
        '<Override PartName="/ppt/slides/slide{}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'.format(i + 1)
        for i in range(len(slides))
    ]
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="{}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        "{}</Types>"
    ).format(CT_NS, "".join(overrides))


ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="{}">'
    '<Relationship Id="rId1" Type="{}/officeDocument" Target="ppt/presentation.xml"/>'
    '<Relationship Id="rId2" Type="{}/metadata/core-properties" Target="docProps/core.xml"/>'
    '<Relationship Id="rId3" Type="{}/extended-properties" Target="docProps/app.xml"/>'
    "</Relationships>"
).format(PKG_REL_NS, R_NS, PKG_REL_NS, R_NS)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    media: dict[str, bytes] = {}
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types())
        zf.writestr("_rels/.rels", ROOT_RELS)
        zf.writestr("docProps/core.xml", CORE)
        zf.writestr("docProps/app.xml", APP)
        zf.writestr("ppt/presentation.xml", presentation_xml())
        zf.writestr("ppt/_rels/presentation.xml.rels", presentation_rels())
        zf.writestr("ppt/slideMasters/slideMaster1.xml", SLIDE_MASTER)
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", SLIDE_MASTER_RELS)
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", SLIDE_LAYOUT)
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", SLIDE_LAYOUT_RELS)
        zf.writestr("ppt/theme/theme1.xml", THEME)
        for i, slide in enumerate(slides, start=1):
            zf.writestr(f"ppt/slides/slide{i}.xml", slide.xml())
            zf.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", slide.rels_xml())
            for _, path in slide.images:
                if path.name not in media:
                    media[path.name] = path.read_bytes()
        for name, data in media.items():
            zf.writestr(f"ppt/media/{name}", data)

    print(f"Built {OUTPUT}")
    print(f"Slides: {len(slides)}")
    print(f"Bytes: {OUTPUT.stat().st_size}")


if __name__ == "__main__":
    main()
