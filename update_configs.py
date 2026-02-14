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
import random

# -------------------- user knobs --------------------
SOURCES = [
    "https://raw.githubusercontent.com/barry-far/V2ray-config/main/All_Configs_base64_Sub.txt",
    "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-protocol/vmess.txt",
    "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-protocol/vless.txt",
    "https://raw.githubusercontent.com/nyeinkokoaung404/V2ray-Configs/main/All_Configs_Sub.txt",
]

REMARK = "☬SHΞN™"
MAX_OUTPUT = 1000

OUT_SUB = Path("subscription.txt")
OUT_INDEX = Path("Index.html")

CONFIG_PATTERN = re.compile(r"(?:vmess|vless|hysteria2|hy2)://[^\s\"'<>]+", re.IGNORECASE)
BASE64_PATTERN = re.compile(r"^[A-Za-z0-9+/=_-]+$")

VLESS_KEY_PARAMS = (
    "type", "security", "sni", "host", "path", "serviceName", "mode", "fp",
    "alpn", "pbk", "sid", "spx", "flow"
)

TRANSPORT_BONUS = {
    "ws": 8, "grpc": 7, "tcp": 6, "h2": 6, "http": 5, "xhttp": 5,
    "splithttp": 5, "quic": 4, "kcp": 3,
}

SECURITY_BONUS = {
    "reality": 10, "tls": 8, "xtls": 8, "none": 0, "": 0,
}

GOOD_PORTS = {443, 80, 8080, 8443, 2053, 2083, 2087, 2096, 8880}

PORT_PRIORITY: dict[int, int] = {
    443: 20,
    80: 18,
    8080: 15,
}

COUNTRY_TLDS: tuple[str, ...] = (".us", ".de", ".nl", ".fr")


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
    for cfg in extract_configs(text):
        yield cfg
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
    encoded = base64.urlsafe_b64encode(
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    )
    return f"vmess://{encoded.decode('utf-8').rstrip('=')}"


def remark_url_fragment(config: str) -> str:
    p = urllib.parse.urlsplit(config)
    return urllib.parse.urlunsplit(
        p._replace(fragment=urllib.parse.quote(REMARK, safe=""))
    )


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


def safe_port(p: urllib.parse.SplitResult) -> int:
    try:
        return int(p.port or 0)
    except ValueError:
        netloc = p.netloc.rsplit('@', 1)[-1]
        if ':' in netloc:
            port_str = netloc.split(':', 1)[1]
            m = re.match(r"\d+", port_str)
            if m:
                return int(m.group(0))
        return 0


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
        return -50
    if port in PORT_PRIORITY:
        return PORT_PRIORITY[port]
    if port in GOOD_PORTS:
        return 3
    return 0


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
    net = str(data.get("net", "")).strip().lower()
    tls = str(data.get("tls", "")).strip().lower()
    host = str(data.get("host", "")).strip().lower()
    path = str(data.get("path", "")).strip()
    sni = str(data.get("sni", "")).strip().lower() if "sni" in data else ""
    aid = str(data.get("aid", "")).strip()
    vid = str(data.get("id", "")).strip().lower()

    key = f"vmess|{vid}|{add}|{port}|{net}|{tls}|{sni}|{host}|{path}|{aid}"

    score = 18
    if net == "ws":
        score += 5
        if port in (443, 80, 8080):
            score += 5

    score += TRANSPORT_BONUS.get(net, 4)
    score += (8 if tls == "tls" else 2)
    score += _port_bonus(port)

    if any(add.endswith(tld) for tld in COUNTRY_TLDS):
        score += 5
    if host:
        score += 2
    if sni:
        score += 2
    if path:
        score += 1

    return ScoredConfig(score=score, config=config, key=key)

# (کد تا انتها به همین منوال ادامه دارد، شامل تعریف تابع‌های امتیازدهی VLESS/Hy2، نوشتن خروجی و تابع main)
