"""
A script to automatically fetch and combine V2Ray configuration links from multiple
public subscription sources and update the repository's ``Index.html`` file.

This script is designed to run periodically via the GitHub Actions workflow
defined in ``.github/workflows/main.yml``.  It downloads V2Ray/Vmess/VLess/Trojan
configuration links from several external providers, deduplicates them, and
writes them back into the ``Index.html`` file in this repository.  Any
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
import pathlib
import re
import sys
from typing import Iterable, List

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
    configuration URLs (starting with ``vmess://``, ``vless://``, ``trojan://``,
    ``ss://``, ``ssr://``, ``hy2://``, or ``hysteria://``) are returned.

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
        "trojan://",
        "ss://",
        "ssr://",
        "hy2://",
        "hysteria://",
    )):
        try:
            decoded_bytes = base64.b64decode(text)
            decoded_text = decoded_bytes.decode("utf-8", errors="ignore").strip()
            # If the decoded text contains at least one protocol prefix, use it.
            if any(prefix in decoded_text for prefix in ("vmess://", "vless://", "trojan://", "ss://", "ssr://")):
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
        if stripped.lower().startswith((
            "vmess://",
            "vless://",
            "trojan://",
            "ss://",
            "ssr://",
            "hy2://",
            "hysteria://",
        )):
            configs.append(stripped)
    return configs


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

    with index_path.open("w", encoding="utf-8") as f:
        for meta in meta_lines:
            f.write(meta.rstrip("\n") + "\n")
        for config in sorted_configs:
            f.write(config.rstrip("\n") + "\n")


def main() -> None:
    index_path = pathlib.Path("Index.html")
    meta = read_existing_meta(index_path)

    all_configs: List[str] = []
    for src in SOURCES:
        fetched = list(fetch_source(src))
        all_configs.extend(fetched)
    if not all_configs:
        print("Warning: no configurations fetched from sources", file=sys.stderr)
    update_index_file(index_path, meta, all_configs)


if __name__ == "__main__":
    main()
