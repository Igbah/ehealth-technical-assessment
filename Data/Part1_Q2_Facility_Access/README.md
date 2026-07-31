# Part 1, Question 2: Facility Readiness, Accessibility and a Governed Spatial Database

All data in this pack is synthetic. The country, states, senatorial districts, local government
areas, wards, and facilities are invented. Any resemblance to a real administrative structure
is incidental.

## Context

A national health facility assessment has scored facilities on the availability of key personnel
across five cadres. The ministry wants to know where populations are underserved, which is not
the same question as where facilities score poorly.

## Files

**`health_facilities.csv`**  (1,346 rows)  
The facility register as received. Coordinates are supplied as text because the source system permitted free entry.

| Column | Type | Example |
|---|---|---|
| `facility_id` | str | HF00260 |
| `facility_name` | str | Uzoyosa Primary Health Centre |
| `facility_type` | str | Primary Health Centre |
| `ward_name` | str | Agbratu |
| `lga_name` | str | Agbmita |
| `sen_district` | str | Agbzatu North |
| `state_name` | str | Agbzatu State |
| `ownership` | str | Public |
| `longitude` | str | 7.908017 |
| `latitude` | str | 7.950908 |

**`minimum_staffing_norms.csv`**  (5 rows)  
The published minimum staffing standard by facility type. Use this to define adequacy rather than inventing a cut point.

| Column | Type | Example |
|---|---|---|
| `facility_type` | str | Health Post |
| `min_medical_officers` | int64 | 0 |
| `min_nurses_midwives` | int64 | 0 |
| `min_chews` | int64 | 2 |
| `min_lab_scientists` | int64 | 0 |
| `min_pharmacy_technicians` | int64 | 0 |
| `adequacy_rule` | str | Facility is adequately staffed whe |

**`ward_population.csv`**  (620 rows)  
Ward population, with the estimation source recorded.

| Column | Type | Example |
|---|---|---|
| `ward_code` | str | W0021 |
| `ward_name` | str | Ekeluno |
| `lga_code` | str | LGA071 |
| `lga_name` | str | Maltsimi |
| `total_population` | float64 | 6698.0 |
| `population_under5` | float64 | 1014.0 |
| `population_source` | str | Projected 2026 from 2006 census |

**`facility_personnel_scores.mif` and `facility_personnel_scores.mid`**

The personnel scoring output, supplied in MapInfo Interchange Format as exported by the
assessment contractor. This is a point layer with attributes. `.mif` holds the header and
geometry, `.mid` holds the attribute rows. GDAL, QGIS, and geopandas can all read it.
Attribute columns are declared in the `.mif` header.

**`LGA_SEN_Districts.xlsx`**

The administrative crosswalk mapping local government areas to senatorial districts,
as issued by the Office of the Surveyor General. It is not a clean table. You may not edit
it by hand.

**`admin_boundaries.gpkg`**

- Layer `wards`: 620 features, Polygon, CRS EPSG:4326
  Fields: `ward_code`, `ward_name`, `lga_code`, `lga_name`, `sen_code`, `sen_district`, `state_code`, `state_name`, `total_population`, `population_under5`
- Layer `lgas`: 121 features, MultiPolygon, CRS EPSG:4326
  Fields: `lga_code`, `lga_name`, `sen_code`, `sen_district`, `state_code`, `state_name`
- Layer `senatorial_districts`: 18 features, Polygon, CRS EPSG:4326
  Fields: `sen_code`, `sen_district`, `state_code`, `state_name`
- Layer `states`: 6 features, Polygon, CRS EPSG:4326
  Fields: `state_code`, `state_name`

**`road_network.geojson`**

A simplified road network with class, surface, and an indicative speed in kilometres per hour.
Supplied in case you choose a network based accessibility measure. You are not obliged to use it.

## Notes

- The facility register, the scoring file, and the crosswalk do not agree with one another.
  Reconciling them, and documenting what you could not reconcile, is part of the task.
- The workbook contains more than one sheet. Read all of them before deciding what is authoritative.
