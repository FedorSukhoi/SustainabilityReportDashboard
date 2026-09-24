# ESG methodology — ClickUp source reconciliation

Revised 2026-09-24. The original ClickUp export is historical and superseded. This revision reconciles it with the **agreed index adaptation**, specified in [the index handoff pack](esg-methodology-handoff-pack.md). It is not a verbatim export or a claim to reproduce Klimado production.

## Current index decisions

| Topic | Historical source or handoff | Implemented index decision |
| --- | --- | --- |
| Inputs | Klimado certificates, utilities, questionnaire | Retain report-derived disclosure/performance signals plus certification-name bonus |
| Components | Conflicting 70/20/10 and 40/20/40 drafts; handoff reports 60/30/10 | Utilities/questionnaire excluded; current report evidence model supplies the entire score |
| E/S/G weighting | 70/20/10 in both supplied sources | Adopt 70/20/10 instead of the project's equal thirds |
| Metric scoring | Handoff describes dimension-level certificate inputs | Retain 30 metrics, existing metric weights and 0–10 scores |
| Certification contribution | Validated, active, industry-matched evidence in handoff | Retain +1 per distinct configured name detected, cap 10; mentions are unvalidated |
| Certificate aggregation | ClickUp average; handoff highest-first plus boost | Defer boost 0.35 pending certificate E/S/G data; do not boost report metrics |
| Materiality | ClickUp multiplication; handoff 80/20 blend with pre-weighting | Defer pending industry mappings; do not fabricate defaults |
| Grades | Several conflicting legacy tables | A >80, B >70, C >55, D >25, F ≤25 |
| Display scale | Project Strong/Good/Developing/Limited | Same letter bands as JSON; display F as Starter |
| Numeric uncertainty | No clear ClickUp semantics | Retain accepted/abstained/target_only/subcomponent_only decisions |
| Output | Product score records vs existing HTML and JSON | Retain HTML and JSON; add methodology version to company JSON |

## Formula and example

```text
score = min(100, round(0.70 × E + 0.20 × S + 0.10 × G
                       + min(detected_standard_count, 10), 1))
```

E, S and G are the existing one-decimal report-derived category scores. This preserves the distinction between pillar weighting and the separate additive bonus. Grade the rounded final score. Utilities and questionnaires have no contribution, denominator or penalty.

H&M: `0.70 × 62.9 + 0.20 × 21.1 + 0.10 × 33.2 + 7 = 58.57`, rounded to **58.6 / C**. The old ClickUp examples involving utilities, questionnaires, averaged certificates or multiplicative materiality are not current index examples.

## Corrections to the supplied annotation

- A score of 78 is **B**, not A; 60 is **C**, not B under the handoff thresholds.
- The reference weighted-average denominator must say **sum of axis weights**, not ambiguously E+S+G.
- “Implementation wins” in the original export referred to Klimado's API and live databases. This repository is a distinct report-analysis implementation with an explicitly agreed adaptation.
- The handoff reports production boost 0.35 and stage 0.20 as of 2026-09-16. Selecting 0.35 for future integration does not make that rule executable with the present data.

## Design rationale and limits

Retain the original intent of traceable evidence, reproducibility and industry relevance. Current scores measure report disclosure and rule-based performance signals; the additive name-mention bonus remains a known limitation. Neither detected certifications nor extracted report values become independently verified merely by being scored.

The source's regulatory references are historical context. This revision makes no claim that ESRS or EU regulation mandates 70/20/10 weights, or that the index establishes regulatory compliance. Here, these are explicitly selected methodology coefficients.

## Historical provenance

The supplied export combines a Main version, Condensed version, contradictory Constants section, March/April 2025 meeting notes and a stale API-factory appendix. Its historical component weights, utility sectors, questionnaire counts and worked examples are excluded from the operational index specification. The original attachment remains available unchanged for archival comparison; use the linked handoff and this repository's code for current index rules.
