# Part 2, Question 3: Converting a Paper Questionnaire into a Digital Form

All data in this pack is synthetic. No real settlement, household, enumerator or specimen
identifier appears in any file.

## What is here

**`Household_Questionnaire_HH2026v1.docx`** is the paper questionnaire, exactly as it was
approved and as it would be handed to you in practice. It is the thing you must digitise.
Read every page, including the notes on completion and the interviewer instructions.

**`reference_media/`** holds the external lookup files that exist alongside the questionnaire.
These are the files that would be attached to the form as media on ODK Central or KoboToolbox.

| File | Bytes | Rows |
|---|---|---|
| `lgas.csv` | 134 | 4 |
| `previous_round_households.csv` | 336,648 | 3,982 |
| `settlements.csv` | 217,606 | 2,524 |
| `settlements.geojson` | 712,368 | 2,530 |
| `specimen_label_allocation.csv` | 2,512 | 24 |
| `staff_roster.csv` | 6,634 | 120 |
| `wards.csv` | 1,077 | 40 |

## Notes

- The questionnaire is a paper instrument. It states coding categories and skip instructions,
  because paper forms do. It does not state permitted ranges, validation rules, cross-question
  consistency checks, or anything about devices, languages, or data protection, because paper
  forms do not. Supplying all of that is the task.
- The reference files are provided because the questionnaire refers to a settlement list, a
  medicine list, a staff roster and pre-printed specimen labels. Work out from the questionnaire
  which file serves which question.
- `specimen_label_allocation.csv` carries the label ranges issued to each team and the check
  digit scheme used on the pre-printed labels.
- Nothing in this folder tells you the operating conditions in the field. Those are in the
  question paper. They constrain your design more than the questionnaire does.

## Submission

Your form must convert without error. State the tool and version you validated with and include
the conversion output in your repository. A form that does not convert is not a form.
