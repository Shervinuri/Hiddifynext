"""
Build a *small, high-chance* V2Ray subscription from many sources.

- No accumulation: output is overwritten every run.
- De-duplication: strong normalized key (not just string equality).
- Filtering + scoring: NOT restricted to WS/gRPC and NOT restricted to specific ports.
  (We still *prefer* some patterns lightly, but we don't hard-penalize "unusual" ports/transports.)
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
from typing import Iterator, Optional

import requests

# -------------------- user knobs --------------------
SOURCES = [
    # Your existing sources
    "https://raw.githubusercontent.com/barry-far/V2ray-config/main/All_Configs_base64_Sub.txt",
    "https://raw.githubusercontent.com/arshiacomplus/v2rayExtractor/refs/heads/main/vless.html",
    "https://raw.githubusercontent.com/parvinxs/Submahsanetxsparvin/refs/heads/main/Sub.mahsa.xsparvin",
    "https://msk.vless-balancer.ru/sub/dXNlcl82Nzg4MzMxMjQ5LDE3Njk1MzUzMTkBqGm3A1STd/#KIA_NET",
    "https://raw.githubusercontent.com/Mosifree/-FREE2CONFIG/refs/heads/main/Reality",
    "https://v2.alicivil.workers.dev",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/super-sub.txt",

    # Added: frequently refreshed, already “cleaned/working” lists (kept lightweight)
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/V2Ray-Config-By-EbraSha.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/vless_configs.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/vmess_configs.txt",
]

REMARK = "☬SHΞN™"

# Keep this smaller to avoid phone lag (was 1000)
MAX_OUTPUT = 450

# Output files (overwritten every run)
OUT_SUB = Path("subscription.txt")
OUT_INDEX = Path("Index.html")  # optional refresh if it exists

# -------------------- internals --------------------
CONFIG_PATTERN = re.compile(r"(?:vmess|vless|hysteria2|hy2)://[^\s\"'<>]+", re.IGNORECASE)
BASE64_PATTERN = re.compile(r"^[A-Za-z0-9+/=_-]+$")

# VLESS params that matter for de-dup
VLESS_KEY_PARAMS = (
    "type", "security", "sni", "host", "path", "serviceName", "mode", "fp",
    "alpn", "pbk", "sid", "spx", "flow"
)

# Softer preferences (NOT restrictions)
TRANSPORT_BONUS = {
    "ws": 8,
    "grpc": 7,
    "tcp": 6,
    "h2": 6,
    "http": 5,
    "xhttp": 5,
    "splithttp": 5,
    "quic": 4,
    "kcp": 3,
}

SECURITY_BONUS = {
    "reality": 10,
    "tls": 8,
    "xtls": 8,
    "none": 0,
    "": 0,
}

# Mild port bonus only (no big penalties for odd ports)
GOOD_PORTS = {443, 80, 8080, 8443, 2053, 2083, 2087, 2096, 8880}

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
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SubBuilder/1.2)"}
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

def _port_bonus(port: int) -> int:
    if port <= 0:
        return -50  # invalid only
    if port in GOOD_PORTS:
        return 3
    return 0  # no penalty for other ports

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
    net = str(data.get("net", "")).strip().lower()  # ws/grpc/tcp/...
    tls = str(data.get("tls", "")).strip().lower()  # "tls" or ""
    host = str(data.get("host", "")).strip().lower()
    path = str(data.get("path", "")).strip()
    sni = str(data.get("sni", "")).strip().lower() if "sni" in data else ""
    aid = str(data.get("aid", "")).strip()
    vid = str(data.get("id", "")).strip().lower()

    key = f"vmess|{vid}|{add}|{port}|{net}|{tls}|{sni}|{host}|{path}|{aid}"

    score = 0
    score += 18  # baseline vmess

    score += TRANSPORT_BONUS.get(net, 4)  # unknown transports still OK
    score += (8 if tls == "tls" else 2)    # no harsh penalty for non-tls

    score += _port_bonus(port)

    if host:
        score += 2
    if sni:
        score += 2
    if path:
        score += 1

    return ScoredConfig(score=score, config=config, key=key)

def _vless_key_score(config: str) -> Optional[ScoredConfig]:
    p = urllib.parse.urlsplit(config)
    host = (p.hostname or "").strip().lower()
    port = int(p.port or 0)
    user = (p.username or "").strip().lower()
    q = _qdict(p.query)

    t = (q.get("type", "") or "tcp").lower()
    security = (q.get("security", "") or "").lower()
    sni = (q.get("sni", "") or "").lower()
    host_hdr = (q.get("host", "") or "").lower()
    path = q.get("path", "") or ""
    svc = q.get("serviceName", "") or ""

    parts = [f"vless|{user}|{host}|{port}"]
    for k in VLESS_KEY_PARAMS:
        parts.append(f"{k}={q.get(k,'')}")
    key = "|".join(parts)

    score = 0
    score += 22  # baseline vless

    score += TRANSPORT_BONUS.get(t, 4)
    score += SECURITY_BONUS.get(security, 2)
    score += _port_bonus(port)

    # small “looks like CDN / stable routing” hints (no hard requirement)
    if sni:
        score += 3
    if host_hdr:
        score += 3
    if path:
        score += 1
    if svc and t == "grpc":
        score += 1

    return ScoredConfig(score=score, config=config, key=key)

def _hy2_key_score(config: str) -> Optional[ScoredConfig]:
    # Raised priority: can work better in some mobile conditions
    p = urllib.parse.urlsplit(config)
    host = (p.hostname or "").strip().lower()
    port = int(p.port or 0)
    user = (p.username or "").strip().lower()
    q = _qdict(p.query)
    sni = (q.get("sni", "") or "").lower()

    key = f"hy2|{user}|{host}|{port}|sni={sni}"

    score = 0
    score += 20  # baseline hy2
    score += _port_bonus(port)
    if sni:
        score += 2

    return ScoredConfig(score=score, config=config, key=key)

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

    scored = scored[:MAX_OUTPUT]

    write_subscription(scored)

    if OUT_INDEX.exists():
        sections = read_index_sections(OUT_INDEX)
        update_index(OUT_INDEX, sections, scored)

    print(f"OK: wrote {len(scored)} configs to {OUT_SUB}", file=sys.stderr)

if __name__ == "__main__":
    main()
