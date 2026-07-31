# Part 2, Question 4: Coverage Survey Analysis Under a Complex Sampling Design

All data in this pack is synthetic. No real survey respondent, household, or interviewer is
represented here.

## Context

A post campaign coverage survey was conducted across three states in May 2026 using a
stratified two stage cluster design.

- Stratum: state. Three strata.
- Stage one: enumeration areas selected within each stratum with probability proportional to
  the number of households recorded in the 2023 census listing. Thirty clusters per stratum,
  selected by systematic probability proportional to size.
- Stage two: twenty households selected by simple random sample from a fresh field listing of
  the selected enumeration area.
- All resident children aged 9 to 59 completed months in a selected household were enumerated.

## Files

**`sampling_frame.csv`**  (920 rows)  
The complete frame of enumeration areas, including those not selected. Stage one selection probabilities are given for selected clusters.

| Column | Type | Example |
|---|---|---|
| `ea_code` | str | EA00001 |
| `stratum_code` | str | ST01 |
| `stratum_name` | str | Bansara State |
| `lga_name` | str | Yobrima |
| `ward_name` | str | Enwwadu |
| `settlement_type` | str | Rural |
| `households_census_2023` | int64 | 33 |
| `cluster_id` | str | C002 |
| `selected` | int64 | 0 |
| `stage1_selection_probability` | float64 | 0.18289157 |
| `stratum_total_households` | float64 | 41500.0 |
| `clusters_selected_in_stratum` | float64 | 30.0 |
| `households_listed_fieldwork` | float64 | 287.0 |
| `field_status` | str | Visited as selected |

**`household_records.csv`**  (1,820 rows)  
One row per selected household, including households where no interview was completed.

| Column | Type | Example |
|---|---|---|
| `household_id` | str | H00485 |
| `cluster_id` | str | C025 |
| `stratum_code` | str | ST01 |
| `interviewer_id` | str | I07 |
| `interview_date` | str | 2026-05-15 |
| `interview_duration_min` | int64 | 5 |
| `result_of_visit` | str | Completed |
| `eligible_children_9_59_months` | float64 | 2.0 |
| `wealth_quintile` | float64 | 1.0 |
| `settlement_type` | str | Rural |
| `stage2_households_listed` | int64 | 95 |
| `stage2_households_selected` | int64 | 20 |

**`child_records.csv`**  (2,316 rows)  
One row per enumerated child in a completed household.

| Column | Type | Example |
|---|---|---|
| `child_id` | str | K00281 |
| `household_id` | str | H00220 |
| `cluster_id` | str | C011 |
| `stratum_code` | str | ST01 |
| `age_months` | int64 | 28 |
| `sex` | str | Female |
| `vaccination_card_seen` | str | No |
| `dose_recorded_on_card` | str | Yes |
| `dose_reported_by_caregiver` | str | Yes |

**`fieldwork_log.csv`**  (90 rows)  
Interviewer level daily fieldwork record, including supervisor spot checks.

| Column | Type | Example |
|---|---|---|
| `interviewer_id` | str | I01 |
| `team` | str | TM1 |
| `fieldwork_date` | str | 2026-05-11 |
| `clusters_worked` | int64 | 1 |
| `households_attempted` | int64 | 20 |
| `households_completed` | int64 | 15 |
| `mean_interview_duration_min` | float64 | 21.6 |
| `supervisor_spot_check` | str | Yes |
| `gps_verified` | str | No |

**`survey_instrument.md`**

An extract of the household instrument, including the interviewer instructions that govern
the skip pattern between card confirmed and caregiver reported vaccination status.

## Notes

- `households_listed_fieldwork` in the frame is the count from the field listing.
  `households_census_2023` is the measure of size used for stage one selection.
  They are not the same number and the difference matters.
- Households that were not interviewed are present in the data with the result of visit
  recorded. They are not an error and must not be dropped without a stated adjustment.
- Where a vaccination card was seen, caregiver recall was not recorded. This is by design.
  See the interviewer instructions.
