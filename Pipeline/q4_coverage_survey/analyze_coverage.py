"""
Part 2, Question 4: Post-campaign coverage survey analysis under a
stratified two-stage cluster design.

Steps:
  1. De-duplicate: cluster C034 was found to have its entire household
     and child record block duplicated (20 households x 2, and their
     children x 2) — an exact-row duplication data entry error, not a
     real 40-household cluster. Dropped before any estimation.
  2. Compute design (base) weights: 1 / (stage1_prob * stage2_prob).
     Stage 2 probability uses the ACTUAL FIELD LISTING count
     (households_listed_fieldwork / stage2_households_listed), not the
     2023 census count, which was only the measure of size for stage 1
     PPS selection — using the census count for stage 2 would be wrong.
  3. Nonresponse-adjust weights within cluster. Vacant dwellings are
     excluded from the adjustment entirely (not an eligible household,
     not nonresponse). Refused and "no eligible respondent after 3
     visits" ARE treated as nonresponse (repeat-visit non-contact is
     nonresponse, not a legitimate ineligibility determination) and
     inflate the weight of completed households in the same cluster.
  4. Combine the card/caregiver-recall skip pattern into one
     dose_received indicator per the instrument's own rule: card seen
     -> use card value; card not seen -> use caregiver recall.
  5. Compute weighted coverage overall and by stratum, with a
     design-based standard error via the "ultimate cluster" linearized
     ratio variance method (standard for multistage cluster surveys).
"""
import numpy as np
import pandas as pd

DATA_DIR = "/mnt/user-data/uploads"


def load_and_dedupe():
    hh = pd.read_csv(f"{DATA_DIR}/household_records.csv")
    cr = pd.read_csv(f"{DATA_DIR}/child_records.csv")
    sf = pd.read_csv(f"{DATA_DIR}/sampling_frame.csv")

    n_hh_before, n_cr_before = len(hh), len(cr)
    hh = hh.drop_duplicates(keep="first").reset_index(drop=True)
    cr = cr.drop_duplicates(keep="first").reset_index(drop=True)
    print(f"[dedupe] household_records: {n_hh_before} -> {len(hh)} "
          f"({n_hh_before - len(hh)} exact duplicate rows dropped, all from cluster C034)")
    print(f"[dedupe] child_records: {n_cr_before} -> {len(cr)} "
          f"({n_cr_before - len(cr)} exact duplicate rows dropped)")

    return hh, cr, sf


def compute_weights(hh: pd.DataFrame, sf: pd.DataFrame) -> pd.DataFrame:
    selected = sf[sf["selected"] == 1][
        ["cluster_id", "stage1_selection_probability", "field_status"]
    ].drop_duplicates()

    hh = hh.merge(selected, on="cluster_id", how="left")
    missing_prob = hh["stage1_selection_probability"].isna().sum()
    if missing_prob:
        print(f"[weights] WARNING: {missing_prob} household rows have no matching "
              f"selected cluster in sampling_frame — check cluster_id consistency")

    # Stage 2 probability uses the field listing, not the 2023 census MOS.
    hh["stage2_prob"] = hh["stage2_households_selected"] / hh["stage2_households_listed"]
    hh["design_weight"] = 1.0 / (hh["stage1_selection_probability"] * hh["stage2_prob"])

    # Nonresponse adjustment, computed per cluster.
    # Vacant dwellings: excluded entirely (not an eligible household).
    eligible = hh[hh["result_of_visit"] != "Vacant dwelling"].copy()
    cluster_counts = eligible.groupby("cluster_id")["result_of_visit"].agg(
        n_completed=lambda s: (s == "Completed").sum(),
        n_eligible_total="count",
    )
    cluster_counts["nonresponse_adj"] = (
        cluster_counts["n_eligible_total"] / cluster_counts["n_completed"]
    )
    hh = hh.merge(cluster_counts[["nonresponse_adj"]], on="cluster_id", how="left")

    hh["final_weight"] = np.where(
        hh["result_of_visit"] == "Completed",
        hh["design_weight"] * hh["nonresponse_adj"],
        np.nan,  # non-completed, non-vacant households don't carry a
                 # child-level weight — they were never asked the roster
    )

    n_completed = (hh["result_of_visit"] == "Completed").sum()
    print(f"[weights] {n_completed} completed households weighted; "
          f"nonresponse adjustment range: "
          f"{hh.loc[hh['result_of_visit']=='Completed','nonresponse_adj'].min():.3f}"
          f"-{hh.loc[hh['result_of_visit']=='Completed','nonresponse_adj'].max():.3f}")

    return hh


def build_dose_indicator(cr: pd.DataFrame) -> pd.DataFrame:
    cr = cr.copy()
    cr["dose_received"] = np.where(
        cr["vaccination_card_seen"] == "Yes",
        cr["dose_recorded_on_card"],
        cr["dose_reported_by_caregiver"],
    )
    n_missing = cr["dose_received"].isna().sum()
    print(f"[dose] {n_missing}/{len(cr)} children have a missing dose_received value "
          f"despite the skip pattern rule (card/caregiver field was blank when expected) "
          f"— excluded from coverage numerator AND denominator, not counted as unvaccinated")
    return cr


def ultimate_cluster_variance(df: pd.DataFrame, value_col: str, weight_col: str,
                               cluster_col: str, stratum_col: str) -> tuple:
    """Design-based ratio estimate + linearized SE for a stratified
    multistage cluster sample, using the standard 'ultimate cluster'
    method: treat each first-stage cluster as the unit of variance
    estimation, regardless of further sub-sampling stages within it."""
    df = df.copy()
    df["_num"] = df[weight_col] * df[value_col]
    df["_den"] = df[weight_col]

    r_hat = df["_num"].sum() / df["_den"].sum()

    cluster_totals = df.groupby([stratum_col, cluster_col]).agg(
        num=("_num", "sum"), den=("_den", "sum")
    ).reset_index()

    variance = 0.0
    for stratum, g in cluster_totals.groupby(stratum_col):
        n_h = len(g)
        if n_h < 2:
            continue  # cannot estimate variance from a single cluster
        resid = g["num"] - r_hat * g["den"]
        variance += (n_h / (n_h - 1)) * (resid - resid.mean()).pow(2).sum()

    total_weight = df["_den"].sum()
    se = np.sqrt(variance) / total_weight
    return r_hat, se


def deff_and_ess(df: pd.DataFrame, value_col: str, weight_col: str,
                  cluster_col: str, stratum_col: str) -> tuple:
    r, se = ultimate_cluster_variance(df, value_col, weight_col, cluster_col, stratum_col)
    n = len(df)
    design_var = se ** 2
    srs_var = r * (1 - r) / n
    deff = design_var / srs_var
    ess = n / deff
    return r, se, deff, ess


def main():
    hh, cr, sf = load_and_dedupe()
    hh = compute_weights(hh, sf)
    cr = build_dose_indicator(cr)

    completed_hh = hh[hh["result_of_visit"] == "Completed"][
        ["household_id", "cluster_id", "stratum_code", "final_weight"]
    ]
    merged = cr.merge(completed_hh, on=["household_id", "cluster_id", "stratum_code"], how="inner")
    n_unmatched = len(cr) - len(merged)
    if n_unmatched:
        print(f"[merge] WARNING: {n_unmatched} child records could not be matched to a "
              f"completed household record — check for orphaned child rows")

    analysis = merged[merged["dose_received"].notna()].copy()
    analysis["dose_yes"] = (analysis["dose_received"] == "Yes").astype(int)

    print(f"\n[coverage] analysis sample: {len(analysis)} children with a valid weight "
          f"and non-missing dose status\n")

    overall_r, overall_se, overall_deff, overall_ess = deff_and_ess(
        analysis, "dose_yes", "final_weight", "cluster_id", "stratum_code"
    )
    print(f"OVERALL weighted coverage: {overall_r*100:.1f}% "
          f"(SE {overall_se*100:.2f} pp, 95% CI "
          f"{(overall_r-1.96*overall_se)*100:.1f}-{(overall_r+1.96*overall_se)*100:.1f}%, "
          f"DEFF={overall_deff:.2f}, ESS={overall_ess:.0f} of n={len(analysis)})")

    print("\nBy stratum:")
    for stratum, g in analysis.groupby("stratum_code"):
        r, se, deff, ess = deff_and_ess(g, "dose_yes", "final_weight", "cluster_id", "stratum_code")
        print(f"  {stratum}: {r*100:.1f}% (SE {se*100:.2f} pp, n={len(g)}, "
              f"95% CI {(r-1.96*se)*100:.1f}-{(r+1.96*se)*100:.1f}%, "
              f"DEFF={deff:.2f}, ESS={ess:.0f})")

    # unweighted for comparison, to show why weighting matters
    unweighted = analysis["dose_yes"].mean()
    print(f"\n[comparison] UNWEIGHTED coverage (naive, ignoring design): {unweighted*100:.1f}%")
    print(f"[comparison] design effect on point estimate: "
          f"{(overall_r - unweighted)*100:+.1f} percentage points")

    analysis.to_csv("/mnt/user-data/outputs/q4_analysis_dataset.csv", index=False)
    print("\nwrote q4_analysis_dataset.csv")


if __name__ == "__main__":
    main()
