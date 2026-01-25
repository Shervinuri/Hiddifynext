"""
A script to automatically fetch and combine V2Ray configuration links from multiple
public subscription sources and update the repository's ``Index.html`` file.

This script is designed to run periodically via the GitHub Actions workflow
defined in ``.github/workflows/main.yml``.  It downloads V2Ray/Vmess/VLess/Hysteria2
configuration links from several external providers, deduplicates them, performs
a lightweight health check, adds a browser redirect to Hiddify Next, and writes
them back into the ``Index.html`` file in
this repository.  Any
metadata lines at the top of the existing ``Index.html`` (such as
``#profile-title`` or ``#profile-update-interval``) are preserved.

The chosen sources are public repositories that publish frequently updated
configuration lists.  If additional sources become available in the future,
they can be added to the ``SOURCES`` list below.  Each source may provide
configuration lines directly or a base64â€‘encoded blob containing meta lines
and configuration links; this script handles both cases.

Usage:

    python update_configs.py

The script relies only on the standard library and the thirdâ€‘party
``requests`` module (listed in ``requirements.txt``).

"""

import base64
import json
import pathlib
import re
import socket
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, List, Optional, Tuple

import requests


# List of subscription URLs to fetch.  These URLs point to public GitHub
# raw files that are updated regularly.  They include both an "all"
# subscription (thousands of links) and a "super" subscription (a curated
# subset).  Feel free to append new sources as needed.
SOURCES: List[str] = [
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/all_sub.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/super-sub.txt",
    # Additional sources can be added here.  For example, perâ€‘protocol lists:
    # "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/filtered/subs/vmess.txt",
    # "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/filtered/subs/vless.txt",
    # "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/filtered/subs/trojan.txt",
]


def _get_text_from_github_api(owner: str, repo: str, branch: str, path: str) -> str | None:
    """Attempt to fetch a file via the GitHub API as a fallback.

    GitHub's REST API can return raw file contents when the ``Accept`` header
    includes ``application/vnd.github.v3.raw``.  This method is used when
    direct access to ``raw.githubusercontent.com`` returns nonâ€‘200 status codes.

    Parameters
    ----------
    owner: str
        Repository owner (user or organization).
    repo: str
        Repository name.
    branch: str
        Branch or ref to fetch from.
    path: str
        Path to the file within the repository.

    Returns
    -------
    Optional[str]
        The file contents as a string if successful, otherwise ``None``.
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    headers = {
        "Accept": "application/vnd.github.v3.raw",
        # Set a generic Userâ€‘Agent to reduce likelihood of being blocked.
        "User-Agent": "Mozilla/5.0 (compatible; V2RayConfigCollector/1.0)"
    }
    try:
        resp = requests.get(api_url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None


def _download_with_fallback(url: str) -> str | None:
    """Attempt to download a text file using multiple strategies.

    The primary method is a direct GET request to ``url``.  If that
    fails (nonâ€‘200 status), and the URL matches the pattern for raw
    GitHub content, the function falls back to using the GitHub API to
    retrieve the file content.

    Parameters
    ----------
    url: str
        The URL to fetch.

    Returns
    -------
    Optional[str]
        The downloaded text content, or ``None`` if all attempts fail.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; V2RayConfigCollector/1.0)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass

    # Attempt fallback via GitHub API if the URL is a raw GitHub link.
    m = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)", url)
    if m:
        owner, repo, branch, path = m.groups()
        return _get_text_from_github_api(owner, repo, branch, path)
    return None


def fetch_source(url: str) -> Iterable[str]:
    """Fetch a subscription file and return a list of configuration lines.

    Each fetched file may be plain text or base64 encoded.  Lines beginning
    with '#' are metadata and are ignored.  Only lines that appear to be
    configuration URLs (starting with ``vmess://``, ``vless://``, ``hy2://``,
    or ``hysteria2://``) are returned.

    Parameters
    ----------
    url: str
        The URL of the remote subscription file.

    Returns
    -------
    Iterable[str]
        A collection of configuration strings extracted from the source.
    """
    text: str | None = _download_with_fallback(url)
    if not text:
        print(f"Warning: failed to fetch {url}", file=sys.stderr)
        return []

    text = text.strip()

    # Some subscription files are a single base64â€‘encoded blob containing
    # meta lines and configuration links.  Detect this by checking whether
    # the content begins with an expected prefix.  If it does not start
    # with '#' (metadata) or a protocol, attempt base64 decoding.
    # Note: invalid base64 decoding is ignored gracefully.
    if not text.startswith("#") and not text.lower().startswith((
        "vmess://",
        "vless://",
        "hy2://",
        "hysteria2://",
    )):
        try:
            decoded_bytes = base64.b64decode(text)
            decoded_text = decoded_bytes.decode("utf-8", errors="ignore").strip()
            # If the decoded text contains at least one protocol prefix, use it.
            if any(prefix in decoded_text for prefix in ("vmess://", "vless://", "hy2://", "hysteria2://")):
                text = decoded_text
        except Exception:
            # If decoding fails, fall back to original text.
            pass

    configs: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip metadata lines beginning with '#'.
        if stripped.startswith("#"):
            continue
        # Accept only lines that start with known protocol prefixes.
        if stripped.lower().startswith(("vmess://", "vless://", "hy2://", "hysteria2://")):
            configs.append(stripped)
    return configs


REMARK = "☬ SHΞN Ai✨ v2ray Miner"
REDIRECT_SUBSCRIPTION_URL = "https://1kb.link/o402sP"
# Update the URL above to match your hosted subscription domain.
DEFAULT_PROFILE_TITLE_BASE64 = "4pisU0jOnk7ihKI="
HEALTH_CHECK_WORKERS = 40


def _extract_profile_title_base64(meta_lines: Iterable[str]) -> str:
    for line in meta_lines:
        lowered = line.lower()
        if lowered.startswith("#profile-title") and "base64:" in lowered:
            _, value = line.split("base64:", 1)
            value = value.strip()
            if value:
                return value
    return DEFAULT_PROFILE_TITLE_BASE64


def build_redirect_lines(meta_lines: Iterable[str]) -> List[str]:
    profile_title = _extract_profile_title_base64(meta_lines)
    redirect_url = f"hiddify://import/{REDIRECT_SUBSCRIPTION_URL}#{profile_title}"
    return [
        "<script>",
        f"window.location.href = '{redirect_url}';",
        "</script>",
        f"<a href=\"{redirect_url}\">{redirect_url}</a>",
    ]


def _decode_vmess_payload(payload: str) -> Optional[dict]:
    try:
        padded = payload + "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return None


def _encode_vmess_payload(data: dict) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    return encoded.decode("utf-8").rstrip("=")


def _remark_vmess(config: str) -> Optional[str]:
    payload = config[len("vmess://") :]
    data = _decode_vmess_payload(payload)
    if not data:
        return None
    data["ps"] = REMARK
    return f"vmess://{_encode_vmess_payload(data)}"


def _remark_url_fragment(config: str) -> str:
    parsed = urllib.parse.urlsplit(config)
    updated = parsed._replace(fragment=urllib.parse.quote(REMARK, safe=""))
    return urllib.parse.urlunsplit(updated)


def _parse_host_port_from_url(config: str) -> Optional[Tuple[str, int]]:
    parsed = urllib.parse.urlsplit(config)
    hostname = parsed.hostname
    port = parsed.port
    if not hostname or port is None:
        return None
    return hostname, port


def _parse_host_port_from_vmess(config: str) -> Optional[Tuple[str, int]]:
    payload = config[len("vmess://") :]
    data = _decode_vmess_payload(payload)
    if not data:
        return None
    host = data.get("add")
    port = data.get("port")
    if not host or port is None:
        return None
    try:
        return str(host), int(port)
    except (TypeError, ValueError):
        return None


def _tcp_connectable(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _resolvable(host: str) -> bool:
    try:
        socket.getaddrinfo(host, None)
        return True
    except Exception:
        return False


def is_healthy(config: str) -> bool:
    lowered = config.lower()
    if lowered.startswith("vmess://"):
        host_port = _parse_host_port_from_vmess(config)
        if not host_port:
            return False
        host, port = host_port
        return _tcp_connectable(host, port)
    if lowered.startswith("vless://"):
        host_port = _parse_host_port_from_url(config)
        if not host_port:
            return False
        host, port = host_port
        return _tcp_connectable(host, port)
    if lowered.startswith(("hy2://", "hysteria2://")):
        host_port = _parse_host_port_from_url(config)
        if not host_port:
            return False
        host, _port = host_port
        return _resolvable(host)
    return False


def normalize_config(config: str) -> Optional[str]:
    lowered = config.lower()
    if lowered.startswith("vmess://"):
        return _remark_vmess(config)
    if lowered.startswith(("vless://", "hy2://", "hysteria2://")):
        return _remark_url_fragment(config)
    return None


def read_existing_meta(index_path: pathlib.Path) -> List[str]:
    """Read the metadata lines from an existing Index.html file.

    Metadata lines begin with '#' and continue until the first non
    metadata line.  If the file does not exist, a default set of
    metadata is returned.

    Parameters
    ----------
    index_path: pathlib.Path
        Path to the Index.html file.

    Returns
    -------
    List[str]
        A list of metadata strings (without trailing newlines).
    """
    default_meta = [
        "#profile-title: base64:4pisU0jOnk7ihKI=",
        "#profile-update-interval: 1",
        "#subscription-userinfo: upload=0; download=0; total=0; expire=0",
        "#support-url: https://github.com/Shervinuri/Hiddifynext",
        "#profile-web-page-url: https://github.com/Shervinuri/Hiddifynext",
    ]
    if not index_path.exists():
        return default_meta
    meta_lines: List[str] = []
    try:
        with index_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("#"):
                    meta_lines.append(line.rstrip("\n"))
                else:
                    break
    except Exception:
        return default_meta
    # If no metadata lines were found, fall back to defaults.
    return meta_lines if meta_lines else default_meta


def update_index_file(index_path: pathlib.Path, meta_lines: Iterable[str], configs: Iterable[str]) -> None:
    """Write metadata and configuration links to the Index.html file.

    Parameters
    ----------
    index_path: pathlib.Path
        The path to the Index.html file to update.
    meta_lines: Iterable[str]
        Metadata lines to write at the top of the file.
    configs: Iterable[str]
        V2Ray configuration links to append after the metadata.
    """
    # Sort configurations deterministically for stable diffs.  Sorting by
    # lowercase ensures consistent order regardless of case.
    sorted_configs = sorted(set(configs), key=lambda x: x.lower())
    redirect_lines = build_redirect_lines(meta_lines)

    with index_path.open("w", encoding="utf-8") as f:
        for meta in meta_lines:
            f.write(meta.rstrip("\n") + "\n")
        for line in redirect_lines:
            f.write(line.rstrip("\n") + "\n")
        for config in sorted_configs:
            f.write(config.rstrip("\n") + "\n")


def main() -> None:
    index_path = pathlib.Path("Index.html")
    meta = read_existing_meta(index_path)

    all_configs: List[str] = []
    for src in SOURCES:
        fetched = list(fetch_source(src))
        for config in fetched:
            normalized = normalize_config(config)
            if not normalized:
                continue
            all_configs.append(normalized)
    if not all_configs:
        print("Warning: no configurations fetched from sources", file=sys.stderr)
        update_index_file(index_path, meta, [])
        return

    unique_configs = sorted(set(all_configs), key=lambda x: x.lower())
    healthy_configs: List[str] = []
    with ThreadPoolExecutor(max_workers=HEALTH_CHECK_WORKERS) as executor:
        future_map = {executor.submit(is_healthy, config): config for config in unique_configs}
        for future in as_completed(future_map):
            config = future_map[future]
            try:
                if future.result():
                    healthy_configs.append(config)
            except Exception:
                continue
    if not healthy_configs:
        print("Warning: no healthy configurations after checks", file=sys.stderr)
    update_index_file(index_path, meta, healthy_configs)


if __name__ == "__main__":
    main()
