# ESG methodology — index handoff pack

Revised 2026-09-24 from the supplied handoff compiled 2026-09-16. Methodology version: `index-2026-09-24`.

## Scope and authority

This document specifies the agreed public index adaptation implemented in this repository. The original handoff describes Klimado's interactive product and reports checks against its production/stage databases on 2026-09-16. Those checks have not been independently repeated here. The API factory and live databases are not part of this repository.

The index continues to analyze corporate sustainability reports. Utilities and questionnaires are outside scope and incur no missing-component penalty. The existing report evidence model, including the certification mention bonus, supplies 100% of the index result. This does not mean certificates alone supply 100%.

## Implemented calculation

1. Extract and resolve report evidence using the existing automated gates.
2. Score each of the existing 30 metrics with up to five disclosure and five textual/numeric performance-signal points. Retain existing metric weights.
3. For each pillar, calculate `100 × sum(weighted metric scores) / sum(metric weights)`, rounded to one decimal.
4. Weight the pillar scores: Environmental 0.70, Social 0.20, Governance 0.10.
5. Add one point for each distinct configured certification/standard name detected in the report, capped at 10 points.
6. Round the result to one decimal, cap at 100, then assign the grade.

```text
weighted_subtotal = 0.70 × Environmental + 0.20 × Social + 0.10 × Governance
certification_bonus = min(number_of_distinct_detected_configured_names, 10)
overall_score = min(round(weighted_subtotal + certification_bonus, 1), 100)
```

Environmental supplies 70% of the pillar subtotal before the additive certification bonus. Certification mentions do not establish ownership, validity, third-party status, or industry relevance. Retaining this bonus is an explicit index decision, not equivalence with Klimado's validated-evidence calculation.

| Grade | Rounded score | Dashboard label |
| --- | --- | --- |
| A | >80 to 100 | A |
| B | >70 to 80 | B |
| C | >55 to 70 | C |
| D | >25 to 55 | D |
| F | 0 to 25 | Starter |

The former Strong/Good/Developing/Limited display scale is replaced by these bands. The same boundaries apply to displayed pillar scores. JSON retains F as the machine-readable grade.

## Evidence and missing-data behavior retained

Accepted numeric values remain available as KPIs. `abstained`, `target_only`, and `subcomponent_only` numeric candidates do not become accepted KPIs. Their report text can still contribute to the existing disclosure or narrative scoring rules, including target mentions. Missing metric evidence scores zero under the existing metric denominator; no new Not rated policy is introduced. Extraction confidence is not an ESG performance score.

## Klimado rules deferred for missing inputs

The supplied handoff reports highest-first certificate aggregation with production boost 0.35 (stage 0.20), followed by an 80/20 evidence/materiality blend. The agreed future profile is production's 0.35, with materiality pre-weighted by the corresponding E/S/G weight. These rules are **not active** in this index version: the repository has neither certificate E/S/G values nor authoritative industry-materiality mappings. Applying them to arbitrary report metrics or inventing materiality would change the agreed model.

When those inputs become available, the reference shape per axis is:

```text
boosted_axis = min(100, max(valid_certificate_axis_values)
                   + 0.35 × sum(other_valid_certificate_axis_values))
blended_axis = round(0.80 × boosted_axis + 0.20 × preweighted_materiality_axis)
reference_total = sum(blended_axis × axis_weight) / sum(axis_weights)
```

The denominator is the sum of weights (0.7 + 0.2 + 0.1), not the sum of dimension scores. This is a reference for a later integration, not a second calculation used in current outputs. That integration must define how certificate-derived dimensions and report-derived dimensions combine, industry matching, duplicate evidence, and missing inputs before activation.

## Worked example and changes

H&M: E 62.9, S 21.1, G 33.2; seven detected standard names. Weighted subtotal = 51.57; final score = 58.6, grade C. Previously the equal-weight average plus bonus yielded 46.1, grade F.

Changed: overall pillar weights, exclusive grade thresholds, dashboard grade labels, methodology metadata and explanatory copy. Retained: extraction/resolution, metric scoring, per-metric weights, category calculations, certification detection and bonus, and KPI selection.

## Implementation and maintenance

- `scoring.py`: version, 70/20/10 aggregation, bonus cap and grade boundaries.
- `esg_report_analyzer_v2.ipynb`: report analysis and metric/category calculations.
- `run_esg_reports.py`: JSON generation, including methodology version.
- `dashboard_builder.py`: HTML rendering using the shared grade function.
- `tests/test_scoring.py`: boundary, weight, rounding, cap and worked-example checks.

Rebuild using `run_esg_reports.py --reports-dir reports_covered --keep-reports`. Version future scoring changes and compare both score changes and evidence invariance. This change intentionally alters scores, so byte-identical score equivalence is not an appropriate acceptance criterion. Ownership and review cadence remain organizational decisions.

Read alongside [the revised ClickUp reconciliation](esg-methodology-clickup-source.md). Original supplied attachments remain unchanged.
