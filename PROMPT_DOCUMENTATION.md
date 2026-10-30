# AI/API Prompt Documentation
**Provider:** Google Gemini Generative Language API (`generateContent`), called with Python `requests` in `ai_engine.py`.

**Purpose:** Generate short, cautious remarks from glucose, haemoglobin and cholesterol values.

**Prompt used:** “You are assisting a non-diagnostic health information prototype. Review only these blood-test values: glucose, haemoglobin and cholesterol. Give a brief cautious informational note. Do not diagnose disease or calculate a definitive probability. Explain that interpretation depends on units, fasting status, age, sex, history and laboratory reference ranges. Do not invent reference ranges. Recommend discussion with a qualified clinician. Do not repeat name, DOB or email. State that this is not medical advice.”

**Review approach:** Check generated text for unsupported claims, invented reference ranges, inappropriate certainty and relevance. The app does not treat generated output as a diagnosis.

**Security:** API key is read from `.env`; `.env` is excluded by `.gitignore`.
