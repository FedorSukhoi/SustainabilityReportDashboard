#!/usr/bin/env python3
"""Batch-execute the analyzer portion of the ESG notebook for every report."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
from pathlib import Path

from dashboard_builder import get_profile, render_dashboard
from source_links import choose_source_url


SUPPORTED_REPORT_SUFFIXES = {".txt", ".pdf"}
ANALYZER_LAST_CELL = 22


def _records(namespace, name):
    frame = namespace.get(name)
    return [] if frame is None else json.loads(frame.to_json(orient="records"))


def analyze(notebook_path: Path, report_path: Path):
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    previous_report = os.environ.get("ESG_REPORT_PATH")
    previous_child = os.environ.get("ESG_BATCH_CHILD")
    os.environ["ESG_REPORT_PATH"] = str(report_path.resolve())
    os.environ["ESG_BATCH_CHILD"] = "1"
    namespace = {"__name__": "__main__"}
    captured = io.StringIO()

    try:
        with contextlib.redirect_stdout(captured):
            for index, cell in enumerate(notebook["cells"]):
                if index > ANALYZER_LAST_CELL:
                    break
                if cell.get("cell_type") != "code":
                    continue
                source = "".join(cell.get("source", []))
                exec(
                    compile(source, f"{notebook_path.name}:cell-{index}", "exec"),
                    namespace,
                )
    finally:
        if previous_report is None:
            os.environ.pop("ESG_REPORT_PATH", None)
        else:
            os.environ["ESG_REPORT_PATH"] = previous_report
        if previous_child is None:
            os.environ.pop("ESG_BATCH_CHILD", None)
        else:
            os.environ["ESG_BATCH_CHILD"] = previous_child

    results = namespace["ESG_RESULTS"]
    return {
        "report": str(report_path.resolve()),
        "company": namespace["REPORT"]["company"],
        "report_stats": {
            key: namespace["REPORT"][key]
            for key in ("word_count", "sentence_count", "paragraph_count")
        },
        "methodology_version": results["methodology_version"],
        "overall_score": results["overall_score"],
        "overall_grade": results["overall_grade"],
        "certification_bonus": results["certification_bonus"],
        "values_total": results["values_total"],
        "values_needing_review": results["values_needing_review"],
        "ambiguous_groups_excluded": results.get("ambiguous_groups_excluded", 0),
        "category_scores": _records(namespace, "CATEGORY_SCORE_DF"),
        "metric_scores": _records(namespace, "METRIC_SCORE_DF"),
        "primary_values": _records(namespace, "PRIMARY_VALUES_DF"),
        "accepted_values": _records(namespace, "VALUES_DF"),
        "value_resolution": _records(namespace, "VALUE_RESOLUTION_DF"),
        "certifications": _records(namespace, "CERTIFICATIONS_DF"),
    }


def safe_stem(path: Path):
    return re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument(
        "--notebook", type=Path, default=Path("esg_report_analyzer_v2.ipynb")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output/analysis"))
    parser.add_argument(
        "--dashboard-output-dir", type=Path, default=Path("output/dashboards")
    )
    parser.add_argument(
        "--archive-dir", type=Path, default=Path("reports_covered"),
        help="Move successfully analyzed reports here before dashboard generation.",
    )
    parser.add_argument(
        "--keep-reports", action="store_true",
        help="Leave source reports in place (used when refreshing reports_covered).",
    )
    args = parser.parse_args()

    reports = sorted(
        path
        for path in args.reports_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_REPORT_SUFFIXES
    )
    if not reports:
        raise FileNotFoundError(
            f"No .txt or .pdf reports found in {args.reports_dir.resolve()}"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for report in reports:
        print(f"Analyzing {report.name} ...")
        result = analyze(args.notebook, report)
        profile = get_profile(result["company"])
        source_url, link_policy = choose_source_url(
            report, result["company"], profile.get("website")
        )
        result["source_url"] = source_url
        result["source_link_policy"] = link_policy

        final_report = report
        if not args.keep_reports:
            args.archive_dir.mkdir(parents=True, exist_ok=True)
            final_report = args.archive_dir / report.name
            if final_report.exists() and final_report.resolve() != report.resolve():
                raise FileExistsError(f"Archive destination already exists: {final_report}")
            if final_report.resolve() != report.resolve():
                report.replace(final_report)
        result["report"] = str(final_report.resolve())

        destination = args.output_dir / f"{safe_stem(report)}.json"
        destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
        dashboard = args.dashboard_output_dir / f"{safe_stem(report)}.html"
        render_dashboard(result, dashboard)
        print(f"  Source link: {source_url or 'local report fallback'} ({link_policy})")
        print(f"  Dashboard: {dashboard.resolve()}")

    summary = []
    for destination in sorted(args.output_dir.glob("*.json")):
        if destination.name == "summary.json":
            continue
        result = json.loads(destination.read_text(encoding="utf-8"))
        summary.append({
            "company": result["company"],
            "report": Path(result["report"]).name,
            "score": result["overall_score"],
            "grade": result["overall_grade"],
            "accepted_values": result["values_total"],
            "ambiguous_groups_excluded": result["ambiguous_groups_excluded"],
            "source_url": result.get("source_url"),
            "output": str(destination),
        })
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Processed {len(reports)} reports; summary now covers {len(summary)} companies: {summary_path.resolve()}")


if __name__ == "__main__":
    main()
