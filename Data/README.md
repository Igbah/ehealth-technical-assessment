# eHealth Africa: Technical Assessment Data Pack
## Senior Coordinator, Data and GIS Analytics

### All data in this pack is synthetic

Every dataset here was generated for this assessment. No real settlement, health facility,
patient, survey respondent, interviewer, surveillance series, or campaign record appears in
any file. Place names, administrative units, and coordinates are invented. Nothing in this
pack may be cited as evidence about any real population or programme.

### What is here

| Folder | For | Approximate size |
|---|---|---|
| `Part1_Q1_Campaign_Tracking/` | Part 1, Question 1 | 58 MB |
| `Part1_Q2_Facility_Access/` | Part 1, Question 2 | 1 MB |
| `Part2_Q3_ODK_Form_Design/` | Part 2, Question 3 | 1 MB |
| `Part2_Q4_Coverage_Survey/` | Part 2, Question 4 | 0 MB |

### The Part 2 Question 3 survey document

The paper questionnaire you must convert is a Word document at:

    Part2_Q3_ODK_Form_Design/Household_Questionnaire_HH2026v1.docx

It is the primary input for that question. Open it before anything else in that folder.
The lookup files in `Part2_Q3_ODK_Form_Design/reference_media/` support it.

Part 3 of the assessment requires no data pack. It is a written and design task, and the
capability assessment findings it works from are given in the question paper itself.

Each folder contains its own `README.md` with a data dictionary. Read it before you start.

### Common conditions

1. Every dataset contains deliberate defects. Identifying, documenting, and handling them is
   part of what is being assessed. Silently dropping records you cannot explain will lose marks.
2. All spatial data is supplied in EPSG:4326. Distance, area, and buffer operations require a
   projected coordinate reference system. State which you chose and why.
3. Do not edit source files by hand. Where a task says the transformation must be automated,
   a manual fix is a failed answer even if the output is correct. This applies to the ODK
   reference media as much as to the spatial and survey data.
4. Where two files disagree, neither is automatically authoritative. Decide, and say why.
5. If a defect makes part of an analysis impossible, say so and explain what you would need.
   A well argued account of why a question cannot be answered from the data supplied will
   score better than a confident answer that ignores the obstacle.

### Reproducibility

Your submitted code must run from these files as supplied, in this folder structure, to your
final outputs. Do not rename or restructure the pack.
