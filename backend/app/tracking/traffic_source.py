"""
Classifies a (referrer, utm_source, utm_medium) triple into one of the
buckets from the spec: Direct, Google/Bing/Yahoo/DuckDuckGo Search,
LinkedIn/Facebook/Twitter(X)/Reddit/GitHub, Referral Website, or Email
Campaign. UTM parameters win when present (explicit attribution), then we
fall back to pattern-matching the referrer's domain.
"""

from __future__ import annotations

from urllib.parse import urlparse

_SEARCH_ENGINES = {
    "google": "Google Search",
    "bing": "Bing",
    "yahoo": "Yahoo",
    "duckduckgo": "DuckDuckGo",
    "baidu": "Baidu",
    "yandex": "Yandex",
}

_SOCIAL_NETWORKS = {
    "linkedin.com": "LinkedIn",
    "facebook.com": "Facebook",
    "lm.facebook.com": "Facebook",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "t.co": "Twitter/X",
    "reddit.com": "Reddit",
    "github.com": "GitHub",
}


def _domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return netloc[4:] if netloc.startswith("www.") else netloc


def classify_traffic_source(
    referrer: str | None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
) -> str:
    if utm_medium and utm_medium.lower() in ("email", "newsletter"):
        return "Email Campaign"
    if utm_source:
        source = utm_source.lower()
        for key, label in _SEARCH_ENGINES.items():
            if key in source:
                return label
        for domain, label in _SOCIAL_NETWORKS.items():
            if domain.split(".")[0] in source:
                return label
        return f"UTM: {utm_source}"

    if not referrer:
        return "Direct"

    domain = _domain(referrer)
    if not domain:
        return "Direct"

    for key, label in _SEARCH_ENGINES.items():
        if key in domain:
            return label
    for social_domain, label in _SOCIAL_NETWORKS.items():
        if domain == social_domain or domain.endswith("." + social_domain):
            return label

    return "Referral Website"
