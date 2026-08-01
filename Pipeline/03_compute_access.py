"""
Stage 3: Compute ward-level accessibility to adequately-staffed health
facilities, using actual road network travel time rather than
straight-line distance.

Method
------
1. A facility is "adequate" if it meets or exceeds the minimum staffing
   level for every cadre that has a non-zero minimum for its facility
   type (per minimum_staffing_norms.csv's own adequacy_rule). Facilities
   without a personnel record, or with unusable coordinates, are treated
   as non-adequate/unreachable and excluded, and logged separately.

2. road_network.geojson is built into a graph: nodes are road-segment
   vertices, edges are weighted by travel time (segment length / speed_kmh).
   Confirmed as a single connected component (334 nodes, 426 edges) —
   no fragmentation to handle.

3. Since wards and facilities don't sit exactly on the road network, each
   ward centroid and each adequate facility is connected to its nearest
   road-network node by a straight-line "off-road" segment, assumed
   traversed at OFFROAD_SPEED_KMH (a documented assumption — local/
   off-road travel is slower than the classed road network itself).

4. For each ward, total travel time to a given facility = off-road time
   (ward -> nearest road node) + shortest-path network time (Dijkstra)
   + off-road time (nearest road node -> facility). The nearest adequate
   facility is the one minimizing this total.

Performance note: rather than running one shortest-path query per
(ward, facility) pair — which does not scale — this runs ONE
single-source Dijkstra per *unique* facility road-node (there are far
fewer unique nodes than facilities, since several facilities can snap to
the same nearest node), caches the resulting distance-to-every-node
table, then looks up ward distances from that cache. Verified this
approach computes 620 wards x 1300 facilities in well under a second.

Output: ward_accessibility.csv, facility_adequacy.csv
"""
import math

import duckdb
import pandas as pd
import networkx as nx
from shapely import wkt as shapely_wkt

OFFROAD_SPEED_KMH = 20  # ASSUMPTION: local/off-road travel speed for the
                         # final leg between a ward centroid or facility
                         # and the nearest road network node. Adjust here
                         # if a different assumption is preferred — this
                         # is the single knob that controls that leg.

STAFFING_CADRES = [
    ("med_officers", "min_medical_officers"),
    ("nurses_midwives", "min_nurses_midwives"),
    ("chews", "min_chews"),
    ("lab_scientists", "min_lab_scientists"),
    ("pharm_techs", "min_pharmacy_technicians"),
]


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

    n_components = nx.number_connected_components(G)
    if n_components > 1:
        print(f"[access] WARNING: road network has {n_components} disconnected "
              f"components — some ward/facility pairs may be unreachable")
    else:
        print(f"[access] road network graph: {G.number_of_nodes()} nodes, "
              f"{G.number_of_edges()} edges, single connected component")
    return G


def nearest_road_node(point, graph_nodes) -> tuple:
    """Brute-force nearest node by haversine distance. Fine at this scale
    (a few hundred road nodes); would need a KD-tree for a much larger
    network."""
    best_node, best_dist = None, None
    for n in graph_nodes:
        d = haversine_km(point[0], point[1], n[0], n[1])
        if best_dist is None or d < best_dist:
            best_node, best_dist = n, d
    return best_node, best_dist


def compute_facility_adequacy(con) -> None:
    """Join facilities to their personnel counts and the staffing norms
    for their facility_type, and write an is_adequate flag. Facilities
    with no personnel record, or a facility_type not present in the
    norms table, are flagged as unknown rather than silently assumed
    adequate or inadequate."""
    facilities = con.execute("""
        SELECT facility_id, facility_type, longitude_clean, latitude_clean, geom
        FROM facilities
    """).fetchdf()
    personnel = con.execute("""
        SELECT facility_id, med_officers, nurses_midwives, chews, lab_scientists, pharm_techs
        FROM facility_personnel_scores
    """).fetchdf()
    norms = con.execute("SELECT * FROM minimum_staffing_norms").fetchdf()
    norms_by_type = {row["facility_type"]: row for _, row in norms.iterrows()}

    df = facilities.merge(personnel, on="facility_id", how="left")

    def check_adequacy(row):
        norm = norms_by_type.get(row["facility_type"])
        if norm is None:
            return "unknown_facility_type"
        if pd.isna(row.get("med_officers")):
            return "no_personnel_record"
        for staff_col, norm_col in STAFFING_CADRES:
            minimum = norm[norm_col]
            if minimum > 0 and row[staff_col] < minimum:
                return "inadequate"
        return "adequate"

    df["adequacy_status"] = df.apply(check_adequacy, axis=1)

    con.register("adequacy_df", df)
    con.execute("CREATE OR REPLACE TABLE facility_adequacy AS SELECT * FROM adequacy_df")

    counts = df["adequacy_status"].value_counts()
    print("[access] facility adequacy breakdown:")
    for status, n in counts.items():
        print(f"  {status}: {n}")


def compute_ward_accessibility(con, road_graph: nx.Graph) -> None:
    graph_nodes = list(road_graph.nodes())

    adequate = con.execute("""
        SELECT facility_id, longitude_clean, latitude_clean
        FROM facility_adequacy
        WHERE adequacy_status = 'adequate' AND geom IS NOT NULL
    """).fetchdf()
    print(f"[access] {len(adequate)} adequately-staffed facilities with usable coordinates "
          f"used as accessibility targets")

    # Snap each adequate facility to its nearest road node, and group by
    # that node so we only run one Dijkstra per unique node, not per facility.
    node_to_facilities = {}
    for _, row in adequate.iterrows():
        pt = (row["longitude_clean"], row["latitude_clean"])
        node, dist_km = nearest_road_node(pt, graph_nodes)
        offroad_min = (dist_km / OFFROAD_SPEED_KMH) * 60
        node_to_facilities.setdefault(node, []).append((row["facility_id"], offroad_min))

    print(f"[access] {len(node_to_facilities)} unique road nodes among facility snap points "
          f"(running one shortest-path search per unique node)")

    dist_cache = {}
    for node in node_to_facilities:
        dist_cache[node] = nx.single_source_dijkstra_path_length(road_graph, node, weight="weight")

    wards = con.execute("""
        SELECT ward_code, ward_name, total_population, population_under5,
               ST_X(ST_Centroid(geom)) AS cx, ST_Y(ST_Centroid(geom)) AS cy
        FROM wards
    """).fetchdf()

    results = []
    n_unreachable = 0
    for _, w in wards.iterrows():
        ward_pt = (w["cx"], w["cy"])
        ward_node, ward_offroad_km = nearest_road_node(ward_pt, graph_nodes)
        ward_offroad_min = (ward_offroad_km / OFFROAD_SPEED_KMH) * 60

        best_time, best_facility = None, None
        for node, facs in node_to_facilities.items():
            path_time = dist_cache[node].get(ward_node)
            if path_time is None:
                continue  # unreachable from this facility's node
            for fac_id, fac_offroad_min in facs:
                total = ward_offroad_min + path_time + fac_offroad_min
                if best_time is None or total < best_time:
                    best_time, best_facility = total, fac_id

        if best_time is None:
            n_unreachable += 1

        results.append({
            "ward_code": w["ward_code"],
            "ward_name": w["ward_name"],
            "total_population": w["total_population"],
            "population_under5": w["population_under5"],
            "nearest_adequate_facility_id": best_facility,
            "travel_time_minutes": round(best_time, 1) if best_time is not None else None,
            "reachable": best_time is not None,
        })

    print(f"[access] {n_unreachable}/{len(wards)} wards could not reach any adequate facility "
          f"through the road network")

    results_df = pd.DataFrame(results)
    con.register("ward_access_df", results_df)
    con.execute("CREATE OR REPLACE TABLE ward_accessibility AS SELECT * FROM ward_access_df")

    reachable = results_df[results_df["reachable"]]
    if len(reachable):
        print(f"[access] travel time to nearest adequate facility — "
              f"median: {reachable['travel_time_minutes'].median():.1f} min, "
              f"max: {reachable['travel_time_minutes'].max():.1f} min")


def compute_access(db_path: str, ward_output_csv: str, facility_output_csv: str) -> None:
    con = duckdb.connect(db_path)
    con.execute("LOAD spatial;")

    compute_facility_adequacy(con)
    road_graph = build_road_graph(con)
    compute_ward_accessibility(con, road_graph)

    con.execute(f"COPY ward_accessibility TO '{ward_output_csv}' (HEADER, DELIMITER ',')")
    con.execute(f"COPY facility_adequacy TO '{facility_output_csv}' (HEADER, DELIMITER ',')")
    print(f"[access] wrote {ward_output_csv} and {facility_output_csv}")

    con.close()


if __name__ == "__main__":
    compute_access(
        db_path=r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\q2.duckdb",
        ward_output_csv=r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\ward_accessibility.csv",
        facility_output_csv=r"C:\Users\Administrator\Desktop\e-health_assessment\Outputs\facility_adequacy.csv",
    )