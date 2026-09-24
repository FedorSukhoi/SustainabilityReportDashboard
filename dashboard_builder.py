"""Build one auditable, self-contained ESG HTML dashboard per company."""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit


PROFILES = {
    "DHL Group": {
        "short": "DHL",
        "headquarters": "Bonn, Germany",
        "founded": "1969",
        "workforce": "583,998 employees (2025)",
        "website": "https://group.dhl.com/",
        "sector": "Logistics & delivery",
        "about": [
            "DHL Group is a global logistics company spanning express delivery, freight forwarding, supply-chain services, e-commerce logistics, and postal operations.",
            "Its 2025 sustainability presentation reports 583,998 employees across a network serving more than 220 countries and territories, creating a broad operational footprint for environmental and workforce oversight.",
            "This assessment evaluates disclosed ESG evidence and detected standards from the supplied report. Numeric claims shown below passed the analyzer’s automated locality and ambiguity checks.",
        ],
    },
    "H&M Group": {
        "short": "H&M",
        "headquarters": "Stockholm, Sweden",
        "founded": "1947",
        "workforce": "132,403 employees (2025)",
        "website": "https://hmgroup.com/",
        "sector": "Fashion retail",
        "about": [
            "H&M Group is a global fashion and design company operating a multi-brand retail portfolio supported by an international sourcing and supplier network.",
            "The 2025 report lists 4,101 stores and 132,403 employees, placing operational energy, supply-chain emissions, workforce practices, and circular resource use at the center of its ESG profile.",
            "This dashboard separates narrative disclosure from accepted numeric evidence. Figures are published only when the analyzer can associate them with a local metric label and resolve competing candidates.",
        ],
    },
    "Lufthansa Group": {
        "short": "LH",
        "headquarters": "Cologne, Germany",
        "founded": "1953",
        "workforce": "103,255 employees (2025)",
        "website": "https://www.lufthansagroup.com/",
        "sector": "Aviation",
        "about": [
            "Lufthansa Group combines passenger airlines with logistics, maintenance, repair and overhaul, and aviation-related services across an international operating network.",
            "Its 2025 Sustainability Fact Sheet reports 103,255 employees and provides audited Scope 1–3 disclosures alongside resource, workforce, governance, and responsible-business indicators.",
            "The dashboard prioritizes traceability: accepted metrics link to the source document, while unresolved candidate groups are excluded from KPI presentation and counted in the audit summary.",
        ],
    },
    "Vestas Wind Systems A/S": {
        "short": "V",
        "headquarters": "Aarhus, Denmark",
        "founded": "1945",
        "workforce": "36,973 employees (2025)",
        "website": "https://www.vestas.com/",
        "sector": "Wind energy",
        "about": [
            "Vestas Wind Systems A/S develops, manufactures, installs, and services wind turbines, positioning the company across the full lifecycle of renewable-energy infrastructure.",
            "The 2025 Annual Report lists 36,973 employees and reports environmental impacts from manufacturing, global transport, operations, suppliers, product circularity, and workforce safety.",
            "This assessment combines disclosure scoring with conservative evidence resolution. The visible KPI set contains accepted actuals; ambiguous values and numeric targets cannot silently replace reported performance.",
        ],
    },
    "Flora Food Group": {
        "short": "FFG",
        "headquarters": "Amsterdam, Netherlands",
        "founded": "2018",
        "workforce": "4,580 employees (2025)",
        "website": "https://www.florafoodgroup.com/",
        "sector": "Food manufacturing",
        "about": [
            "Flora Food Group develops culinary products across spreads, creams, oils, fats, and plant-based foods for retail, foodservice, and industrial customers.",
            "Its 2025 report describes operations serving more than 100 countries and a workforce of 4,580 employees, with material impacts spanning nutrition, sourcing, climate, packaging, and workplace safety.",
            "The dashboard distinguishes operational performance from avoided-impact claims and targets, publishing only numeric actuals that pass the analyzer's evidence-resolution gate.",
        ],
    },
    "Kellanova": {
        "short": "K",
        "headquarters": "Chicago, Illinois, United States",
        "founded": "1906",
        "workforce": "Not disclosed in source",
        "website": "https://www.kellanova.com/",
        "sector": "Food manufacturing",
        "about": [
            "Kellanova manufactures and markets snacks and convenience foods through an international portfolio of consumer brands.",
            "The supplied 2025 climate-related financial risk report focuses on governance, transition and physical climate risks, scenario analysis, emissions, and decarbonization commitments.",
            "Because this is a focused TCFD disclosure rather than a full sustainability report, absent social or governance metrics are treated as undisclosed, not estimated.",
        ],
    },
    "Nomad Foods": {
        "short": "NF",
        "headquarters": "United Kingdom",
        "founded": "2014",
        "workforce": "7,500+ employees (2025)",
        "website": "https://www.nomadfoods.com/",
        "sector": "Frozen food",
        "about": [
            "Nomad Foods manufactures, sells, and distributes branded frozen food products across 22 European markets.",
            "Its 2025 Sustainability Report covers responsible sourcing, nutrition, operational emissions, packaging, water, workforce engagement, ethics, and governance for a team of more than 7,500 people.",
            "Reported actuals are separated from 2030 commitments so future targets cannot be presented as current operating performance.",
        ],
    },
    "Ahold Delhaize": {
        "short": "AD",
        "headquarters": "Zaandam, Netherlands",
        "founded": "2016",
        "workforce": "384,000 employees (2025)",
        "website": "https://www.aholddelhaize.com/",
        "sector": "Food retail & e-commerce",
        "about": [
            "Ahold Delhaize operates local food-retail and e-commerce brands across the United States and Europe.",
            "The 2025 Annual Report lists 9,551 stores and approximately 384,000 employees, with ESG disclosures spanning energy, emissions, water, workforce engagement, sourcing, ethics, and board oversight.",
            "Table magnitudes such as thousands, GWh, and MtCO2e are normalized before scoring, while competing current- and prior-period figures are resolved conservatively.",
        ],
    },
}


FALLBACK_PROFILE = {
    "short": "ESG",
    "headquarters": "See source report",
    "founded": "See source report",
    "workforce": "See source report",
    "website": "#",
    "sector": "Corporate ESG assessment",
    "about": [
        "This company dashboard summarizes environmental, social, and governance disclosures identified in the supplied sustainability report.",
        "The analyzer evaluates both narrative coverage and metric-specific numeric evidence while preserving the source report as the primary record.",
        "Only resolved actual values are displayed as KPIs. Ambiguous numeric groups are excluded automatically and remain documented in the analysis output.",
    ],
}


ICON_PATHS = {
    "pin": '<path d="M12 21s6-5.35 6-12a6 6 0 1 0-12 0c0 6.65 6 12 6 12Z"/><circle cx="12" cy="9" r="2.2"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h6"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "arrow": '<path d="M7 17 17 7M7 7h10v10"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
    "leaf": '<path d="M20 4c-7 0-12 4-12 10 0 3 2 5 5 5 6 0 7-8 7-15Z"/><path d="M4 20c3-5 7-8 13-11"/>',
    "bolt": '<path d="m13 2-9 12h8l-1 8 9-12h-8l1-8Z"/>',
    "wind": '<path d="M3 8h11a3 3 0 1 0-3-3M3 12h16a2 2 0 1 1-2 2M3 16h9"/>',
    "drop": '<path d="M12 2S5 10 5 15a7 7 0 0 0 14 0c0-5-7-13-7-13Z"/>',
    "recycle": '<path d="m7 19-3-5 3-5M4 14h6M17 5l3 5-3 5M20 10h-6M8 6l4-4 4 4M12 2v6"/>',
    "people": '<circle cx="8" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M2 20c0-4 2-7 6-7s6 3 6 7M14 14c4 0 6 2 6 6"/>',
    "governance": '<path d="M3 10h18M5 10v8M9 10v8M15 10v8M19 10v8M3 20h18M12 3l9 5H3l9-5Z"/>',
}


def esc(value):
    return html.escape(str(value), quote=True)


def icon(name, size=18):
    path = ICON_PATHS.get(name, ICON_PATHS["file"])
    return f'<svg class="icon" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>'


def score_label(score):
    from scoring import grade_from_score

    grade = grade_from_score(float(score or 0))
    return ("Starter" if grade == "F" else grade), {
        "A": "green", "B": "blue", "C": "amber", "D": "amber", "F": "slate"
    }[grade]


def format_number(value, unit):
    value = float(value)
    if unit == "%":
        return f"{value:g}%"
    if unit == "rate":
        return f"{value:g}"
    if abs(value) >= 1_000_000:
        number = f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "m"
    elif abs(value) >= 1_000:
        number = f"{value:,.0f}"
    elif value.is_integer():
        number = f"{value:,.0f}"
    else:
        number = f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{number} {unit}".strip()


def report_href(report_path, html_path, page=None):
    relative = os.path.relpath(Path(report_path), html_path.parent)
    href = "/".join(quote(part) for part in Path(relative).parts)
    if page and Path(report_path).suffix.lower() == ".pdf":
        href += f"#page={int(float(page))}"
    return href


def get_profile(company):
    return PROFILES.get(company, {**FALLBACK_PROFILE, "short": company[:2].upper()})


def source_href(data, profile, html_path, page=None):
    """Use the stored official external source; retain local paths only as a fallback."""
    source = data.get("source_url") or profile.get("website")
    if not source or source == "#":
        return report_href(Path(data["report"]), html_path, page)
    if page and urlsplit(source).path.lower().endswith(".pdf"):
        parts = urlsplit(source)
        source = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, f"page={int(float(page))}"))
    return source


def matching_evidence(data, primary):
    for row in data.get("accepted_values", []):
        if (
            row.get("Metric") == primary.get("Metric")
            and row.get("Unit") == primary.get("Unit")
            and row.get("Variant", "default") == primary.get("Variant", "default")
            and str(row.get("Year")) == str(primary.get("Year"))
            and math.isclose(float(row.get("Value", 0)), float(primary.get("Value", 0)), rel_tol=1e-9)
        ):
            return row
    return {}


def metric_icon(metric):
    low = metric.lower()
    if "energy" in low:
        return "bolt"
    if "emission" in low or "carbon" in low:
        return "wind"
    if "water" in low:
        return "drop"
    if "waste" in low or "circular" in low:
        return "recycle"
    if any(word in low for word in ("employee", "women", "gender", "training", "safety", "turnover")):
        return "people"
    if any(word in low for word in ("board", "ethics", "corruption", "privacy", "governance")):
        return "governance"
    return "leaf"


def build_sidebar_field(icon_name, label, value, href=None):
    rendered = f'<a href="{esc(href)}" target="_blank" rel="noopener">{esc(value)} {icon("arrow", 14)}</a>' if href and href != "#" else esc(value)
    return f'''<div class="meta-row"><span class="meta-icon">{icon(icon_name)}</span><div><span class="eyebrow">{esc(label)}</span><div class="meta-value">{rendered}</div></div></div>'''


def render_dashboard(data, output_path: Path):
    company = data["company"]
    profile = get_profile(company)
    overall_label, overall_tone = score_label(data.get("overall_score", 0))
    report_path = Path(data["report"])
    canonical_source_href = source_href(data, profile, output_path)
    verified = date.today().strftime("%d %b %Y").upper()

    category_map = {row["Category"]: row["Score"] for row in data.get("category_scores", [])}
    pillar_cards = []
    pillar_icons = {"Environmental": "leaf", "Social": "people", "Governance": "governance"}
    for category in ("Environmental", "Social", "Governance"):
        score = float(category_map.get(category, 0))
        label, tone = score_label(score)
        pillar_cards.append(f'''
        <article class="pillar">
          <div class="pillar-top"><span class="pillar-icon {tone}">{icon(pillar_icons[category])}</span><span class="badge {tone}">{esc(label)}</span></div>
          <h3>{esc(category)}</h3><div class="pillar-score">{score:.1f}<span>/100</span></div>
          <div class="meter"><span style="width:{max(2, min(100, score)):.1f}%"></span></div>
        </article>''')

    scored_metrics = sorted(
        [row for row in data.get("metric_scores", []) if float(row.get("Total", 0)) > 0],
        key=lambda row: (float(row.get("Weighted Score", 0)), float(row.get("Total", 0))),
        reverse=True,
    )
    areas, seen = [], set()
    for row in scored_metrics:
        name = row["Metric"]
        if name in seen:
            continue
        seen.add(name)
        areas.append(f'<span class="area-chip">{icon(metric_icon(name), 16)}{esc(name)}</span>')
        if len(areas) == 6:
            break

    evidence_cards = []
    for primary in data.get("primary_values", [])[:8]:
        evidence = matching_evidence(data, primary)
        page = evidence.get("Page")
        href = source_href(data, profile, output_path, page)
        source_label = report_path.name + (f" · p. {int(float(page))}" if page else "")
        method = str(primary.get("Source", "direct")).replace("_", " ").title()
        variant = primary.get("Variant", "default")
        metric_label = primary["Metric"] + (f" ({variant})" if variant != "default" else "")
        year = primary.get("Year")
        year_source = str(primary.get("Year Source") or "undated").replace("_", " ")
        period_label = f"Reporting year {year} · {year_source}" if year else "Reporting year not explicit"
        evidence_cards.append(f'''
        <article class="evidence-card">
          <div class="evidence-head"><span class="category-dot {esc(primary['Category'].lower())}"></span><span>{esc(primary['Category'])}</span><span class="confidence">{float(primary.get('Confidence', 0)):.0f}% confidence</span></div>
          <h3>{esc(metric_label)}</h3>
          <div class="evidence-value">{esc(format_number(primary['Value'], primary['Unit']))}</div>
          <div class="source-meta">{icon('file', 15)}<span>{esc(source_label)}</span></div>
          <div class="source-meta">{icon('shield', 15)}<span>{esc(method)} · automated resolution accepted</span></div>
          <div class="source-meta">{icon('calendar', 15)}<span>{esc(period_label)}</span></div>
          <a class="text-link" href="{esc(href)}" target="_blank" rel="noopener">VIEW SOURCE {icon('arrow', 14)}</a>
        </article>''')
    if not evidence_cards:
        evidence_cards.append('<div class="empty-state">No numeric evidence passed the automated resolution gate. Narrative disclosure scores remain available above.</div>')

    certificates = []
    for item in data.get("certifications", []):
        cert = item.get("Certification", "Detected standard")
        certificates.append(f'''
        <article class="certificate-card">
          <div class="cert-mark">{icon('shield', 20)}</div>
          <div class="cert-copy"><span class="eyebrow">DETECTED REFERENCE</span><h3>{esc(cert)}</h3><p>Reported in the analyzed source · validity to be confirmed with the issuer.</p></div>
          <a class="small-button" href="{esc(canonical_source_href)}" target="_blank" rel="noopener">VIEW REPORT {icon('arrow', 13)}</a>
        </article>''')
    if not certificates:
        certificates.append('<div class="empty-state">No configured certification references were detected in this report.</div>')

    about = "".join(f"<p>{esc(paragraph)}</p>" for paragraph in profile["about"])
    index_score = float(data.get("overall_score", 0))
    report_year_match = re.findall(r"20\d{2}", report_path.name)
    report_year = report_year_match[-1] if report_year_match else "See report"

    sidebar = "".join([
        build_sidebar_field("pin", "Headquarters", profile["headquarters"]),
        build_sidebar_field("calendar", "Founded", profile["founded"]),
        build_sidebar_field("users", "Workforce", profile["workforce"]),
        build_sidebar_field("link", "Website", profile["website"], profile["website"]),
        build_sidebar_field("file", "Source report", report_path.name, canonical_source_href),
        build_sidebar_field("clock", "Last verified", verified),
    ])

    css = r'''
:root{--ink:#102a2e;--muted:#64777a;--line:#dce7e6;--paper:#f5f8f7;--card:#fff;--cyan:#18b8c6;--cyan-soft:#e7f8fa;--green:#15865d;--green-soft:#e8f6ef;--blue:#2f6fcb;--blue-soft:#edf4ff;--amber:#a66a10;--amber-soft:#fff5df;--slate:#617174;--slate-soft:#eef2f2;--radius:15px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.55}.page{max-width:1440px;margin:auto;padding:28px 32px 56px}.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}.brand{display:flex;align-items:center;gap:10px;font-size:13px;font-weight:800;letter-spacing:.08em}.brand-mark{width:30px;height:30px;border-radius:9px;background:var(--ink);color:#fff;display:grid;place-items:center}.audit-chip{font-size:12px;color:var(--muted);border:1px solid var(--line);background:#fff;border-radius:999px;padding:7px 11px}.hero{background:linear-gradient(125deg,#102d31 0%,#173e42 70%,#1b5054 100%);color:#fff;border-radius:20px;padding:30px 34px;margin-bottom:20px;display:flex;align-items:flex-end;justify-content:space-between;gap:28px;overflow:hidden;position:relative}.hero:after{content:"";position:absolute;width:290px;height:290px;border-radius:50%;background:rgba(24,184,198,.12);right:-70px;top:-150px}.hero-copy{position:relative;z-index:1}.hero .kicker{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#9fe6eb;font-weight:800}.hero h1{font-size:clamp(30px,4vw,51px);line-height:1.05;margin:8px 0 10px;letter-spacing:-.04em}.hero p{margin:0;color:#cce0e2;max-width:720px}.hero-score{position:relative;z-index:1;min-width:190px;text-align:right}.hero-score strong{font-size:52px;line-height:1;letter-spacing:-.05em}.hero-score span{color:#bcd4d6}.shell{display:grid;grid-template-columns:minmax(0,1.85fr) minmax(310px,1fr);gap:20px;align-items:start}.main{display:grid;gap:20px}.sidebar{position:sticky;top:18px}.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:25px}.section-title{display:flex;align-items:center;gap:11px;margin-bottom:18px}.accent{width:4px;height:25px;border-radius:99px;background:var(--cyan)}h2{font-size:20px;line-height:1.25;margin:0;letter-spacing:-.02em}.about-copy{color:#40575a;font-size:15px;max-width:940px}.about-copy p{margin:0 0 13px}.about-copy p:last-child{margin-bottom:0}.methodology{display:flex;gap:12px;align-items:flex-start;background:var(--blue-soft);border:1px solid #d9e8ff;border-radius:12px;padding:14px 16px;margin-bottom:18px;color:#355573;font-size:14px}.methodology strong{color:#173f67}.pillars{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.pillar{border:1px solid var(--line);border-radius:13px;padding:17px;min-width:0}.pillar-top{display:flex;align-items:center;justify-content:space-between}.pillar-icon{width:35px;height:35px;border-radius:10px;display:grid;place-items:center}.pillar h3{font-size:14px;margin:15px 0 3px}.pillar-score{font-size:26px;font-weight:800;letter-spacing:-.03em}.pillar-score span{font-size:12px;color:var(--muted);font-weight:600}.meter{height:5px;background:#edf2f1;border-radius:99px;overflow:hidden;margin-top:12px}.meter span{display:block;height:100%;background:var(--cyan);border-radius:99px}.badge{font-size:11px;font-weight:800;border-radius:999px;padding:5px 9px}.green{color:var(--green);background:var(--green-soft)}.blue{color:var(--blue);background:var(--blue-soft)}.amber{color:var(--amber);background:var(--amber-soft)}.slate{color:var(--slate);background:var(--slate-soft)}.areas{display:flex;flex-wrap:wrap;gap:9px}.area-chip{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);border-radius:999px;padding:8px 11px;background:#fbfdfc;color:#294347;font-size:13px;font-weight:700}.evidence-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.evidence-card{border:1px solid var(--line);border-radius:13px;padding:18px;display:flex;flex-direction:column;min-height:220px}.evidence-head{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em;font-weight:800}.category-dot{width:7px;height:7px;border-radius:50%;background:var(--cyan)}.category-dot.social{background:#5d7adf}.category-dot.governance{background:#8558b5}.confidence{margin-left:auto;text-transform:none;letter-spacing:0}.evidence-card h3{font-size:14px;margin:18px 0 3px}.evidence-value{font-size:28px;font-weight:850;letter-spacing:-.03em;margin-bottom:16px}.source-meta{display:flex;align-items:flex-start;gap:7px;color:var(--muted);font-size:12px;margin:3px 0}.text-link{display:inline-flex;align-items:center;gap:5px;color:#087c88;font-size:11px;font-weight:900;letter-spacing:.08em;text-decoration:none;margin-top:auto;padding-top:15px}.text-link:hover,.meta-value a:hover{text-decoration:underline}.certificate-list{display:grid;gap:10px}.certificate-card{display:grid;grid-template-columns:42px minmax(0,1fr) auto;gap:13px;align-items:center;border:1px solid var(--line);border-radius:12px;padding:13px}.cert-mark{width:40px;height:40px;border-radius:11px;background:var(--green-soft);color:var(--green);display:grid;place-items:center}.cert-copy h3{font-size:14px;margin:2px 0}.cert-copy p{font-size:12px;color:var(--muted);margin:0}.small-button{display:inline-flex;align-items:center;gap:5px;text-decoration:none;border:1px solid #b7dfe2;color:#087c88;border-radius:999px;padding:8px 10px;font-size:10px;font-weight:900;letter-spacing:.07em}.company-card{padding:0;overflow:hidden}.company-head{background:#f8fbfa;border-bottom:1px solid var(--line);padding:25px}.monogram{width:56px;height:56px;border-radius:15px;background:var(--ink);color:#fff;display:grid;place-items:center;font-size:19px;font-weight:900;margin-bottom:18px}.company-head h2{font-size:25px;margin-bottom:5px}.sector{font-size:13px;color:var(--muted);margin-bottom:14px}.status-row{display:flex;align-items:center;justify-content:space-between;gap:12px}.status-pill{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:7px 10px;font-size:12px;font-weight:850}.index-mini{font-size:12px;color:var(--muted)}.index-mini strong{font-size:16px;color:var(--ink)}.meta-list{padding:10px 25px 20px}.meta-row{display:grid;grid-template-columns:32px 1fr;gap:10px;padding:15px 0;border-bottom:1px solid #edf2f1}.meta-row:last-child{border-bottom:0}.meta-icon{color:#759093;padding-top:2px}.eyebrow{display:block;color:#7b8e90;font-size:9px;line-height:1.3;font-weight:900;letter-spacing:.12em;text-transform:uppercase}.meta-value{font-size:13px;font-weight:750;margin-top:3px;overflow-wrap:anywhere}.meta-value a{color:var(--ink);text-decoration:none;display:inline-flex;align-items:center;gap:3px}.audit-box{margin:0 25px 25px;background:var(--cyan-soft);border:1px solid #c7ecef;border-radius:12px;padding:14px}.audit-box h3{font-size:12px;margin:0 0 9px}.audit-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.audit-stat strong{display:block;font-size:18px}.audit-stat span{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}.empty-state{color:var(--muted);font-size:14px;border:1px dashed var(--line);border-radius:12px;padding:18px}.footer{display:flex;justify-content:space-between;gap:20px;margin-top:20px;padding:4px 2px;color:var(--muted);font-size:11px}.icon{flex:0 0 auto}.screen-reader{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
@media(max-width:1000px){.shell{grid-template-columns:1fr}.sidebar{position:static;order:-1}.company-card{display:grid;grid-template-columns:minmax(260px,.8fr) 1.2fr}.company-head{border-bottom:0;border-right:1px solid var(--line)}.audit-box{grid-column:1/-1}.meta-list{display:grid;grid-template-columns:repeat(2,1fr);column-gap:20px}}
@media(max-width:700px){.page{padding:16px}.topbar{align-items:flex-start}.audit-chip{display:none}.hero{padding:24px;display:block}.hero-score{text-align:left;margin-top:22px}.shell{gap:14px}.card{padding:19px}.pillars,.evidence-grid{grid-template-columns:1fr}.company-card{display:block}.company-head{border-right:0;border-bottom:1px solid var(--line)}.meta-list{display:block}.certificate-card{grid-template-columns:40px 1fr}.small-button{grid-column:2;justify-self:start}.footer{display:block}.footer span{display:block;margin:4px 0}}
@media print{body{background:#fff}.page{max-width:none;padding:0}.sidebar{position:static}.text-link,.small-button{display:none}.card,.hero{break-inside:avoid}}
'''

    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Auditable ESG dashboard for {esc(company)}"><title>{esc(company)} · ESG assessment</title><style>{css}</style></head>
<body><div class="page">
  <header class="topbar"><div class="brand"><span class="brand-mark">I</span> IMPAKTER ESG AUDIT</div><div class="audit-chip">Automated evidence review · {verified}</div></header>
  <section class="hero"><div class="hero-copy"><div class="kicker">{esc(profile['sector'])} · Sustainability assessment</div><h1>{esc(company)}</h1><p>Evidence-led ESG profile generated from {esc(report_path.name)} using the Impakter Index scoring workflow.</p></div><div class="hero-score"><strong>{index_score:.1f}</strong><span>/100<br>Impakter Index</span></div></section>
  <div class="shell">
    <main class="main">
      <section class="card"><div class="section-title"><span class="accent"></span><h2>About {esc(company)}</h2></div><div class="about-copy">{about}</div></section>
      <section class="card"><div class="section-title"><span class="accent"></span><h2>Sustainability overview</h2></div><div class="methodology">{icon('shield',20)}<div><strong>Methodology note.</strong> The index weights Environmental 70%, Social 20%, and Governance 10%, then adds one point per detected certification or standard (maximum 10), capped at 100. Grades: A &gt;80, B &gt;70, C &gt;55, D &gt;25; otherwise Starter (F). Scores are rounded to one decimal before grading. Report disclosure and performance signals remain the scoring inputs; certification mentions are not validated certificates. Utilities and questionnaires are excluded.</div></div><div class="pillars">{''.join(pillar_cards)}</div></section>
      <section class="card"><div class="section-title"><span class="accent"></span><h2>Key sustainability areas</h2></div><div class="areas">{''.join(areas)}</div></section>
      <section class="card"><div class="section-title"><span class="accent"></span><h2>Certificates & standards</h2></div><div class="certificate-list">{''.join(certificates)}</div></section>
      <section class="card"><div class="section-title"><span class="accent"></span><h2>Sustainability evidence</h2></div><div class="evidence-grid">{''.join(evidence_cards)}</div></section>
    </main>
    <aside class="sidebar"><section class="card company-card"><div class="company-head"><div class="monogram">{esc(profile['short'])}</div><h2>{esc(company)}</h2><div class="sector">{esc(profile['sector'])}</div><div class="status-row"><span class="status-pill {overall_tone}">{icon('check',15)} ESG profile: {esc(overall_label)}</span><span class="index-mini"><strong>{index_score:.1f}</strong> /100</span></div></div><div class="meta-list">{sidebar}</div><div class="audit-box"><h3>Evidence resolution</h3><div class="audit-stats"><div class="audit-stat"><strong>{int(data.get('values_total',0))}</strong><span>accepted values</span></div><div class="audit-stat"><strong>{int(data.get('ambiguous_groups_excluded',0))}</strong><span>groups excluded</span></div><div class="audit-stat"><strong>{int(data.get('report_stats',{}).get('word_count',0)):,}</strong><span>source words</span></div></div></div></section></aside>
  </div>
  <footer class="footer"><span>Generated {verified} · Automated assessment, not a certification or investment recommendation.</span><span>Reporting period: {esc(report_year)} · Primary source: <a href="{esc(canonical_source_href)}" target="_blank" rel="noopener">{esc(report_path.name)}</a></span></footer>
</div></body></html>'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return output_path


def build_all(analysis_dir=Path("output/analysis"), output_dir=Path("output/dashboards")):
    analysis_dir, output_dir = Path(analysis_dir), Path(output_dir)
    outputs = []
    for source in sorted(analysis_dir.glob("*.json")):
        if source.name == "summary.json":
            continue
        data = json.loads(source.read_text(encoding="utf-8"))
        destination = output_dir / f"{source.stem}.html"
        render_dashboard(data, destination)
        outputs.append(destination)
    if not outputs:
        raise FileNotFoundError(f"No company analysis JSON files found in {analysis_dir.resolve()}")
    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-dir", type=Path, default=Path("output/analysis"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/dashboards"))
    args = parser.parse_args()
    for path in build_all(args.analysis_dir, args.output_dir):
        print(path.resolve())


if __name__ == "__main__":
    main()
