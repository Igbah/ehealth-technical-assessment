"""
Q4 Section 3: Data quality assessment using the fieldwork log and
household/child responses.

Run once child_records.csv, household_records.csv, fieldwork_log.csv,
and sampling_frame.csv are available at DATA_DIR.
"""
import numpy as np
import pandas as pd

DATA_DIR = r"C:\Users\Administrator\Desktop\e-health_assessment\Data\Part2_Q4_Coverage_Survey"


def interviewer_outliers():
    hh = pd.read_csv(f"{DATA_DIR}/household_records.csv").drop_duplicates()
    cr = pd.read_csv(f"{DATA_DIR}/child_records.csv").drop_duplicates()
    fw = pd.read_csv(f"{DATA_DIR}/fieldwork_log.csv")

    # dose indicator
    cr["dose_received"] = np.where(
        cr["vaccination_card_seen"] == "Yes", cr["dose_recorded_on_card"], cr["dose_reported_by_caregiver"]
    )
    cr["dose_yes"] = (cr["dose_received"] == "Yes").astype("float")

    completed = hh[hh["result_of_visit"] == "Completed"][["household_id", "interviewer_id"]]
    cr_i = cr.merge(completed, on="household_id", how="left")

    print("=== INTERVIEWER-LEVEL REPORTED COVERAGE (unweighted, raw signal) ===")
    interviewer_cov = cr_i.groupby("interviewer_id")["dose_yes"].agg(["mean", "count"])
    interviewer_cov["mean_pct"] = interviewer_cov["mean"] * 100
    overall_mean = cr_i["dose_yes"].mean()
    interviewer_cov["z"] = (
        (interviewer_cov["mean"] - overall_mean)
        / np.sqrt(overall_mean * (1 - overall_mean) / interviewer_cov["count"])
    )
    print(interviewer_cov.sort_values("z").to_string())
    outliers = interviewer_cov[interviewer_cov["z"].abs() > 2]
    print(f"\nInterviewers with |z| > 2 (coverage far from overall mean given their n): "
          f"{list(outliers.index)}")

    print("\n=== INTERVIEW DURATION BY INTERVIEWER (household-level) ===")
    dur = hh.groupby("interviewer_id")["interview_duration_min"].agg(["mean", "min", "max", "count"])
    print(dur.sort_values("mean").to_string())
    print(f"\nOverall median household duration: {hh['interview_duration_min'].median()} min")
    short = hh[hh["interview_duration_min"] < hh["interview_duration_min"].quantile(0.05)]
    print(f"Households in bottom 5th percentile of duration: {len(short)}, "
          f"interviewers involved: {sorted(short['interviewer_id'].unique())}")

    print("\n=== FIELDWORK LOG CROSS-CHECK ===")
    fw["completion_rate"] = fw["households_completed"] / fw["households_attempted"]
    print(fw.groupby("interviewer_id").agg(
        mean_completion_rate=("completion_rate", "mean"),
        mean_duration=("mean_interview_duration_min", "mean"),
        pct_spot_checked=("supervisor_spot_check", lambda s: (s == "Yes").mean() * 100),
        pct_gps_verified=("gps_verified", lambda s: (s == "Yes").mean() * 100),
    ).to_string())

    print("\n=== MISSINGNESS PATTERN ===")
    cr["missing_dose"] = cr["dose_received"].isna()
    print("Missingness by interviewer (via household link):")
    cr_i2 = cr[["household_id", "missing_dose"]].merge(completed, on="household_id", how="inner")
    miss_by_int = cr_i2.groupby("interviewer_id")["missing_dose"].mean() * 100
    print(miss_by_int.sort_values(ascending=False).to_string())


if __name__ == "__main__":
    interviewer_outliers()