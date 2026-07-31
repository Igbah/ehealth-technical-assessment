Overview

This repository contains my submission for the eHealth Africa Senior Coordinator, Data and GIS Analytics technical assessment. It covers:

Part 1 — Q2: Facility readiness and geographic access analysis
Part 2 — Q4: Complex-survey inference for a coverage estimate
Part 3 — Q5 & Q6: Coordination response and capability-building plan (compulsory)

Raw data for all four Part 1/2 questions is retained under Data/ for completeness, but only Q2 and Q4 were answered in full, per the assessment's own-choice structure.

Repository structure
├── Data/                          # Raw input data, untouched — never edited by hand
│   ├── Part1_Q1_Campaign_Tracking/
│   ├── Part1_Q2_Facility_Access/     ← used
│   ├── Part2_Q3_ODK_Form_Design/
│   └── Part2_Q4_Coverage_Survey/     ← used
├── Pipeline/                      # Scripts, run in sequence from raw data to final outputs
├── Output/                        # Generated results (database, tables, figures)
├── Tables/                        # Final summary tables referenced in the written responses
├── Docs/                          # Methodology notes and written responses
├── AI_Use.md                      # Log of AI assistance used, disclosed per assessment instructions
├── requirements.txt                # Python dependencies
└── README.md                      # This file
Setup
bash
# 1. Clone the repository
git clone https://github.com/Igbah/ehealth-technical-assessment.git
cd ehealth-technical-assessment

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt
Reproducing the analysis

Each question's pipeline runs end-to-end from the raw files in Data/ to the final outputs in Output/ and Tables/, with no manual intervention required.

bash
python Pipeline/run_pipeline.py

This runs, in order:

Data cleaning and reconciliation
Load into the spatial database (DuckDB)
Analysis / accessibility computation
Output generation (maps, summary tables)

(Update this section with the exact script names/order as the pipeline is built out.)

Written responses

The full written answers for Q2 (methodology note), Q4 (report and judgement sections), Q5, and Q6 are in Docs/.

AI assistance disclosure

AI assistance was used during this submission, as permitted by the assessment instructions. A running, specific log of what was used and for what is maintained in AI_Use.md.

Notes on tools
Python (pandas, geopandas, DuckDB) for the reproducible pipeline
ArcGIS Pro used only for final cartographic layout of the Q2 map — not part of the automated pipeline, since it depends on a paid license the reviewer may not have. All analysis leading up to the map is in open-source Python/DuckDB.