"""
Stage 5: Produce final outputs for the Q2 deliverable.

  1. wards_accessibility.gpkg — ward polygons joined with population,
     travel time to nearest adequate facility, travel time to nearest
     facility of any status, and gap_type classification. This is the
     file to bring into ArcGIS Pro for the final A3 cartography — no
     further joins should be needed there.

  2. ward_summary_table.csv — the same data as a flat table, for the
     appendix of the written report.

  3. most_severe_gaps.csv — the top N wards by travel time to nearest
     adequate facility, split out by gap_type. This directly answers
     the assessment's requirement to identify where the access gap is
     most severe AND distinguish facility-absent from understaffed-
     facility causes in the same view.

Nothing here re-derives numbers — it only joins and formats what
02_load_db.py, 03_compute_access.py, and 04_classify_gaps.py already
computed and stored in the database.
"""
import duckdb


def make_outputs(
    db_path: str,
    gpkg_output: str,
    summary_csv_output: str,
    most_severe_csv_output: str,
    top_n_per_gap_type: int = 15,
) -> None:
    con = duckdb.connect(db_path)
    con.execute("LOAD spatial;")

    con.execute("""
        CREATE OR REPLACE TABLE ward_output AS
        SELECT
            w.ward_code,
            g.ward_name,
            g.total_population,
            g.population_under5,
            g.travel_time_to_adequate_min,
            g.nearest_adequate_facility_id,
            g.travel_time_to_any_facility_min,
            g.nearest_any_facility_id,
            g.gap_type,
            w.geom
        FROM wards w
        JOIN ward_gap_classification g ON w.ward_code = g.ward_code
    """)
    n = con.execute("SELECT COUNT(*) FROM ward_output").fetchone()[0]
    print(f"[outputs] ward_output: {n} wards joined (geometry + accessibility + gap classification)")

    # --- 1. GeoPackage for ArcGIS -----------------------------------------
    # SRS is set explicitly here because DuckDB's GEOMETRY type does not
    # track a coordinate system per column through arbitrary SQL
    # transformations — without this, the exported .gpkg has correct
    # WGS84 coordinate values but no CRS metadata, which is why ArcGIS
    # reports "projection not defined" even though the coordinates
    # themselves are fine. All source layers were confirmed EPSG:4326.
    con.execute(f"""
        COPY ward_output TO '{gpkg_output}' WITH (FORMAT GDAL, DRIVER 'GPKG', SRS 'EPSG:4326')
    """)
    print(f"[outputs] wrote {gpkg_output} — ready to open directly in ArcGIS Pro")

    # --- 2. Flat summary table (no geometry) for the report appendix ------
    con.execute(f"""
        COPY (SELECT * EXCLUDE (geom) FROM ward_output ORDER BY travel_time_to_adequate_min DESC)
        TO '{summary_csv_output}' (HEADER, DELIMITER ',')
    """)
    print(f"[outputs] wrote {summary_csv_output}")

    # --- 3. Most severe gaps, split by cause -------------------------------
    con.execute(f"""
        COPY (
            SELECT * EXCLUDE (geom) FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY gap_type
                        ORDER BY travel_time_to_adequate_min DESC
                    ) AS severity_rank
                FROM ward_output
                WHERE gap_type != 'adequately_served'
            )
            WHERE severity_rank <= {top_n_per_gap_type}
            ORDER BY gap_type, severity_rank
        ) TO '{most_severe_csv_output}' (HEADER, DELIMITER ',')
    """)
    print(f"[outputs] wrote {most_severe_csv_output} — top {top_n_per_gap_type} most severe "
          f"wards per gap_type (facility_absent and facility_present_understaffed)")

    con.close()


if __name__ == "__main__":
    make_outputs(
        db_path=r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\q2.duckdb",
        gpkg_output=r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\wards_accessibility.gpkg",
        summary_csv_output=r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\ward_summary_table.csv",
        most_severe_csv_output=r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\most_severe_gaps.csv",
    )