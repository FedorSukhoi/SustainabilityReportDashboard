"""Recover year-aligned ESG values from flattened PDF/TXT table text.

The main analyzer deliberately works with small text segments. This module adds
structured segments for table rows so values inherit the correct year, unit,
and accounting basis before ordinary metric extraction and scoring run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


YEAR_RE = re.compile(r"\b(20[0-3]\d)\b")
NUMBER_RE = re.compile(
    r"(?<![\w.])([+\-−–]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|"
    r"[+\-−–]?\d+(?:\.\d+)?)(?![\w.])"
)
PRIVATE_CO2_RE = re.compile(r"CO[\ue000-\uf8ff]e", re.I)
SPLIT_THOUSANDS_RE = re.compile(r"(?<=\d)\s*,\s*(?=\d{3}\b)")


@dataclass(frozen=True)
class UnitInfo:
    canonical: str
    scale: float
    start: int
    end: int


UNIT_PATTERNS = [
    ("kgCO2e", re.compile(r"\bkg\s*CO2e\b", re.I)),
    ("tCO2e", re.compile(r"(?:(1,000|thousand|million|bn|[kKmM])\s*)?(?:metric\s+)?(?:t(?:onnes?)?\s*)?CO2e", re.I)),
    ("tonnes", re.compile(r"(?:(1,000|thousand|million|bn|[kKmM])\s*)?(?:metric\s+)?tonnes?\b", re.I)),
    ("MWh", re.compile(r"\bMWh\b", re.I)),
    ("GWh", re.compile(r"\bGWh\b", re.I)),
    ("kWh", re.compile(r"\bkWh\b", re.I)),
    ("m3", re.compile(r"\b(?:m3|m\^3|cubic\s+met(?:re|er)s?)\b", re.I)),
    ("hours", re.compile(r"\b(?:hours?|hrs?)\b", re.I)),
    ("%", re.compile(r"%")),
]


def _normalize_line(line: str) -> str:
    line = PRIVATE_CO2_RE.sub("CO2e", line)
    line = line.replace("CO₂e", "CO2e").replace("CO₂", "CO2")
    line = line.replace("−", "-").replace("–", "-")
    return SPLIT_THOUSANDS_RE.sub(",", line)


def _magnitude_scale(raw: str | None, matched_text: str) -> float:
    if not raw:
        return 1.0
    # Uppercase MTCO2e is a common US spelling for metric tonnes. Lowercase
    # MtCO2e is megatonnes. Case is therefore meaningful here.
    if raw == "M" and re.search(r"MTCO2e", matched_text):
        return 1.0
    return {
        "1,000": 1e3,
        "thousand": 1e3,
        "k": 1e3,
        "m": 1e6,
        "million": 1e6,
        "bn": 1e9,
    }.get(raw.lower(), 1.0)


def _unit_info(text: str) -> UnitInfo | None:
    normalized = _normalize_line(text)
    matches = []
    for canonical, pattern in UNIT_PATTERNS:
        for match in pattern.finditer(normalized):
            magnitude = match.group(1) if match.lastindex else None
            matches.append(UnitInfo(
                canonical=canonical,
                scale=_magnitude_scale(magnitude, match.group(0)),
                start=match.start(),
                end=match.end(),
            ))
    return min(matches, key=lambda item: item.start) if matches else None


def _year_header(line: str, report_year: int | None, offset: int = 0) -> list[tuple[int, int]]:
    """Return the most table-like horizontal cluster of year columns."""
    matches = [(int(m.group(1)), offset + m.start()) for m in YEAR_RE.finditer(line)]
    if len(matches) < 2:
        return []
    numeric_tokens = NUMBER_RE.findall(_normalize_line(line))
    clusters: list[list[tuple[int, int]]] = []
    for item in matches:
        if not clusters or item[1] - clusters[-1][-1][1] > 35:
            clusters.append([item])
        else:
            clusters[-1].append(item)
    cluster = max(clusters, key=lambda values: (len(values), values[0][1]))
    if len(cluster) < 2:
        return []
    # Future target columns must not be aligned to current/retrospective data.
    if report_year:
        cluster = [item for item in cluster if item[0] <= report_year]
    seen = set()
    output = []
    for year, position in cluster:
        if year not in seen:
            seen.add(year)
            output.append((year, position))
    if len(output) >= 3:
        return output
    # Two-year headers are valid only when they are genuinely header-like,
    # rather than two dates mentioned in narrative text or a mixed target row.
    if not cluster:
        return []
    local_text = line[max(0, cluster[0][1] - offset - 4):cluster[-1][1] - offset + 8]
    local_numeric_tokens = NUMBER_RE.findall(_normalize_line(local_text))
    alpha_words = re.findall(r"[A-Za-z]{2,}", line)
    if len(output) == 2 and len(local_numeric_tokens) == 2 and len(alpha_words) <= 4:
        return output
    return []


def _keyword_spans(text: str, metric_keywords: dict[str, Iterable[str]]) -> list[tuple[int, int, str]]:
    low = text.lower()
    found = []
    for metric, keywords in metric_keywords.items():
        for keyword in keywords:
            keyword_low = keyword.lower()
            if metric == "Total GHG Emissions" and not (
                "total" in keyword_low or "footprint" in keyword_low
            ):
                continue
            start = 0
            while True:
                position = low.find(keyword_low, start)
                if position < 0:
                    break
                found.append((position, position + len(keyword_low), metric))
                start = position + max(1, len(keyword_low))
    return found


def _variant(text: str) -> str:
    low = text.lower().replace("–", "-").replace("−", "-")
    if re.search(r"(?:combined\s+|total\s+)?scope\s*1\s*(?:&|and|\+)\s*(?:market[- ]based\s*)?(?:scope\s*)?2", low):
        return "combined-scope-1-2"
    if re.search(r"market[- ]based", low):
        return "market-based"
    if re.search(r"location[- ]based", low):
        return "location-based"
    return "default"


def is_combined_scope_aggregate(text: str, value_start: int, metric_name: str) -> bool:
    """True when a value is attached to a Scope 1+2 aggregate, not either component."""
    if metric_name not in {"Scope 1 Emissions", "Scope 2 Emissions"}:
        return False
    low = _normalize_line(text).lower()
    combined = list(re.finditer(
        r"(?:combined\s+|total\s+)?scope\s*1\s*(?:&|and|\+)\s*(?:market[- ]based\s*)?(?:scope\s*)?2",
        low,
    ))
    if not combined:
        return False
    individual_pattern = r"scope\s*1(?!\s*(?:&|and|\+))" if metric_name.startswith("Scope 1") else r"scope\s*2"
    individual = list(re.finditer(individual_pattern, low))
    combined_distance = min(abs(value_start - match.end()) for match in combined)
    individual_distance = min(
        (abs(value_start - match.end()) for match in individual
         if not any(parent.start() <= match.start() < parent.end() for parent in combined)),
        default=10**6,
    )
    return combined_distance <= individual_distance


def _numeric_tokens(line: str, data_start: int = 0, offset: int = 0) -> list[tuple[float, int, str]]:
    normalized = _normalize_line(line)
    values = []
    for match in NUMBER_RE.finditer(normalized):
        if match.start() < data_start:
            continue
        prefix = normalized[max(0, match.start() - 8):match.start()].lower()
        if re.search(r"scope\s*$", prefix):
            continue
        raw = match.group(1).replace(",", "").replace("−", "-").replace("–", "-")
        values.append((float(raw), offset + match.start(), match.group(1)))
    return values


def _map_years(
    values: list[tuple[float, int, str]],
    headers: list[tuple[int, int]],
    report_year: int | None,
) -> list[tuple[float, int, str, int, str]]:
    if headers and len(values) == len(headers):
        return [(*value, year, "table_header") for value, (year, _) in zip(values, headers)]
    if headers and len(values) > len(headers):
        remaining = list(values)
        mapped = []
        for year, header_position in headers:
            if not remaining:
                break
            nearest = min(remaining, key=lambda item: abs(item[1] - header_position))
            if abs(nearest[1] - header_position) <= 12:
                mapped.append((*nearest, year, "table_header"))
                remaining.remove(nearest)
        if len(mapped) >= 1:
            return mapped
    if len(values) == 1 and report_year:
        return [(*values[0], report_year, "report_year_default")]
    return []


def _table_header_unit(line: str) -> UnitInfo | None:
    unit = _unit_info(line)
    if not unit:
        return None
    low = line.lower()
    header_words = ("category", "group", "activity type", "base year", "target year", "retrospective")
    return unit if any(word in low for word in header_words) else None


def _chunks(line: str) -> list[tuple[str, int]]:
    """Split flattened multi-column pages while retaining x-like offsets."""
    chunks = []
    start = 0
    for match in re.finditer(r"\s{3,}", line):
        part = line[start:match.start()]
        if part.strip():
            left = len(part) - len(part.lstrip())
            chunks.append((part.strip(), start + left))
        start = match.end()
    part = line[start:]
    if part.strip():
        left = len(part) - len(part.lstrip())
        chunks.append((part.strip(), start + left))
    return chunks


def _data_start_after_unit(text: str, unit_end: int) -> int:
    """Skip closing punctuation and a following '(sum of ...)' row note."""
    position = unit_end
    while position < len(text) and (text[position].isspace() or text[position] == ")"):
        position += 1
    if position < len(text) and text[position] == "(":
        close = text.find(")", position + 1)
        if close >= 0:
            position = close + 1
    return position


def build_table_segments(
    text: str,
    report_year: int | None,
    metric_keywords: dict[str, Iterable[str]],
    metric_units: dict[str, Iterable[str]] | None = None,
) -> list[dict]:
    """Build one normalized evidence segment per table value/year cell."""
    output = []
    for page_number, page in enumerate(text.split("\f"), start=1):
        lines = [_normalize_line(line.rstrip()) for line in page.splitlines()]
        active_years: list[tuple[int, int]] = []
        active_unit: UnitInfo | None = None
        year_header_age = 10**6
        unit_header_age = 10**6

        for index, line in enumerate(lines):
            line_chunks = _chunks(line)
            detected_years = _year_header(line, report_year)
            detected_unit = None
            for chunk, offset in line_chunks:
                years = _year_header(chunk, report_year, offset)
                if len(years) > len(detected_years):
                    detected_years = years
                header_unit = _table_header_unit(chunk)
                if header_unit:
                    detected_unit = header_unit
            if detected_years:
                active_years = detected_years
                year_header_age = 0
            else:
                year_header_age += 1
            if detected_unit:
                active_unit = detected_unit
                unit_header_age = 0
            else:
                unit_header_age += 1
            if year_header_age > 90:
                active_years = []
            if unit_header_age > 12:
                active_unit = None

            # A year-heading line establishes column positions; its year tokens
            # are never measurements from a metric row on that same line.
            if detected_years:
                continue

            if not line.strip() or (not active_years and not active_unit):
                continue

            for base_chunk, base_offset in line_chunks:
                spans = _keyword_spans(base_chunk, metric_keywords)
                if not spans:
                    continue

                base_chunk_index = line_chunks.index((base_chunk, base_offset))
                same_line_candidates = []
                for item in line_chunks[base_chunk_index:]:
                    if item != (base_chunk, base_offset) and _keyword_spans(item[0], metric_keywords):
                        break
                    same_line_candidates.append(item)
                if active_years:
                    right_limit = max(position for _, position in active_years) + 24
                    same_line = [
                        item for item in same_line_candidates
                        if item[1] <= right_limit
                    ]
                else:
                    same_line = same_line_candidates
                row_chunks = same_line or [(base_chunk, base_offset)]
                joined = " ".join(chunk for chunk, _ in row_chunks)
                # Wrapped PDF rows frequently place the unit and all values on
                # the following line. Prefer a horizontally aligned chunk.
                for lookahead in (1, 2):
                    unit = _unit_info(joined) or active_unit
                    enough_values = any(_numeric_tokens(chunk) for chunk, _ in row_chunks)
                    if unit and enough_values:
                        break
                    if index + lookahead >= len(lines):
                        break
                    next_chunks = _chunks(lines[index + lookahead])
                    if not next_chunks:
                        continue
                    continuation = min(next_chunks, key=lambda item: abs(item[1] - base_offset))
                    if active_years and abs(continuation[1] - base_offset) > 80:
                        continue
                    continuation_index = next_chunks.index(continuation)
                    if active_years:
                        right_limit = max(position for _, position in active_years) + 24
                        row_chunks.extend(
                            item for item in next_chunks[continuation_index:]
                            if item[1] <= right_limit
                        )
                    else:
                        row_chunks.extend(next_chunks[continuation_index:])
                    joined = " ".join(chunk for chunk, _ in row_chunks)
                    spans = _keyword_spans(joined, metric_keywords)

                row_unit = _unit_info(joined) or active_unit
                if not row_unit:
                    continue
                matched_metrics = sorted({metric for _, _, metric in spans})
                if metric_units is not None:
                    matched_metrics = [
                        metric for metric in matched_metrics
                        if row_unit.canonical in set(metric_units.get(metric, []))
                    ]
                if not matched_metrics:
                    continue

                best_values: list[tuple[float, int, str]] = []
                for physical_chunk, offset in row_chunks:
                    physical_unit = _unit_info(physical_chunk)
                    start = _data_start_after_unit(physical_chunk, physical_unit.end) if physical_unit else 0
                    best_values.extend(_numeric_tokens(physical_chunk, start, offset))
                if active_years and len(best_values) == len(active_years) + 1:
                    # A superscript/footnote number immediately after the unit.
                    numbered_row = bool(re.match(r"\s*\d{1,2}\.\s", base_chunk))
                    if numbered_row or abs(best_values[0][0]) <= 9 or (
                        row_unit.scale != 1 and best_values[0][2].replace(",", "") == "1000"
                    ):
                        best_values = best_values[1:]
                if not best_values:
                    continue

                # A single value may inherit the report year only from an
                # explicit table-level unit header. Prose with its own unit is
                # left to the ordinary evidence extractor.
                own_unit = _unit_info(joined)
                if not active_years and (len(best_values) != 1 or own_unit):
                    continue
                mapped = _map_years(best_values, active_years, report_year)
                if not mapped or (active_years and len(mapped) < 2):
                    continue

                row_variant = _variant(joined)
                if row_variant == "combined-scope-1-2":
                    continue
                if not any(metric in {"Scope 2 Emissions", "Total GHG Emissions"} for metric in matched_metrics):
                    row_variant = "default"
                label_parts = []
                for physical_chunk, _ in row_chunks:
                    unit = _unit_info(physical_chunk)
                    if _keyword_spans(physical_chunk, metric_keywords):
                        if unit:
                            label_parts.append(physical_chunk[:unit.end])
                        else:
                            candidates = _numeric_tokens(physical_chunk)
                            cut = candidates[0][1] if candidates else len(physical_chunk)
                            label_parts.append(physical_chunk[:cut].rstrip())
                    elif unit:
                        label_parts.append(physical_chunk[:unit.end])
                label = " ".join(label_parts) or joined
                label = re.sub(r"\s+", " ", label).strip(" |")

                for raw_value, _, _, year, year_source in mapped:
                    scaled_value = raw_value * row_unit.scale
                    value_text = f"{scaled_value:.12g}"
                    reconstructed = f"{label} {value_text} {row_unit.canonical} in {year}."
                    output.append({
                        "page": page_number,
                        "kind": "structured_table_cell",
                        "text": reconstructed,
                        "table_year": str(year),
                        "year_source": year_source,
                        "variant": row_variant,
                        "table_value": scaled_value,
                        "table_unit": row_unit.canonical,
                        "table_label": label,
                        "matched_metrics": matched_metrics,
                    })

    # Deduplicate cells produced by overlapping/wrapped line passes.
    unique = {}
    for item in output:
        key = (
            item["page"], tuple(item["matched_metrics"]), item["table_value"],
            item["table_unit"], item["table_year"], item["variant"],
        )
        unique.setdefault(key, item)
    return list(unique.values())
