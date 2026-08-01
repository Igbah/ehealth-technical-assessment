import duckdb

con = duckdb.connect(r"Outputs\q2.duckdb")

query = """
SELECT f.facility_id, f.facility_name, f.longitude_clean, f.latitude_clean,
       p.longitude, p.latitude, p.facility_name AS personnel_facility_name
FROM facilities f
JOIN facility_personnel_scores p ON f.facility_id = p.facility_id
WHERE f.geom IS NOT NULL
  AND (ABS(f.longitude_clean - p.longitude) > 0.05
       OR ABS(f.latitude_clean - p.latitude) > 0.05)
"""

df = con.execute(query).fetchdf()
print(df.to_string())