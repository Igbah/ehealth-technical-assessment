"""
Stage 2: Load all cleaned/reference data into a single DuckDB database
with spatial support, ready for the accessibility analysis in Stage 3.

Sources loaded:
  - facilities_clean.csv          (output of 01_clean.py)
  - admin_boundaries.gpkg         states, senatorial_districts, lgas, wards
  - ward_population.csv           only used for its 'population_source'
                                   column — population counts themselves
                                   are read from the gpkg 'wards' layer,
                                   which is authoritative: it agrees with
                                   the CSV on every value the CSV has, and
                                   is additionally complete where the CSV
                                   has 14 missing values.
  - minimum_staffing_norms.csv    adequacy thresholds by facility_type
  - facility_personnel_scores.mid/.mif   MapInfo pair — .mif holds point
                                   geometry + column schema only, .mid
                                   holds the actual attribute values.
                                   The two files share no key column and
                                   must be joined purely by row order.
  - road_network.geojson          used later for the accessibility calc

Every load step prints row counts and flags anything dropped or
unmatched — nothing is silently discarded.
"""
import re

import duckdb
import pandas as pd


# ---------------------------------------------------------------------------
# facility_personnel_scores.mid/.mif reader
# ---------------------------------------------------------------------------

def read_personnel_scores(mif_path: str, mid_path: str) -> pd.DataFrame:
    """Parse the paired MapInfo files. The .mif's 'Point lon lat' lines and
    the .mid's comma-delimited attribute rows have no shared key — they are
    aligned purely by row order, so row-count must match exactly or the
    join is unsafe and we refuse to guess."""
    points = []
    with open(mif_path, "r", encoding="latin-1") as f:
        for line in f:
            m = re.match(r"^\s*Point\s+([\-\d.]+)\s+([\-\d.]+)", line)
            if m:
                points.append((float(m.group(1)), float(m.group(2))))

    columns = ["facility_id", "facility_name", "med_officers", "nurses_midwives",
               "chews", "lab_scientists", "pharm_techs", "personnel_score", "sen_rank"]
    df = pd.read_csv(mid_path, header=None, names=columns)

    if len(df) != len(points):
        raise ValueError(
            f"Row count mismatch: {len(df)} .mid rows vs {len(points)} .mif points — "
            "cannot safely align without a shared key. Do not proceed until resolved."
        )

    df["longitude"] = [p[0] for p in points]
    df["latitude"] = [p[1] for p in points]

    # Drop the known junk placeholder rows (HF7xxxx, "Unnamed facility",
    # SEN_RANK=999) — same synthetic-noise pattern seen in health_facilities.csv.
    junk_mask = df["facility_name"].str.strip().str.lower() == "unnamed facility"
    n_junk = int(junk_mask.sum())
    df = df[~junk_mask].copy()
    print(f"[load_db] facility_personnel_scores: {n_junk} junk placeholder rows dropped, "
          f"{len(df)} real rows remain")

    return df


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def load_database(
    db_path: str,
    facilities_clean_csv: str,
    admin_boundaries_gpkg: str,
    ward_population_csv: str,
    minimum_staffing_norms_csv: str,
    personnel_scores_mif: str,
    personnel_scores_mid: str,
    road_network_geojson: str,
) -> None:
    con = duckdb.connect(db_path)
    con.execute("INSTALL spatial; LOAD spatial;")

    # --- facilities -----------------------------------------------------
    con.execute(f"""
        CREATE OR REPLACE TABLE facilities AS
        SELECT *,
            CASE WHEN coord_status = 'included'
                 THEN ST_Point(longitude_clean, latitude_clean)
                 ELSE NULL END AS geom
        FROM read_csv_auto('{facilities_clean_csv}', ALL_VARCHAR=FALSE)
    """)
    n_facilities = con.execute("SELECT COUNT(*) FROM facilities").fetchone()[0]
    n_geo = con.execute("SELECT COUNT(*) FROM facilities WHERE geom IS NOT NULL").fetchone()[0]
    print(f"[load_db] facilities: {n_facilities} loaded, {n_geo} with usable geometry")

    # --- spatial boundary layers -----------------------------------------
    for layer in ("states", "senatorial_districts", "lgas", "wards"):
        con.execute(f"""
            CREATE OR REPLACE TABLE {layer} AS
            SELECT * FROM ST_Read('{admin_boundaries_gpkg}', layer='{layer}')
        """)
        n = con.execute(f"SELECT COUNT(*) FROM {layer}").fetchone()[0]
        print(f"[load_db] {layer}: {n} features loaded from admin_boundaries.gpkg")

    # --- ward population_source metadata (population counts already in wards) ---
    con.execute(f"""
        CREATE OR REPLACE TABLE ward_population_source AS
        SELECT ward_code, population_source
        FROM read_csv_auto('{ward_population_csv}')
    """)
    con.execute("""
        ALTER TABLE wards ADD COLUMN IF NOT EXISTS population_source VARCHAR
    """)
    con.execute("""
        UPDATE wards
        SET population_source = ward_population_source.population_source
        FROM ward_population_source
        WHERE wards.ward_code = ward_population_source.ward_code
    """)
    n_null_pop = con.execute(
        "SELECT COUNT(*) FROM wards WHERE total_population IS NULL"
    ).fetchone()[0]
    print(f"[load_db] wards: population loaded from gpkg (authoritative — complete "
          f"where ward_population.csv had 14 missing values); {n_null_pop} still null")

    # --- minimum staffing norms -------------------------------------------
    con.execute(f"""
        CREATE OR REPLACE TABLE minimum_staffing_norms AS
        SELECT * FROM read_csv_auto('{minimum_staffing_norms_csv}')
    """)
    n_norms = con.execute("SELECT COUNT(*) FROM minimum_staffing_norms").fetchone()[0]
    print(f"[load_db] minimum_staffing_norms: {n_norms} facility types loaded")

    # --- facility personnel scores (.mid/.mif) -----------------------------
    personnel_df = read_personnel_scores(personnel_scores_mif, personnel_scores_mid)
    con.register("personnel_df", personnel_df)
    con.execute("CREATE OR REPLACE TABLE facility_personnel_scores AS SELECT * FROM personnel_df")

    # Sanity cross-check: for facilities present in both tables, do the
    # .mif point coordinates roughly agree with facilities_clean's own
    # cleaned coordinates? A large disagreement would suggest the two
    # datasets don't actually describe the same facility despite matching
    # IDs — worth knowing before joining them for the accessibility calc.
    mismatch = con.execute("""
        SELECT COUNT(*) FROM facilities f
        JOIN facility_personnel_scores p ON f.facility_id = p.facility_id
        WHERE f.geom IS NOT NULL
          AND (ABS(f.longitude_clean - p.longitude) > 0.05
               OR ABS(f.latitude_clean - p.latitude) > 0.05)
    """).fetchone()[0]
    n_joined = con.execute("""
        SELECT COUNT(*) FROM facilities f
        JOIN facility_personnel_scores p ON f.facility_id = p.facility_id
    """).fetchone()[0]
    n_personnel_unmatched = con.execute("""
        SELECT COUNT(*) FROM facility_personnel_scores p
        LEFT JOIN facilities f ON f.facility_id = p.facility_id
        WHERE f.facility_id IS NULL
    """).fetchone()[0]
    print(f"[load_db] facility_personnel_scores: {len(personnel_df)} facilities loaded, "
          f"{n_joined} match a facility_id in facilities_clean.csv, "
          f"{n_personnel_unmatched} do not")
    print(f"[load_db] coordinate cross-check: {mismatch}/{n_joined} matched facilities have "
          f".mif coordinates >0.05° away from their facilities_clean coordinates "
          f"(review these — may indicate a facility_id collision, not just noise)")

    # --- road network -------------------------------------------------------
    con.execute(f"""
        CREATE OR REPLACE TABLE road_network AS
        SELECT * FROM ST_Read('{road_network_geojson}')
    """)
    n_roads = con.execute("SELECT COUNT(*) FROM road_network").fetchone()[0]
    print(f"[load_db] road_network: {n_roads} road segments loaded")

    con.close()
    print(f"[load_db] database written to {db_path}")


if __name__ == "__main__":
    load_database(
        db_path=r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\q2.duckdb",
        facilities_clean_csv=r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\facilities_clean.csv",
        admin_boundaries_gpkg=r"C:\Users\Administrator\Desktop\e-health_assessment\Data\Part1_Q2_Facility_Access\admin_boundaries.gpkg",
        ward_population_csv=r"C:\Users\Administrator\Desktop\e-health_assessment\Data\Part1_Q2_Facility_Access\ward_population.csv",
        minimum_staffing_norms_csv=r"C:\Users\Administrator\Desktop\e-health_assessment\Data\Part1_Q2_Facility_Access\minimum_staffing_norms.csv",
        personnel_scores_mif=r"C:\Users\Administrator\Desktop\e-health_assessment\Data\Part1_Q2_Facility_Access\facility_personnel_scores.mif",
        personnel_scores_mid=r"C:\Users\Administrator\Desktop\e-health_assessment\Data\Part1_Q2_Facility_Access\facility_personnel_scores.mid",
        road_network_geojson=r"C:\Users\Administrator\Desktop\e-health_assessment\Data\Part1_Q2_Facility_Access\road_network.geojson",
    )