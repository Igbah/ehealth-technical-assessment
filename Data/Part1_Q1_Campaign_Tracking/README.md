# Part 1, Question 1: Campaign Team Tracking and Coverage Reconciliation

All data in this pack is synthetic. It does not describe any real settlement, team, or campaign.
Names, coordinates, and case data were generated for assessment purposes only.

## Context

Bansara State ran a five day house to house Supplementary Immunization Activity from
9 to 13 March 2026 across four Local Government Areas: Idi-Oro (urban), Gwarin (rural),
Katsuma (rural), and Ilela (mixed). Vaccination teams carried GPS loggers recording a fix
approximately every 60 seconds. Teams also completed a daily paper e-tally of doses
administered, which was later keyed in.

## Files

### `tracks/` (160 files, 956,702 points in total)
One file per team per campaign day, named `<team_id>_<date>.csv`.

**`T04_2026-03-11.csv`**  (11,830 rows)  
Columns are identical across all track files.

| Column | Type | Example |
|---|---|---|
| `team_id` | str | T04 |
| `logger_id` | str | GL-4396 |
| `timestamp` | str | 2026-03-11 07:23:00 |
| `longitude` | float64 | 8.223934 |
| `latitude` | float64 | 10.700408 |
| `accuracy_m` | float64 | 5.1 |
| `speed_kmh` | float64 | 4.0 |

### Reference and reporting files

**`settlement_masterlist.csv`**  (2,562 rows)  
The planned settlement list used for microplanning.

| Column | Type | Example |
|---|---|---|
| `settlement_id` | str | S00790 |
| `settlement_name` | str | Uztsimi |
| `settlement_type` | str | Village |
| `ward_code` | str | W009 |
| `ward_name` | str | Washatu |
| `lga_code` | str | LGA02 |
| `lga_name` | str | Gwarin |
| `longitude` | float64 | 7.514759 |
| `latitude` | float64 | 11.01041 |
| `target_population_under5` | float64 | 125.0 |

**`etally_daily.csv`**  (2,023 rows)  
Doses administered as reported by teams on the paper e-tally.

| Column | Type | Example |
|---|---|---|
| `campaign_date` | str | 2026-03-09 |
| `team_id` | str | T01 |
| `settlement_id` | str | S00033 |
| `ward_code` | str | W001 |
| `lga_name` | str | Idi-Oro |
| `target_population_under5` | int64 | 31 |
| `doses_administered` | int64 | 23 |

**`inaccessible_settlements.csv`**  (75 rows)  
Settlements classified before the round as inaccessible on security grounds.

| Column | Type | Example |
|---|---|---|
| `settlement_id` | str | S00955 |
| `settlement_name` | str | Datina |
| `ward_code` | str | W013 |
| `ward_name` | str | Sashako |
| `lga_name` | str | Gwarin |
| `security_classification` | str | Inaccessible |
| `date_classified` | str | 2026-02-24 |

**`boundaries.gpkg`**

- Layer `wards`: 40 features, Polygon, CRS EPSG:4326
  Fields: `ward_code`, `ward_name`, `lga_code`, `lga_name`, `lga_type`, `state_name`
- Layer `lgas`: 4 features, Polygon, CRS EPSG:4326
  Fields: `lga_code`, `lga_name`, `lga_type`, `state_name`
- Layer `state`: 1 features, Polygon, CRS EPSG:4326
  Fields: `state_name`

## Notes you should not need to be told, but which are stated once

- Coordinates are supplied in EPSG:4326. Any distance, area, or buffer operation requires a
  projected coordinate reference system. Choosing one and saying why is part of the task.
- The data contains genuine defects. Some are recording errors, some are equipment failures,
  and some are real programmatic findings. Telling them apart is the assessment.
- Do not delete records you cannot explain. Flag them, count them, and report them.
