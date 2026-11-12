#!/usr/bin/env python3
"""Sums (or counts) first-party GHSA advisories for a package over a trailing
window and compares against a user-set threshold.

Uses GitHub's global Security Advisories API
(GET /advisories?ecosystem=...&affects=...), which is keyed by
ecosystem + package name, not by repository — there is no "advisories
against my repo" endpoint. The caller supplies ecosystem/package explicitly;
this script does not attempt to auto-detect them.
"""
import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

GITHUB_API = "https://api.github.com"

# Fallback when an advisory has no numeric CVSS score, only a severity string.
SEVERITY_FALLBACK = {
    "low": 2.5,
    "medium": 5.0,
    "moderate": 5.0,
    "high": 7.5,
    "critical": 9.5,
}


def fetch_advisories(ecosystem: str, package: str, token: str) -> list[dict]:
    advisories = []
    url = (
        f"{GITHUB_API}/advisories"
        f"?ecosystem={urllib.parse.quote(ecosystem)}"
        f"&affects={urllib.parse.quote(package)}"
        f"&per_page=100"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    while url:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                page = json.loads(resp.read().decode("utf-8"))
                advisories.extend(page)
                url = _next_link(resp.headers.get("Link"))
        except urllib.error.HTTPError as e:
            print(f"GHSA API request failed: {e.code} {e.reason}", file=sys.stderr)
            raise

    return advisories


def _next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        segment = part.strip()
        if segment.endswith('rel="next"'):
            return segment[segment.index("<") + 1 : segment.index(">")]
    return None


def score_of(advisory: dict) -> float:
    """CVSS v3.1 preferred; falls back to severity string."""
    cvss = advisory.get("cvss") or {}
    score = cvss.get("score")
    if isinstance(score, (int, float)):
        return float(score)

    severity = (advisory.get("severity") or "").lower()
    return SEVERITY_FALLBACK.get(severity, 0.0)


def in_window(advisory: dict, window_months: int) -> bool:
    published_at = advisory.get("published_at")
    if not published_at:
        return False
    published = datetime.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=window_months * 30
    )
    return published >= cutoff


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ecosystem", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--mode", choices=["cvss-sum", "count"], default="cvss-sum")
    parser.add_argument("--threshold", type=float, default=30.0)
    parser.add_argument("--window-months", type=int, default=6)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    advisories = fetch_advisories(args.ecosystem, args.package, token)
    windowed = [a for a in advisories if in_window(a, args.window_months)]

    if args.mode == "count":
        value = float(len(windowed))
    else:
        value = sum(score_of(a) for a in windowed)

    triggered = value >= args.threshold

    print(
        f"ecosystem={args.ecosystem} package={args.package} "
        f"mode={args.mode} window_months={args.window_months} "
        f"advisories_in_window={len(windowed)} value={value} "
        f"threshold={args.threshold} triggered={triggered}"
    )

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"triggered={'true' if triggered else 'false'}\n")
            f.write(f"cvss-sum={value}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
