"""Build a *small, high-chance* V2Ray subscription from many sources.

- No accumulation: output is overwritten every run.
- De-duplication: strong normalized key (not just string equality).
- Filtering + scoring: prefers VLESS/VMess with WS/gRPC + TLS on common CDN ports.
- Output: `subscription.txt` (one config per line) and optional `Index.html` refresh.

Edit:
- SOURCES (your subs)
- REMARK (your tag)
- MAX_OUTPUT (how many lines you want to keep)
"""

from __future__ import annotations

import base64
import json
import re
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

import requests

# -------------------- user knobs --------------------
SOURCES = [
    "https://raw.githubusercontent.com/barry-far/V2ray-config/main/All_Configs_base64_Sub.txt",
    "https://raw.githubusercontent.com/arshiacomplus/v2rayExtractor/refs/heads/main/vless.html",
    "https://raw.githubusercontent.com/parvinxs/Submahsanetxsparvin/refs/heads/main/Sub.mahsa.xsparvin",
    "https://msk.vless-balancer.ru/sub/dXNlcl82Nzg4MzMxMjQ5LDE3Njk1MzUzMTkBqGm3A1STd/#KIA_NET",
    "https://raw.githubusercontent.com/Mosifree/-FREE2CONFIG/refs/heads/main/Reality",
    "https://v2.alicivil.workers.dev",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/super-sub.txt",
]

REMARK = "☬SHΞN™"

# Keep this small to avoid phone lag.
MAX_OUTPUT = 1000

# Prefer these transports and ports (common â€œworks more oftenâ€ set).
PREFERRED_TRANSPORTS = {"ws", "grpc"}
PREFERRED_PORTS_STRONG = {443}
PREFERRED_PORTS_GOOD = {2053, 2083, 2087, 2096, 8443, 80, 8080, 8880}

# Output files (overwritten every run)
OUT_SUB = Path("subscription.txt")
OUT_INDEX = Path("Index.html")  # optional refresh if it exists

# -------------------- internals --------------------
CONFIG_PATTERN = re.compile(r"(?:vmess|vless|hysteria2|hy2)://[^\s\"'<>]+", re.IGNORECASE)
BASE64_PATTERN = re.compile(r"^[A-Za-z0-9+/=_-]+$")

# VLESS params that matter for de-dup
VLESS_KEY_PARAMS = (
    "type", "security", "sni", "host", "path", "serviceName", "mode", "fp", "alpn", "pbk", "sid", "spx", "flow"
)

@dataclass(frozen=True)
class IndexSections:
    meta_lines: list[str]
    tail_lines: list[str]

@dataclass(frozen=True)
class ScoredConfig:
    score: int
    config: str
    key: str

def fetch_text(url: str) -> Optional[str]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SubBuilder/1.1)"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200 and r.text:
            return r.text
    except Exception:
        return None
    return None

def extract_configs(text: str) -> list[str]:
    return list({m.group(0) for m in CONFIG_PATTERN.finditer(text)})

def maybe_decode_base64(line: str) -> Optional[str]:
    cleaned = line.strip()
    if not cleaned or not BASE64_PATTERN.match(cleaned):
        return None
    try:
        padded = cleaned + "=" * (-len(cleaned) % 4)
        decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
        if "://" not in decoded:
            return None
        return decoded
    except Exception:
        return None

def collect_configs_from_text(text: str) -> Iterator[str]:
    # direct
    for cfg in extract_configs(text):
        yield cfg
    # base64 lines (some subs are base64 list)
    for line in text.splitlines():
        decoded = maybe_decode_base64(line)
        if not decoded:
            continue
        for cfg in extract_configs(decoded):
            yield cfg

def remark_vmess(config: str) -> Optional[str]:
    payload = config[len("vmess://"):]
    try:
        padded = payload + "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
        data = json.loads(decoded.decode("utf-8"))
    except Exception:
        return None
    data["ps"] = REMARK
    encoded = base64.urlsafe_b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    return f"vmess://{encoded.decode('utf-8').rstrip('=')}"

def remark_url_fragment(config: str) -> str:
    p = urllib.parse.urlsplit(config)
    return urllib.parse.urlunsplit(p._replace(fragment=urllib.parse.quote(REMARK, safe="")))

def normalize_config(config: str) -> Optional[str]:
    lowered = config.lower()
    if lowered.startswith("vmess://"):
        return remark_vmess(config)
    if lowered.startswith(("vless://", "hysteria2://", "hy2://")):
        return remark_url_fragment(config)
    return None

def _qdict(query: str) -> dict[str, str]:
    # keep first value only (enough for our scoring/dedup)
    q = urllib.parse.parse_qs(query, keep_blank_values=True)
    return {k: (v[0] if v else "") for k, v in q.items()}

def make_key_and_score(config: str) -> Optional[ScoredConfig]:
    low = config.lower()
    if low.startswith("vmess://"):
        return _vmess_key_score(config)
    if low.startswith("vless://"):
        return _vless_key_score(config)
    if low.startswith(("hy2://", "hysteria2://")):
        return _hy2_key_score(config)
    return None

def _vmess_key_score(config: str) -> Optional[ScoredConfig]:
    payload = config[len("vmess://"):]
    try:
        padded = payload + "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
        data = json.loads(decoded.decode("utf-8"))
    except Exception:
        return None

    add = str(data.get("add", "")).strip().lower()
    port = int(str(data.get("port", "0")).strip() or 0)
    net = str(data.get("net", "")).strip().lower()  # ws/grpc/tcp
    tls = str(data.get("tls", "")).strip().lower()  # "tls" or ""
    host = str(data.get("host", "")).strip().lower()
    path = str(data.get("path", "")).strip()
    sni = str(data.get("sni", "")).strip().lower() if "sni" in data else ""
    aid = str(data.get("aid", "")).strip()
    vid = str(data.get("id", "")).strip().lower()

    key = f"vmess|{vid}|{add}|{port}|{net}|{tls}|{sni}|{host}|{path}|{aid}"
    score = 0

    # protocol preference
    score += 20

    # transport preference
    if net in PREFERRED_TRANSPORTS:
        score += 30 if net == "ws" else 25
    elif net == "tcp":
        score += 10
    else:
        score -= 10

    # tls preference
    if tls == "tls":
        score += 20
    else:
        score -= 10

    # port preference
    score += _port_score(port)

    # host/sni helpful
    if host:
        score += 4
    if sni:
        score += 4

    return ScoredConfig(score=score, config=config, key=key)

def _vless_key_score(config: str) -> Optional[ScoredConfig]:
    p = urllib.parse.urlsplit(config)
    host = (p.hostname or "").strip().lower()
    port = int(p.port or 0)
    user = (p.username or "").strip().lower()
    q = _qdict(p.query)

    t = q.get("type", "").lower() or "tcp"
    security = q.get("security", "").lower()
    sni = q.get("sni", "").lower()
    host_hdr = q.get("host", "").lower()
    path = q.get("path", "")
    svc = q.get("serviceName", "")

    # build dedup key from important parameters
    parts = [f"vless|{user}|{host}|{port}"]
    for k in VLESS_KEY_PARAMS:
        parts.append(f"{k}={q.get(k,'')}")
    key = "|".join(parts)

    score = 0
    score += 30  # vless > vmess

    # transport
    if t in PREFERRED_TRANSPORTS:
        score += 32 if t == "ws" else 27
    elif t == "tcp":
        score += 10
    else:
        score -= 8

    # security
    if security in {"tls", "reality"}:
        score += 22 if security == "tls" else 26
    elif security == "none" or not security:
        score -= 10
    else:
        score += 2

    # port
    score += _port_score(port)

    # sni/host/path improve CDN-looking configs
    if sni:
        score += 5
    if host_hdr:
        score += 5
    if path:
        score += 2
    if svc and t == "grpc":
        score += 3

    return ScoredConfig(score=score, config=config, key=key)

def _hy2_key_score(config: str) -> Optional[ScoredConfig]:
    # keep but low priority (some phones/clients struggle; also fewer of these exist)
    p = urllib.parse.urlsplit(config)
    host = (p.hostname or "").strip().lower()
    port = int(p.port or 0)
    user = (p.username or "").strip().lower()
    q = _qdict(p.query)
    sni = q.get("sni", "").lower()
    key = f"hy2|{user}|{host}|{port}|sni={sni}"
    score = 8 + _port_score(port) + (4 if sni else 0)
    return ScoredConfig(score=score, config=config, key=key)

def _port_score(port: int) -> int:
    if port in PREFERRED_PORTS_STRONG:
        return 25
    if port in PREFERRED_PORTS_GOOD:
        # favor 80/8080 but not as much as 443-family
        return 18 if port in {2053, 2083, 2087, 2096, 8443} else 10
    if port <= 0:
        return -30
    # weird ports are risky for mobile stability
    if port in {25, 53, 123, 1900, 3389, 6667}:
        return -40
    return -5

def read_index_sections(path: Path) -> IndexSections:
    if not path.exists():
        return IndexSections(meta_lines=[], tail_lines=[])

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    meta_lines: list[str] = []
    i = 0
    while i < len(lines) and lines[i].startswith("#"):
        meta_lines.append(lines[i])
        i += 1

    redirect_start = None
    for idx, line in enumerate(lines):
        if "hiddify://import/" in line:
            for back in range(idx, -1, -1):
                if lines[back].strip().lower() == "<script>":
                    redirect_start = back
                    break
            if redirect_start is None:
                redirect_start = idx
            break

    tail_lines: list[str] = []
    if redirect_start is not None:
        tail_lines = lines[redirect_start:]

    return IndexSections(meta_lines=meta_lines, tail_lines=tail_lines)

def write_subscription(scored: list[ScoredConfig]) -> None:
    OUT_SUB.write_text("\n".join([s.config for s in scored]) + "\n", encoding="utf-8")

def update_index(path: Path, sections: IndexSections, scored: list[ScoredConfig]) -> None:
    # Overwrite Index.html: meta + configs + tail
    with path.open("w", encoding="utf-8") as f:
        for line in sections.meta_lines:
            f.write(line + "\n")
        for s in scored:
            f.write(s.config + "\n")
        for line in sections.tail_lines:
            f.write(line + "\n")

def main() -> None:
    collected: list[str] = []

    for url in SOURCES:
        text = fetch_text(url)
        if not text:
            print(f"Warning: failed to fetch {url}", file=sys.stderr)
            continue
        for cfg in collect_configs_from_text(text):
            norm = normalize_config(cfg)
            if norm:
                collected.append(norm)

    if not collected:
        print("Warning: no configs found.", file=sys.stderr)
        OUT_SUB.write_text("", encoding="utf-8")
        return

    # Score + strong dedup by normalized key
    best_by_key: dict[str, ScoredConfig] = {}
    for cfg in collected:
        sc = make_key_and_score(cfg)
        if not sc:
            continue
        prev = best_by_key.get(sc.key)
        if (prev is None) or (sc.score > prev.score):
            best_by_key[sc.key] = sc

    scored = list(best_by_key.values())
    scored.sort(key=lambda x: x.score, reverse=True)

    # Keep only top N
    scored = scored[:MAX_OUTPUT]

    # Write outputs (no accumulation)
    write_subscription(scored)

    # Optional: refresh Index.html if it already exists
    if OUT_INDEX.exists():
        sections = read_index_sections(OUT_INDEX)
        update_index(OUT_INDEX, sections, scored)

    print(f"OK: wrote {len(scored)} configs to {OUT_SUB}", file=sys.stderr)

if __name__ == "__main__":
    main()
