# AI Use Log

This file documents where and how AI assistance (Claude) was used during
this technical assessment, per the assessment's disclosure requirement.
Each entry corresponds to a git commit and states what AI helped with,
what I verified independently, and where judgment calls were mine alone.

---

## 2026-08-01 — Fix 01_clean.py: senatorial district reconciliation bug

**Commit:** 501e8c8
**Files:** Pipeline/01_clean.py, Outputs/facilities_clean.csv, Outputs/reconciliation_log.csv

**What AI assisted with:**
- Diagnosed a data-quality bug in the senatorial-district cross-check logic:
  an initial run flagged 1,118/1,346 facilities (83%) as disagreeing with
  the reference table on senatorial district, an implausibly high rate.
  AI helped trace this to a coding bug rather than a real data issue — the
  reference spreadsheet's SENATORIAL DISTRICT column has the same
  merged-cell pattern as the STATE column (populated only on the first LGA
  row of each block), and the cleaning script wasn't forward-filling it.
- Proposed and implemented the forward-fill fix, and re-verified against
  synthetic test data reproducing the merged-cell pattern before applying
  it to the real dataset.
- Helped resolve unrelated environment/debugging issues along the way:
  a Windows PowerShell string-escaping error, a stale/partially-merged
  script version causing a NameError, and a missing output directory
  causing an OSError.

**What I verified independently:**
- Re-ran the fixed script against the real ~1,346-row facility dataset
  and confirmed the senatorial-district disagreement rate dropped to a
  credible 12/1,346 (0.9%).
- Manually inspected the reconciliation log in Excel and confirmed the
  12 remaining disagreements form a coherent, explainable pattern: 8 are
  facilities in LGA100 (Tivsano-North) whose records still reference the
  pre-2021 senatorial district, consistent with the reference table's own
  gazette note about a 2021 boundary transfer for that LGA.
- Manually scanned health_facilities.csv for placeholder/junk rows to
  confirm the "0 junk rows dropped" result was a genuine finding, not a
  missed filter.

**Judgment retained:** the decision that the 12 remaining disagreements
represent a real, reportable data-quality finding (rather than a residual
bug) was made by me after reviewing the underlying facility IDs and
cross-referencing the reference table's remarks column myself.


## 2026-08-01 — Resolve duplicate LGA codes using spatial boundaries as tiebreaker

**Commit:** 3e1ade5
**Files:** Pipeline/01_clean.py, Outputs/facilities_clean.csv, Outputs/reconciliation_log.csv

**What AI assisted with:**
- After the previous fix, 12/1,346 facilities still disagreed with the
  reference table on senatorial district, all traced to 3 LGA codes with
  duplicate/conflicting rows in LGA_SEN_Districts.xlsx. The prior resolution
  rule preferred whichever duplicate row cited a "gazette" transfer notice
  in its Remarks column.
- AI proposed cross-checking this against admin_boundaries.gpkg (the
  spatial boundary polygons) once it was available, and inspecting it
  directly revealed that for LGA100 (Tivsano-North), the gazette-cited row
  ("Tivbetu Central") actually disagreed with both the spatial boundary
  file AND all 8 facilities' self-reported values (all "Tivbetu North").
- AI recommended switching the duplicate-resolution rule: prefer the
  reference-table row whose senatorial_district matches the independent
  spatial boundaries file, falling back to the gazette-citation heuristic
  only when the spatial file can't resolve the tie. Rationale: a citation
  string in a spreadsheet is unverified text, while the spatial boundary
  file and the facility registry are two independent sources that
  corroborate each other.
- Implemented and unit-tested the fix against synthetic data reproducing
  the conflict before applying it to the real dataset.

**What I verified independently:**
- Confirmed via fiona that admin_boundaries.gpkg's lgas layer has 121
  features across 6 states, 18 senatorial districts, and 620 wards, all
  in EPSG:4326 — checked LGA100, LGA023, and LGA032 directly.
- Re-ran the full pipeline against the real dataset and confirmed the
  senatorial-district conflict count dropped to 0/1,346, with all three
  duplicate LGA codes resolved without disturbing the two (LGA023, LGA032)
  that were already correct under the old rule.

**Judgment retained:** the decision to trust the spatial boundary file
over a "cites a gazette" text string as the tiebreaker — rather than the
reverse, or leaving both duplicate rows unresolved — was mine, made after
reviewing the underlying evidence (independent corroboration from two
sources vs. one unverified citation) rather than defaulting to whichever
looked more official.