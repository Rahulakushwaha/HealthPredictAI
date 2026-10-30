# HealthPredict AI
Patient blood-test record management assessment prototype using Python, Streamlit, SQLite and Google's Gemini REST API.

## Setup (Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `.env` and add your Gemini API key. Never upload `.env` or your key to GitHub.
Run:
```powershell
python -m streamlit run app.py
```

## Features
- Create, read, update and delete patient records.
- SQLite persistent storage and CSV export.
- Email, date, future-DOB and numeric-value validation.
- Duplicate email detection.
- Exact assessment dataset processing with a validation log for rejected/duplicate entries.
- External Gemini API call for cautious informational remarks.

## Assessment demonstration
Open **Test Data & Validation**, process the ten supplied rows, show the valid records and validation log. Then in **Patient Records**, edit one email to `gokul@infocare.com`, delete one record, and show the refreshed list. In **AI Health Remarks**, select a saved patient and generate remarks after configuring the API key.

The supplied test data lacks units, fasting status, sex, history and laboratory reference ranges. AI output is therefore explicitly non-diagnostic and should be reviewed by a qualified clinician. Do not use real patient information without appropriate consent, authorization and privacy safeguards.
