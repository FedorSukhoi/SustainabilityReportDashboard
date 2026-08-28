"""Select a stable, official external source link for an ESG report."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


URL_PATTERN = re.compile(r"https?://[^\s<>()\]\[\"']+", re.I)
NON_SOURCE_TERMS = (
    "policy", "code-of-conduct", "supplier", "charter", "methodology",
    "assurance", "index", "databook", "supplement", "grievance",
    "human-rights", "modern-slavery",
)
SOURCE_TERMS = (
    "annual-report", "annual_reports", "annual-reports", "reporting",
    "sustainability", "responsibility", "esg", "tcfd", "disclosure",
    "appetite-for-a-better-world", "betterdayspromise",
)
GENERIC_DOMAINS = {
    "google.com", "www.google.com", "linkedin.com", "www.linkedin.com",
    "youtube.com", "www.youtube.com", "facebook.com", "www.facebook.com",
}


def _clean_url(value: str) -> str | None:
    value = value.strip().rstrip(".,;:)")
    if not value.lower().startswith(("http://", "https://")):
        return None
    parts = urlsplit(value)
    if not parts.hostname or parts.hostname.lower() in GENERIC_DOMAINS:
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def _pdf_urls(path: Path) -> list[str]:
    helper = r'''
import json, re, sys
from pypdf import PdfReader
urls=[]
for page in PdfReader(sys.argv[1]).pages:
    for ref in page.get('/Annots') or []:
        try:
            obj=ref.get_object(); action=obj.get('/A'); uri=action.get('/URI') if action else None
            if uri: urls.append(str(uri))
        except Exception:
            pass
    urls.extend(re.findall(r'https?://[^\s<>()\]\[\"\']+', page.extract_text() or '', re.I))
print(json.dumps(urls))
'''
    interpreters = [Path(sys.executable)]
    external = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
    if external.exists() and external.resolve() != Path(sys.executable).resolve():
        interpreters.append(external)
    for interpreter in interpreters:
        completed = subprocess.run(
            [str(interpreter), "-c", helper, str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
        )
        if completed.returncode == 0:
            try:
                return json.loads(completed.stdout)
            except json.JSONDecodeError:
                pass
    return []


def extract_urls(path: Path) -> list[str]:
    path = Path(path)
    raw = _pdf_urls(path) if path.suffix.lower() == ".pdf" else URL_PATTERN.findall(
        path.read_text(encoding="utf-8", errors="ignore")
    )
    unique = []
    for value in raw:
        cleaned = _clean_url(value)
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return unique


def _host_matches(host: str, official_host: str) -> bool:
    host, official_host = host.lower().removeprefix("www."), official_host.lower().removeprefix("www.")
    return host == official_host or host.endswith("." + official_host)


def choose_source_url(
    report_path: Path,
    company: str,
    official_website: str | None = None,
) -> tuple[str | None, str]:
    """Prefer an official report/reporting URL; otherwise use the official site."""
    report_path = Path(report_path)
    urls = extract_urls(report_path)
    official_host = urlsplit(official_website or "").hostname or ""
    company_tokens = {
        token for token in re.findall(r"[a-z]{4,}", company.lower())
        if token not in {"group", "foods", "systems", "company", "holdings"}
    }
    stem = report_path.stem.lower()
    sustainability_report = "sustainability" in stem or bool(re.search(r"sr\d{2}", stem))
    annual_report = "annual" in stem
    years = set(re.findall(r"20\d{2}", stem))

    candidates = []
    for position, url in enumerate(urls):
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        low = url.lower()
        first_party = bool(official_host and _host_matches(host, official_host))
        token_match = any(token in host for token in company_tokens)
        if official_host and not first_party:
            continue
        if not official_host and not token_match:
            continue
        score = 100 if first_party else 55
        score += 28 if any(term in low for term in SOURCE_TERMS) else 0
        score += 10 if low.endswith(".pdf") else 0
        score += 14 if any(year in low for year in years) else 0
        score -= 25 if any(term in low for term in NON_SOURCE_TERMS) else 0
        if sustainability_report:
            score += 24 if any(term in low for term in ("sustainability", "responsibility", "esg", "appetite-for-a-better-world", "betterdayspromise")) else 0
            score -= 24 if "annual-report" in low else 0
        if annual_report:
            score += 18 if "annual-report" in low or "annual_reports" in low or "investor" in low else 0
            score -= 12 if "tcfd" in low else 0
        candidates.append((score, -position, url))

    if candidates:
        return max(candidates)[2], "official report link found in source"
    if official_website and official_website != "#":
        return official_website, "official company website fallback"
    return None, "no external official link available"
