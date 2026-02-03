"""Update Index.html with merged V2Ray configs from multiple subscriptions."""

from __future__ import annotations

import base64
import json
import re
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import requests

SOURCES = [
    "https://raw.githubusercontent.com/barry-far/V2ray-config/main/All_Configs_base64_Sub.txt",
    "https://raw.githubusercontent.com/arshiacomplus/v2rayExtractor/refs/heads/main/vless.html",
    "https://raw.githubusercontent.com/parvinxs/Submahsanetxsparvin/refs/heads/main/Sub.mahsa.xsparvin",
    "https://msk.vless-balancer.ru/sub/dXNlcl82Nzg4MzMxMjQ5LDE3Njk1MzUzMTkBqGm3A1STd/#KIA_NET",
    "https://raw.githubusercontent.com/Mosifree/-FREE2CONFIG/refs/heads/main/Reality",
    "https://raw.githubusercontent.com/Mosifree/-FREE2CONFIG/refs/heads/main/Clash_Reality",
    "https://cdn.fildl.ir/sub/TUNrQ2JpLDE3Njc4OTA3OTEyzup1z2RKG#Subscription",
    "https://raw.githubusercontent.com/Mosifree/-FREE2CONFIG/refs/heads/main/Reality",
    "https://raw.githubusercontent.com/Mosifree/-FREE2CONFIG/refs/heads/main/Clash_Reality",
    "https://danesh1118.github.io/Heoehoehdidhwj3978eheheodheoheofhrirh8e7eyhedohdkdheodhh9rehejrjfohrkeje/",
    "https://v2.alicivil.workers.dev",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/super-sub.txt",
    "https://gist.githubusercontent.com/senatorpersian/ddb0dc4ceed582630c24ef56197d297a/raw/cb3370e2be7a72cb640d96c7b137029dc05b3739/subscription.txt",
    "https://gist.githubusercontent.com/senatorpersian/ddb0dc4ceed582630c24ef56197d297a/raw/7767ced7587c4f8d203de08b186606eb880f3814/subscription.txt",
]

REMARK = "☬SHΞЯVIN™"
CONFIG_PATTERN = re.compile(r"(?:vmess|vless|hysteria2|hy2)://[^\s\"'<>]+", re.IGNORECASE)
BASE64_PATTERN = re.compile(r"^[A-Za-z0-9+/=_-]+$")


@dataclass(frozen=True)
class IndexSections:
    meta_lines: list[str]
    tail_lines: list[str]


def fetch_text(url: str) -> str | None:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; HiddifyUpdater/1.0)"}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.text
    except Exception:
        return None
    return None


def extract_configs(text: str) -> list[str]:
    configs = set(match.group(0) for match in CONFIG_PATTERN.finditer(text))
    return list(configs)


def maybe_decode_base64(line: str) -> str | None:
    cleaned = line.strip()
    if not cleaned or not BASE64_PATTERN.match(cleaned):
        return None
    try:
        padded = cleaned + "=" * (-len(cleaned) % 4)
        decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
    except Exception:
        return None
    return decoded


def collect_configs_from_text(text: str) -> Iterator[str]:
    for config in extract_configs(text):
        yield config
    for line in text.splitlines():
        decoded = maybe_decode_base64(line)
        if not decoded:
            continue
        for config in extract_configs(decoded):
            yield config


def remark_vmess(config: str) -> str | None:
    payload = config[len("vmess://") :]
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
    parsed = urllib.parse.urlsplit(config)
    updated = parsed._replace(fragment=urllib.parse.quote(REMARK, safe=""))
    return urllib.parse.urlunsplit(updated)


def normalize_config(config: str) -> str | None:
    lowered = config.lower()
    if lowered.startswith("vmess://"):
        return remark_vmess(config)
    if lowered.startswith(("vless://", "hysteria2://", "hy2://")):
        return remark_url_fragment(config)
    return None


def read_index_sections(path: Path) -> IndexSections:
    if not path.exists():
        return IndexSections(meta_lines=[], tail_lines=[])

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    meta_lines: list[str] = []
    index = 0
    while index < len(lines) and lines[index].startswith("#"):
        meta_lines.append(lines[index])
        index += 1

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


def update_index(path: Path, sections: IndexSections, configs: Iterable[str]) -> None:
    unique_configs = sorted(set(configs), key=str.lower)
    with path.open("w", encoding="utf-8") as handle:
        for line in sections.meta_lines:
            handle.write(f"{line}\n")
        for config in unique_configs:
            handle.write(f"{config}\n")
        for line in sections.tail_lines:
            handle.write(f"{line}\n")


def main() -> None:
    all_configs: list[str] = []
    for url in SOURCES:
        text = fetch_text(url)
        if not text:
            print(f"Warning: failed to fetch {url}", file=sys.stderr)
            continue
        for config in collect_configs_from_text(text):
            normalized = normalize_config(config)
            if normalized:
                all_configs.append(normalized)

    if not all_configs:
        print("Warning: no configs found in subscriptions.", file=sys.stderr)

    index_path = Path("Index.html")
    sections = read_index_sections(index_path)
    update_index(index_path, sections, all_configs)


if __name__ == "__main__":
    main()
