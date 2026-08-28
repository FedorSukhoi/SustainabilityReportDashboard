# Sustainability Report Analyzer and Dashboard

This project turns corporate sustainability reports into two auditable outputs:

1. a structured JSON analysis containing evidence-resolution decisions, metric scores, category scores, and primary KPI values; and
2. a self-contained HTML dashboard that presents the accepted results and links back to an official source.

The pipeline is deterministic and rule-based. It does not ask a language model to invent or estimate missing ESG values. When numeric evidence is ambiguous, target-only, a subcomponent, or otherwise unsafe to present as current performance, the analyzer excludes it.

## End-to-end process

```mermaid
flowchart LR
    A["PDF or TXT report in reports/"] --> B["Text and page extraction"]
    B --> C["Cleaning and local evidence segmentation"]
    C --> D["Prose and table-row recognition"]
    D --> E["Metric matching, column/year mapping, and unit normalization"]
    E --> F["Automated evidence resolution"]
    F --> G["Metric, category, and overall scoring"]
    G --> H["Report moved to reports_covered/"]
    H --> I["JSON analysis"]
    I --> J["HTML dashboard"]
```

### 1. Report discovery

[`run_esg_reports.py`](run_esg_reports.py) scans `reports/` for `.pdf` and `.txt` files. Each report is analyzed independently by executing the analysis cells in [`esg_report_analyzer_v2.ipynb`](esg_report_analyzer_v2.ipynb) in a fresh namespace.

The report path is passed through `ESG_REPORT_PATH`, so the notebook does not need to be edited for each company.

### 2. PDF or text loading

For a PDF, the analyzer attempts text extraction in this order:

1. `pypdf` in the active Python environment;
2. the system `pdftotext` command; or
3. the bundled document-runtime Python with `pypdf`.

Pages are joined with form-feed characters (`\f`). These boundaries allow evidence rows to retain a page number. A `.txt` export is read directly; page numbers are available only when its page breaks were preserved as form feeds.

### 3. Cleaning and segmentation

The analyzer normalizes line endings, subscript digits, tabs, repeated blank lines, and page breaks. It then builds small evidence segments instead of analyzing whole pages:

- table cells separated by runs of spaces;
- individual non-empty lines; and
- prose sentences between 25 and 350 characters.

[`table_extraction.py`](table_extraction.py) adds a second, structured pass over the preserved page layout. It keeps the horizontal positions of row labels, units, values, and year headings; carries a year heading down to its table rows; handles labels or units wrapped onto the next line; and applies row-level magnitude scales such as `(1,000 tCO2e)` or `million tCO2e`. Each recovered cell becomes a `structured_table_cell` evidence segment with an explicit value, canonical unit, year, year source, and accounting variant.

Exact duplicate segments are removed. This local segmentation is important: it reduces the chance that a number belonging to one table row is attached to a different ESG metric elsewhere on the page.

The report record also stores:

- `word_count`: whitespace-separated words in the cleaned report;
- `sentence_count`: normalized prose sentences; and
- `paragraph_count`: the number of local evidence segments, despite the historical JSON field name.

### 4. Company identification

The analyzer searches the beginning of the report for company-like names with common legal suffixes. If that fails, it normalizes the filename by splitting CamelCase and separators and removing report-type and year suffixes.

Company metadata used by the dashboard—such as headquarters, founding year, workforce, website, sector, and the About narrative—is maintained separately in `PROFILES` inside [`dashboard_builder.py`](dashboard_builder.py). It is not inferred from the numeric ESG analysis.

### 5. ESG evidence matching

The notebook defines 30 metrics across Environmental, Social, and Governance categories. Each metric has:

- keyword aliases;
- expected units;
- a category and weight;
- a numeric or qualitative type; and
- a performance polarity such as `higher_better`, `lower_better`, or `neutral`.

Each evidence segment is compared with the metric keywords using literal and fuzzy matching. The fuzzy threshold is 85. Numeric extraction is allowed only when a literal metric label is present; fuzzy narrative evidence may contribute to disclosure scoring, but it cannot by itself publish a KPI.

### 6. Numeric candidate extraction

For quantitative metrics, the analyzer recognizes canonical units and their spelling variants, including:

- `tCO2e`, `MWh`, `GWh`, `kWh`, `m3`, tonnes, percentages, hours, and rates;
- magnitude suffixes such as thousand, million, `k`, `m`, and `bn`; and
- both number-before-unit and unit-before-number table layouts.

Candidates retain the metric, value, normalized unit, page, source segment, confidence, label distance, year, year source, accounting variant, table provenance, and context flags.

General safeguards include:

- a maximum metric-label distance of 140 characters;
- a competing-label margin of 12 characters;
- rejecting table-header years as measurements;
- distinguishing uppercase `MTCO2e` meaning metric tonnes from `MtCO2e` meaning million tonnes;
- recognizing future years and target language;
- identifying avoided impacts, change amounts, and partial components; and
- refusing to assign one combined value to multiple GHG scopes;
- rejecting values separated from a metric label by a sentence/row boundary;
- ignoring future target/comparison columns when mapping historical table headings;
- treating location-based and market-based Scope 2 rows as distinct variants; and
- excluding combined Scope 1+2 totals from both component metrics.

### 7. Automated value resolution

Candidate values are resolved independently by metric, unit, period, and accounting variant. Target-only and subcomponent-only groups are excluded before ranking. Exact structured-table cells receive a 25-point provenance bonus so a precise table value can beat a rounded prose summary without hard-coding a company or page.

The resolution score is based on:

```text
confidence
- 0.18 × label distance
+ up to 12 points for corroboration on additional pages
- 18 for target context
+ 12 for actual-performance context
- 18 for subcomponent context
+ 8 for the latest detected year
+ 3 for a table-cell or line segment
+ 25 for a structured table cell
```

Two values within 2% are treated as agreeing evidence. Otherwise, the leading candidate needs a resolution-score margin of at least 10 points. If it does not, the whole group is recorded as `abstained` and cannot reach scoring or the dashboard.

Possible decisions in `value_resolution` are:

- `accepted`: safe enough to enter `accepted_values`;
- `abstained`: competing values could not be resolved;
- `target_only`: only a target or future commitment was found; or
- `subcomponent_only`: only a component, avoided impact, or change amount was found.

`ambiguous_groups_excluded` counts only `abstained` decisions. The other rejected decision types remain visible in `value_resolution` but are not included in that counter.

### 8. Metric scoring

Every metric receives up to 10 points: five for disclosure and five for performance.

Disclosure points:

| Flag | Point condition |
| --- | --- |
| Mentioned | At least one matching evidence segment exists. |
| Specific | An accepted numeric value exists, or a qualitative metric names a policy, framework, standard, or certification. |
| YoY | The text contains comparison language or accepted values cover at least two distinct years. |
| Target | Target, goal, objective, commitment, roadmap, or ambition language appears. |
| Progress | Progress or directional achievement language appears. |

Performance points:

| Flag | Points | Condition |
| --- | ---: | --- |
| Net positive | 2 | Polarity-aware positive evidence exceeds negative evidence. |
| Validation | 1 | Verification, assurance, SBTi, or similar third-party language appears. |
| Trend | 1 | Accepted values across two dated periods move in the preferred direction. |
| Clean | 1 | No configured negative or incident language appears. |

The weighted contribution of a metric is:

```text
weighted score = metric total / 10 × metric weight
```

### 9. Category, certification, overall, and grade calculations

Each category score is calculated independently:

```text
category score = 100 × sum(weighted metric scores) / sum(metric weights)
```

Every configured certification or standard whose name occurs in the report adds one overall point, capped at 10. Detection confirms only that the term occurs; it does not validate certificate ownership, scope, issue date, or expiry.

```text
overall score = mean(Environmental, Social, Governance) + certification bonus
```

The result is capped at 100 and rounded to one decimal. Letter grades use `A ≥ 90`, `B ≥ 80`, `C ≥ 70`, `D ≥ 60`, and `F < 60`.

The dashboard uses a separate descriptive scale: `Strong ≥ 65`, `Good ≥ 50`, `Developing ≥ 35`, and `Limited < 35`.

### 10. JSON generation and report archiving

The batch runner writes one file per company to `output/analysis/` and rebuilds `output/analysis/summary.json`.

The company JSON contains:

| Field | Meaning |
| --- | --- |
| `report`, `company`, `report_stats` | Source identity and extraction statistics. |
| `overall_score`, `overall_grade` | Final numeric result and letter grade. |
| `certification_bonus` | Number of detected configured standards, capped at 10. |
| `values_total` | Number of accepted numeric rows. |
| `ambiguous_groups_excluded` | Number of `abstained` resolution groups. |
| `category_scores` | Environmental, Social, and Governance scores. |
| `metric_scores` | Full scoring result for all 30 metrics. |
| `accepted_values` | Accepted numeric rows with their evidence lineage. |
| `value_resolution` | Accepted and rejected group-level decisions. |
| `primary_values` | One dashboard KPI selected per metric from accepted actuals. |
| `certifications` | Detected configured standard names. |
| `source_url`, `source_link_policy` | External dashboard destination and how it was selected. |

After successful analysis, the input report is moved from `reports/` to `reports_covered/`. The saved JSON points to the archived location.

### 11. Official source-link selection

[`source_links.py`](source_links.py) reads visible URLs and PDF link annotations. It keeps first-party company links, favors report/reporting, sustainability, ESG, responsibility, and matching-year URLs, and penalizes policy, supplier, assurance, index, and other auxiliary-document URLs.

If no suitable embedded report URL is available, the dashboard uses the official website configured in the company profile. A local file path is used only when neither option exists.

### 12. Dashboard generation

[`dashboard_builder.py`](dashboard_builder.py) converts each JSON record into a self-contained HTML file in `output/dashboards/`.

JSON-to-dashboard mappings are:

| Dashboard component | Input |
| --- | --- |
| Hero score and sidebar score | `overall_score` |
| ESG status pill | Descriptive scale applied to `overall_score` |
| ESG pillar cards | `category_scores` |
| Key sustainability areas | Six non-zero metrics ranked by weighted score, then total score |
| Evidence cards | First eight `primary_values`, joined back by metric, value, unit, year, and variant for page and resolution metadata |
| Certificates cards | `certifications` |
| Evidence-resolution box | `values_total`, `ambiguous_groups_excluded`, and `report_stats.word_count` |
| Source buttons | `source_url`, with a PDF page fragment when the external source itself is a PDF |
| Company sidebar and About text | `PROFILES` in `dashboard_builder.py` |

Values at or above one million are abbreviated to `m` in the HTML, while the JSON retains the full numeric value.

Evidence cards also expose the accounting basis where relevant, the normalized reporting year, and whether that year came from a table header, an explicit nearby year, or the report-year default used by a headerless table.

## Running the pipeline

Place new reports in `reports/`, then run:

```bash
/Users/mac/miniconda3/envs/pystats/bin/python run_esg_reports.py
```

This analyzes every supported report, writes JSON and HTML outputs, updates the summary, and moves processed reports into `reports_covered/`.

To regenerate existing covered reports without moving them:

```bash
/Users/mac/miniconda3/envs/pystats/bin/python run_esg_reports.py \
  --reports-dir reports_covered \
  --keep-reports
```

The dashboard-only workflow is also available through [`esg_dashboard_generator.ipynb`](esg_dashboard_generator.ipynb) or:

```bash
python3 dashboard_builder.py
```

## Concrete lineage example: H&M Group (current output)

The current covered source is [`HM-Group-Annual-and-sustainability-report-2025.txt`](reports_covered/HM-Group-Annual-and-sustainability-report-2025.txt), a layout-preserving text export. Its outputs are [`hm-group-annual-and-sustainability-report-2025.json`](output/analysis/hm-group-annual-and-sustainability-report-2025.json) and [`hm-group-annual-and-sustainability-report-2025.html`](output/dashboards/hm-group-annual-and-sustainability-report-2025.html).

### Report-level result

| Field | Current result | Derivation |
| --- | ---: | --- |
| Company | H&M Group | Company-name heuristic. |
| Words | 112,437 | Cleaned report text. |
| Sentences | 4,147 | Normalized sentence splitter. |
| Evidence segments | 13,884 | Ordinary local evidence plus structured table cells. |
| Accepted numeric rows | 26 | Every accepted metric/unit/year/variant group, including historical rows. |
| Ambiguous groups excluded | 4 | Three Water Withdrawal periods and one undated Renewable Energy group. |
| Certifications | 7 | ISO 45001, CDP, SBTi, RE100, FSC, PEFC, and Sedex. |
| Category scores | E 62.9 · S 21.1 · G 33.2 | Weighted metric aggregation. |
| Overall | 46.1 / 100 · F | Category mean plus the seven-point certification bonus. |
| Source link | `https://hmgroup.com/` | Official-company-site fallback because the TXT export has no stronger embedded report URL. |

### How the page 41 emissions table becomes dated JSON

The table prints its retrospective headings several lines above the Scope 1 row:

```text
2025          2024          2023          (2019)        ... 2030 2040 ...
Gross Scope 1 GHG emissions (tCO2e) 17,039 17,002 17,050 22,738 0.2 -25.1
```

The structured pass stores the x-position of the four retrospective headings, ignores the future target/comparison columns, and aligns the row values to those headings. It creates four independent accepted cells: 2025 = 17,039; 2024 = 17,002; 2023 = 17,050; and 2019 = 22,738 tCO2e. Every cell has `Source: structured_table_cell`, `Year Source: table_header`, `Variant: default`, `Table Context: true`, and page 41.

The same logic separates the two Scope 2 rows rather than forcing them to compete:

| Variant | 2019 | 2023 | 2024 | 2025 | Dashboard selection |
| --- | ---: | ---: | ---: | ---: | --- |
| Location-based | 658,763 | 378,730 | 372,984 | 337,786 | Retained in `accepted_values`. |
| Market-based | 48,735 | 40,554 | 28,492 | 25,131 | 25,131 tCO2e for 2025 is the primary KPI. |

The market-based row is preferred only when choosing one Scope 2 dashboard KPI. Both accounting bases and all mapped historical periods remain in JSON for audit and trend logic.

### All accepted H&M numeric rows

| Metric / variant | Accepted periods and values | Provenance |
| --- | --- | --- |
| Scope 1 Emissions / default | 2019 22,738; 2023 17,050; 2024 17,002; 2025 17,039 tCO2e | Structured table cells, plus one undated duplicate from the legacy unit-before-value pass. |
| Scope 2 / market-based | 2019 48,735; 2023 40,554; 2024 28,492; 2025 25,131 tCO2e | Structured table cells. |
| Scope 2 / location-based | 2019 658,763; 2023 378,730; 2024 372,984; 2025 337,786 tCO2e | Structured table cells, plus one undated duplicate from the legacy pass. |
| Energy Consumption / default | 2019 1,821,661; 2023 1,219,302; 2024 1,173,864; 2025 1,146,868 MWh | Structured table cells, plus one undated duplicate from the legacy pass. |
| Renewable Energy / default | 2019 96%; 2023 94%; 2024 96%; 2025 95% | Structured table cells. |
| Scope 3 Emissions / default | 2024 1,269,000 tCO2e | Direct prose extraction; the closest explicit year is 2024. |
| Employee Turnover / default | Undated 59.2% | Legacy unit-before-value extraction. |
| Gender Diversity / default | Undated 50% | Direct extraction. The evidence is female board membership, so this remains a documented taxonomy limitation. |

There are 26 accepted rows in total. Historical and alternate-basis rows are intentionally not collapsed into the seven `primary_values`; they support trend scoring and auditability. The dashboard primaries are Scope 1 17,039 tCO2e (2025), market-based Scope 2 25,131 tCO2e (2025), Scope 3 1.269m tCO2e (2024), Energy Consumption 1.147m MWh (2025), Renewable Energy 95% (2025), Employee Turnover 59.2%, and Gender Diversity 50%.

### Rejected H&M groups

| Metric / period | Decision | Reason |
| --- | --- | --- |
| Water Withdrawal / 2022 | `abstained` | Two different complete-looking table candidates tied. |
| Water Withdrawal / 2024 | `abstained` | Two different complete-looking table candidates tied. |
| Water Withdrawal / 2025 | `abstained` | Two different complete-looking table candidates tied. |
| Renewable Energy / unknown | `abstained` | Three values differed and the leading margin was 3.0, below 10. |
| Waste Generated / 2024 | `target_only` | The candidate was classified as a target rather than current performance. |

The four abstentions produce `ambiguous_groups_excluded: 4`; `target_only` is separately auditable but does not increment that counter.

### Complete H&M metric scoring

| Category | Metric | Disclosure | Performance | Total | Weight | Weighted |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Environmental | Scope 1 Emissions | 5 | 4 | 9 | 10 | 9.0 |
| Environmental | Scope 2 Emissions | 5 | 3 | 8 | 10 | 8.0 |
| Environmental | Scope 3 Emissions | 5 | 3 | 8 | 10 | 8.0 |
| Environmental | Total GHG Emissions | 4 | 3 | 7 | 8 | 5.6 |
| Environmental | Carbon Intensity | 1 | 1 | 2 | 8 | 1.6 |
| Environmental | Energy Consumption | 5 | 4 | 9 | 7 | 6.3 |
| Environmental | Renewable Energy | 4 | 3 | 7 | 8 | 5.6 |
| Environmental | Water Withdrawal | 3 | 2 | 5 | 7 | 3.5 |
| Environmental | Waste Generated | 1 | 0 | 1 | 6 | 0.6 |
| Environmental | Waste Recycled | 2 | 2 | 4 | 6 | 2.4 |
| Environmental | Circular Economy | 3 | 1 | 4 | 5 | 2.0 |
| Environmental | Biodiversity | 4 | 4 | 8 | 5 | 4.0 |
| Social | Employee Turnover | 2 | 0 | 2 | 7 | 1.4 |
| Social | Training Hours | 1 | 0 | 1 | 6 | 0.6 |
| Social | Gender Diversity | 2 | 0 | 2 | 8 | 1.6 |
| Social | Women in Leadership | 1 | 1 | 2 | 8 | 1.6 |
| Social | Employee Engagement | 4 | 3 | 7 | 6 | 4.2 |
| Social | LTIFR | 0 | 0 | 0 | 9 | 0.0 |
| Social | TRIR | 0 | 0 | 0 | 9 | 0.0 |
| Social | Human Rights | 5 | 1 | 6 | 8 | 4.8 |
| Social | Supplier Audits | 0 | 0 | 0 | 6 | 0.0 |
| Social | Pay Gap | 1 | 1 | 2 | 8 | 1.6 |
| Governance | Independent Directors | 1 | 1 | 2 | 8 | 1.6 |
| Governance | Board Diversity | 1 | 1 | 2 | 8 | 1.6 |
| Governance | Executive Compensation | 1 | 1 | 2 | 6 | 1.2 |
| Governance | Anti-Corruption | 3 | 1 | 4 | 9 | 3.6 |
| Governance | Whistleblower Policy | 2 | 1 | 3 | 6 | 1.8 |
| Governance | Cybersecurity | 4 | 3 | 7 | 8 | 5.6 |
| Governance | Data Privacy | 3 | 0 | 3 | 8 | 2.4 |
| Governance | Ethics | 3 | 0 | 3 | 7 | 2.1 |

The weighted Environmental rows sum to 56.6 across 90 weight points, producing 62.9. Social remains 21.1 and Governance 33.2. Their mean is 39.0667; adding the seven-point certification bonus gives the final 46.1 score. The dashboard therefore shows `Developing`, while the letter-grade scale gives `F`.

## Interpretation limits

- The system scores disclosure evidence and rule-based textual performance signals; it is not an external ESG rating, certification, investment recommendation, or legal assurance opinion.
- Keyword presence can over-classify a metric, as shown by H&M’s board-membership figure being attached to Gender Diversity.
- Flattened PDF tables can preserve values while losing a reliable year-to-column mapping.
- Detection of a certification name is not proof of a valid certificate.
- A missing numeric KPI means the evidence did not pass the automated resolution gate, not necessarily that the company did not disclose the topic.
- Confidence measures extraction quality, not whether the reported result is environmentally or socially strong.
