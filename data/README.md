# Data access

The analysis expects an Excel workbook named `mortality.xlsx` containing the sheets `model` and `Fact_Patient_Visits`.

Place the workbook at `data/raw/mortality.xlsx`, or pass another path with `--input`. Raw row-level data are excluded from Git by default so that a public repository does not accidentally publish sensitive or restricted records.

Before publishing the workbook separately, confirm its provenance, license, de-identification status, and whether the names and identifiers are synthetic. The repository outputs contain aggregate results only.

