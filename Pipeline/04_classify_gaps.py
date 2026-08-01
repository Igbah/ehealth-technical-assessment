"""
Stage 4: Classify each ward's access gap by cause.

03_compute_access.py already computed each ward's travel time to its
nearest ADEQUATELY-STAFFED facility. That number alone can't tell you
why a ward is underserved — it could be because no facility exists
nearby at all, or because a facility exists nearby but fails minimum
staffing norms. Those need different interventions (build a new
facility vs. staff an existing one), so this stage computes a second
measure — travel time to the nearest facility of ANY staffing status —
and compares the two to classify the cause.

Classification logic (UNDERSERVED_THRESHOLD_MIN is a documented,
adjustable assumption — see below):

  - travel_time_to_adequate <= threshold
        -> "adequately_served"
  - travel_time_to_adequate >  threshold AND
    travel_time_to_any_facility <= threshold
        -> "facility_present_understaffed"
        (a facility is reasonably close; it just doesn't meet staffing norms)
  - travel_time_to_adequate >  threshold AND
    travel_time_to_any_facility >  threshold (or unreachable)
        -> "facility_absent"
        (no facility of any kind is reasonably close)

Reuses the road network graph and routing approach already verified in
03_compute_access.py, applied a second time with an unfiltered facility
set (adequate + inadequate + unknown, excluding only unusable
coordinates) as the target set instead of adequate-only.

Input:  the DuckDB database built by 02_load_db.py, plus the
        facility_adequacy and road_network tables it and
        03_compute_access.py already populated.
Output: ward_gap_classification.csv
"""
import math

import duckdb
import pandas as pd
import networkx as nx
from shapely import wkt as shapely_wkt

UNDERSERVED_THRESHOLD_MIN = 60  # ASSUMPTION: a commonly-cited benchmark for
                                 # emergency/essential health service access.
                                 # Adjust here; the classification is sensitive
                                 # to this choice, so the summary output also
                                 # prints the full travel-time distribution so
                                 # the reader can judge sensitivity themselves.

OFFROAD_SPEED_KMH = 20  # must match the assumption used in 03_compute_access.py


def haversine_km(lon1, lat1, lon2, lat2) -> float:
    R = 6371.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_road_graph(con) -> nx.Graph:
    rows = con.execute("SELECT speed_kmh, ST_AsText(geom) AS wkt FROM road_network").fetchall()
    G = nx.Graph()
    for speed_kmh, wkt in rows:
        line = shapely_wkt.loads(wkt)
        coords = list(line.coords)
        for i in range(len(coords) - 1):
            a, b = coords[i], coords[i + 1]
            dist_km = haversine_km(a[0], a[1], b[0], b[1])
            time_min = (dist_km / speed_kmh) * 60
            G.add_edge(a, b, weight=time_min, dist_km=dist_km)
    return G


def nearest_road_node(point, graph_nodes) -> tuple:
    best_node, best_dist = None, None
    for n in graph_nodes:
        d = haversine_km(point[0], point[1], n[0], n[1])
        if best_dist is None or d < best_dist:
            best_node, best_dist = n, d
    return best_node, best_dist


def nearest_facility_travel_time(con, road_graph: nx.Graph, facility_query: str) -> pd.DataFrame:
    """Given a SQL query selecting (facility_id, longitude_clean,
    latitude_clean) for some subset of facilities, return a per-ward
    dataframe of travel time to the nearest one, using the same
    snap-to-road-node + cached single-source Dijkstra approach as
    03_compute_access.py."""
    graph_nodes = list(road_graph.nodes())
    facilities = con.execute(facility_query).fetchdf()

    node_to_facilities = {}
    for _, row in facilities.iterrows():
        pt = (row["longitude_clean"], row["latitude_clean"])
        node, dist_km = nearest_road_node(pt, graph_nodes)
        offroad_min = (dist_km / OFFROAD_SPEED_KMH) * 60
        node_to_facilities.setdefault(node, []).append((row["facility_id"], offroad_min))

    dist_cache = {}
    for node in node_to_facilities:
        dist_cache[node] = nx.single_source_dijkstra_path_length(road_graph, node, weight="weight")

    wards = con.execute("""
        SELECT ward_code, ST_X(ST_Centroid(geom)) AS cx, ST_Y(ST_Centroid(geom)) AS cy
        FROM wards
    """).fetchdf()

    results = []
    for _, w in wards.iterrows():
        ward_node, ward_offroad_km = nearest_road_node((w["cx"], w["cy"]), graph_nodes)
        ward_offroad_min = (ward_offroad_km / OFFROAD_SPEED_KMH) * 60

        best_time, best_facility = None, None
        for node, facs in node_to_facilities.items():
            path_time = dist_cache[node].get(ward_node)
            if path_time is None:
                continue
            for fac_id, fac_offroad_min in facs:
                total = ward_offroad_min + path_time + fac_offroad_min
                if best_time is None or total < best_time:
                    best_time, best_facility = total, fac_id

        results.append({
            "ward_code": w["ward_code"],
            "travel_time": round(best_time, 1) if best_time is not None else None,
            "facility_id": best_facility,
        })

    return pd.DataFrame(results)


def classify_gaps(db_path: str, output_csv: str) -> None:
    con = duckdb.connect(db_path)
    con.execute("LOAD spatial;")

    road_graph = build_road_graph(con)

    # Measure 1: nearest ADEQUATE facility (should match 03_compute_access.py's
    # own numbers — recomputed here rather than re-read from its CSV so this
    # script is self-contained and doesn't depend on file paths from stage 3).
    to_adequate = nearest_facility_travel_time(con, road_graph, """
        SELECT facility_id, longitude_clean, latitude_clean
        FROM facility_adequacy
        WHERE adequacy_status = 'adequate' AND geom IS NOT NULL
    """).rename(columns={"travel_time": "travel_time_to_adequate_min",
                          "facility_id": "nearest_adequate_facility_id"})

    # Measure 2: nearest facility of ANY staffing status (adequate,
    # inadequate, or unknown — anything with usable coordinates).
    to_any = nearest_facility_travel_time(con, road_graph, """
        SELECT facility_id, longitude_clean, latitude_clean
        FROM facility_adequacy
        WHERE geom IS NOT NULL
    """).rename(columns={"travel_time": "travel_time_to_any_facility_min",
                          "facility_id": "nearest_any_facility_id"})

    wards = con.execute("""
        SELECT ward_code, ward_name, total_population, population_under5
        FROM wards
    """).fetchdf()

    df = wards.merge(to_adequate, on="ward_code", how="left").merge(to_any, on="ward_code", how="left")

    def classify(row):
        t_adequate = row["travel_time_to_adequate_min"]
        t_any = row["travel_time_to_any_facility_min"]
        if pd.notna(t_adequate) and t_adequate <= UNDERSERVED_THRESHOLD_MIN:
            return "adequately_served"
        if pd.notna(t_any) and t_any <= UNDERSERVED_THRESHOLD_MIN:
            return "facility_present_understaffed"
        return "facility_absent"

    df["gap_type"] = df.apply(classify, axis=1)

    con.register("gap_df", df)
    con.execute("CREATE OR REPLACE TABLE ward_gap_classification AS SELECT * FROM gap_df")
    con.execute(f"COPY ward_gap_classification TO '{output_csv}' (HEADER, DELIMITER ',')")
    con.close()

    print(f"[gaps] classification threshold: {UNDERSERVED_THRESHOLD_MIN} minutes "
          f"(travel time to nearest adequate facility)")
    print("[gaps] gap_type breakdown:")
    for gap_type, n in df["gap_type"].value_counts().items():
        pop = df.loc[df["gap_type"] == gap_type, "total_population"].sum()
        print(f"  {gap_type}: {n} wards, {pop:,.0f} people")

    print("\n[gaps] travel-time-to-adequate-facility distribution (for threshold sensitivity check):")
    print(df["travel_time_to_adequate_min"].describe().to_string())

    print(f"\n[gaps] wrote {output_csv}")


if __name__ == "__main__":
    classify_gaps(
        db_path=r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\q2.duckdb",
        output_csv=r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\ward_gap_classification.csv",
    )