
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project folder
load_dotenv(Path(__file__).resolve().parent / ".env")


def api_is_configured():
    return bool(os.getenv("GEMINI_API_KEY"))


def generate_health_remarks(p):
    key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    if not key:
        raise RuntimeError(
            "Gemini API key is missing. Please configure your .env file."
        )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:generateContent"
    )

    prompt = f"""
    You are assisting a non-diagnostic health information prototype.

    Review these blood-test values:
    Glucose: {p['glucose']}
    Haemoglobin: {p['haemoglobin']}
    Cholesterol: {p['cholesterol']}

    Write a brief, cautious informational summary.

    Requirements:
    - Do not diagnose any disease.
    - Do not calculate disease probabilities.
    - Do not invent laboratory reference ranges.
    - Explain that interpretation depends on units, fasting
      status, age, sex, medical history and laboratory ranges.
    - Recommend discussing results with a qualified clinician.
    - Do not repeat patient name, DOB or email.
    - State that this is not medical advice.
    """

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 200
        }
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": key
    }

    retry_delays = [3, 8, 15]

    for attempt in range(4):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=(15, 90)
            )

            # Retry temporary server and rate-limit errors
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < 3:
                    time.sleep(retry_delays[attempt])
                    continue

                raise RuntimeError(
                    f"Gemini service is temporarily unavailable "
                    f"(HTTP {response.status_code}). "
                    "Please try again later."
                )

            if response.status_code >= 400:
                raise RuntimeError(
                    f"Gemini API HTTP {response.status_code}: "
                    f"{response.text[:500]}"
                )

            data = response.json()

            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError(
                    "Gemini returned no response. Please try again."
                )

            parts = candidates[0].get("content", {}).get("parts", [])
            result = " ".join(
                part.get("text", "") for part in parts
            ).strip()

            if not result:
                raise RuntimeError(
                    "Gemini returned an empty response."
                )

            return result

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as error:

            if attempt == 3:
                raise RuntimeError(
                    "Gemini request timed out after multiple attempts. "
                    "Check your internet connection and try again later."
                ) from error

            time.sleep(retry_delays[attempt])

    raise RuntimeError("Unable to generate AI remarks.")
