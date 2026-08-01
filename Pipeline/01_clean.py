"""
Stage 1: Clean and reconcile the raw facility file.

Combines three cleaning concerns into one auditable pass:
  A. Coordinate repair  — comma-decimal corruption, DMS format,
                           out-of-bounds values, missing values.
  B. Junk-row removal   — placeholder "Unnamed facility" rows.
  C. LGA reconciliation — fuzzy-match each facility's self-reported
                           lga_name against the authoritative
                           LGA_SEN_Districts reference table, and
                           cross-check the facility's self-reported
                           sen_district against the authoritative one.

Every decision is written to a reconciliation log — nothing is
silently dropped or silently corrected.

Input:  health_facilities.csv, LGA_SEN_Districts.xlsx
Output: facilities_clean.csv, reconciliation_log.csv
"""
import re

import pandas as pd
from rapidfuzz import fuzz, process

NIGERIA_LON_RANGE = (2.5, 15.0)
NIGERIA_LAT_RANGE = (4.0, 14.0)

DMS_PATTERN = re.compile(
    r"""^\s*(\d+)[°]\s*(\d+)['’]\s*([\d.]+)["”]\s*([NSEW])\s*$"""
)

FUZZY_MATCH_THRESHOLD = 85  # below this, treat as unmatched rather than guess


# ---------------------------------------------------------------------------
# A. Coordinate repair
# ---------------------------------------------------------------------------

def dms_to_decimal(dms_str: str):
    match = DMS_PATTERN.match(str(dms_str).strip())
    if not match:
        return None
    degrees, minutes, seconds, direction = match.groups()
    value = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    if direction in ("S", "W"):
        value = -value
    return value


def fix_comma_decimal(value_str: str):
    s = str(value_str).strip()
    if "," not in s:
        return None
    groups = s.split(",")
    try:
        int_part_len = len(groups[0])
        digits = "".join(groups)
        int(digits)
    except ValueError:
        return None
    candidate = float(f"{digits[:int_part_len]}.{digits[int_part_len:]}")
    return candidate if 0 < candidate < 180 else None


def parse_coordinate(value):
    if pd.isna(value) or str(value).strip() == "":
        return None, "missing"
    s = str(value).strip()
    if "°" in s:
        result = dms_to_decimal(s)
        return (result, "dms") if result is not None else (None, "unparseable")
    if "," in s:
        result = fix_comma_decimal(s)
        return (result, "comma_decimal") if result is not None else (None, "unparseable")
    try:
        return float(s), "clean"
    except ValueError:
        return None, "unparseable"


def is_within_nigeria(lon: float, lat: float) -> bool:
    return (
        NIGERIA_LON_RANGE[0] <= lon <= NIGERIA_LON_RANGE[1]
        and NIGERIA_LAT_RANGE[0] <= lat <= NIGERIA_LAT_RANGE[1]
    )


# ---------------------------------------------------------------------------
# C. LGA name reconciliation
# ---------------------------------------------------------------------------

def normalize_lga_name(name: str) -> str:
    """Lowercase, strip whitespace, drop a trailing ' LGA' / ' Local Govt Area' suffix."""
    s = str(name).strip()
    s = re.sub(r"\s+lga\s*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+local\s+govt\s+area\s*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def build_lga_reference(ref_xlsx: str) -> pd.DataFrame:
    """Load the LGA_SEN_Districts reference spreadsheet.

    Handles two real quirks of the source file:
      - it's .xlsx, not .csv, so it must be read with read_excel
      - the STATE column is only populated on the first LGA row of
        each state block (a merged-cell artifact) and needs forward-fill
    """
    raw = pd.read_excel(ref_xlsx, sheet_name=0)

    # Position-based rename: robust to the exact header text/casing
    # ("L.G.A" vs "lga" etc.) as long as column ORDER matches the
    # documented layout: STATE | L.G.A | SEN DISTRICT | Wards | LGA Code | Remarks
    raw = raw.rename(columns={
        raw.columns[0]: "state",
        raw.columns[1]: "lga",
        raw.columns[2]: "senatorial_district",
        raw.columns[3]: "n_wards",
        raw.columns[4]: "lga_code",
        raw.columns[5]: "remarks",
    })

    # Drop title/footer/blank rows — anything without a real LGA name
    raw = raw[raw["lga"].notna()]
    raw = raw[raw["lga"].astype(str).str.strip() != ""]
    raw = raw[raw["lga"].astype(str).str.strip().str.upper() != "TOTAL"]

    # Forward-fill merged-cell columns. Both STATE and SENATORIAL DISTRICT
    # are only populated on the first LGA row of their block in the source
    # spreadsheet — a nested merged-cell pattern (each state contains
    # several senatorial districts, each senatorial district contains
    # several LGAs, and only the first row of each block carries the label).
    raw["state"] = raw["state"].ffill()
    raw["senatorial_district"] = raw["senatorial_district"].ffill()

    ref = raw.reset_index(drop=True).copy()
    ref["lga_norm"] = ref["lga"].apply(normalize_lga_name)

    # Detect duplicate lga_code entries with conflicting sen_district —
    # this is a real data-quality condition in the source, not a bug.
    dupe_codes = ref["lga_code"][ref["lga_code"].duplicated(keep=False)]
    if not dupe_codes.empty:
        print(f"[reconcile] {dupe_codes.nunique()} LGA code(s) have conflicting "
              f"senatorial-district rows in the reference table: "
              f"{sorted(dupe_codes.astype(str).unique())}")
        # Resolution rule: prefer the row whose Remarks cites a specific
        # gazette/transfer notice over a plain unremarked row, since that
        # indicates the more recent authoritative assignment.
        ref["_has_gazette"] = ref["remarks"].astype(str).str.contains(
            "gazette", case=False, na=False
        )
        ref = (
            ref.sort_values("_has_gazette", ascending=False)
            .drop_duplicates(subset="lga_code", keep="first")
            .drop(columns="_has_gazette")
            .reset_index(drop=True)
        )

    return ref


def reconcile_lga(facility_lga: str, facility_sen_district: str, ref: pd.DataFrame):
    """
    Returns dict with matched lga_code, canonical lga name, canonical
    sen_district, match method/score, and whether the facility's own
    reported sen_district agrees with the authoritative one.
    """
    if pd.isna(facility_lga) or str(facility_lga).strip() == "":
        return {
            "lga_match_method": "missing",
            "lga_match_score": None,
            "matched_lga_code": None,
            "matched_lga_canonical": None,
            "matched_sen_district": None,
            "sen_district_agrees": None,
        }

    query = normalize_lga_name(facility_lga)
    choices = ref["lga_norm"].tolist()

    match = process.extractOne(query, choices, scorer=fuzz.WRatio)
    if match is None or match[1] < FUZZY_MATCH_THRESHOLD:
        return {
            "lga_match_method": "unmatched",
            "lga_match_score": None if match is None else match[1],
            "matched_lga_code": None,
            "matched_lga_canonical": None,
            "matched_sen_district": None,
            "sen_district_agrees": None,
        }

    matched_norm, score, _ = match
    row = ref[ref["lga_norm"] == matched_norm].iloc[0]
    method = "exact" if score == 100 else "fuzzy"
    agrees = (
        normalize_lga_name(facility_sen_district) == normalize_lga_name(row["senatorial_district"])
        if pd.notna(facility_sen_district)
        else None
    )
    return {
        "lga_match_method": method,
        "lga_match_score": score,
        "matched_lga_code": row["lga_code"],
        "matched_lga_canonical": row["lga"],
        "matched_sen_district": row["senatorial_district"],
        "sen_district_agrees": agrees,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def clean(facilities_csv: str, lga_ref_xlsx: str, output_csv: str, log_csv: str) -> None:
    df = pd.read_csv(facilities_csv, dtype=str)
    ref = build_lga_reference(lga_ref_xlsx)

    # B. Drop junk placeholder rows
    junk_mask = df["facility_name"].str.strip().str.lower() == "unnamed facility"
    n_junk = int(junk_mask.sum())
    df = df[~junk_mask].copy()

    log_rows = []
    lons, lats, coord_statuses = [], [], []

    for _, row in df.iterrows():
        # A. Coordinates
        lon_val, lon_method = parse_coordinate(row["longitude"])
        lat_val, lat_method = parse_coordinate(row["latitude"])
        if lon_val is None or lat_val is None:
            coord_status = "excluded_missing_or_unparseable"
            lon_val = lat_val = None
        elif not is_within_nigeria(lon_val, lat_val):
            coord_status = "excluded_out_of_bounds"
            lon_val = lat_val = None
        else:
            coord_status = "included"
        lons.append(lon_val)
        lats.append(lat_val)
        coord_statuses.append(coord_status)

        # C. LGA reconciliation
        lga_result = reconcile_lga(row["lga_name"], row.get("sen_district"), ref)

        log_rows.append({
            "facility_id": row["facility_id"],
            "raw_lga_name": row["lga_name"],
            "raw_sen_district": row.get("sen_district"),
            "raw_longitude": row["longitude"],
            "raw_latitude": row["latitude"],
            "lon_parse_method": lon_method,
            "lat_parse_method": lat_method,
            "coord_status": coord_status,
            **lga_result,
        })

    df["longitude_clean"] = lons
    df["latitude_clean"] = lats
    df["coord_status"] = coord_statuses

    log_df = pd.DataFrame(log_rows)
    df = df.merge(log_df[[
        "facility_id", "matched_lga_code", "matched_lga_canonical",
        "matched_sen_district", "sen_district_agrees",
    ]], on="facility_id", how="left")

    df.to_csv(output_csv, index=False)
    log_df.to_csv(log_csv, index=False)

    n_total = len(df)
    n_coord_ok = (df["coord_status"] == "included").sum()
    n_lga_unmatched = (log_df["lga_match_method"] == "unmatched").sum()
    n_sen_conflict = (log_df["sen_district_agrees"] == False).sum()  # noqa: E712

    print(f"[clean] {n_junk} junk placeholder rows dropped")
    print(f"[clean] {n_coord_ok}/{n_total} facilities have usable coordinates")
    print(f"[clean] {n_lga_unmatched}/{n_total} facilities could not be matched to an LGA")
    print(f"[clean] {n_sen_conflict}/{n_total} facilities disagree with the reference "
          f"table on senatorial district")
    print(f"[clean] full reconciliation log written to {log_csv}")


if __name__ == "__main__":
    clean(
        r"C:\Users\Administrator\Desktop\e-health_assessment\Data\Part1_Q2_Facility_Access\health_facilities.csv",
        r"C:\Users\Administrator\Desktop\e-health_assessment\Data\Part1_Q2_Facility_Access\LGA_SEN_Districts.xlsx",
        r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\facilities_clean.csv",
        r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\reconciliation_log.csv",
    )