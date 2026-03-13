# SaathiMind - Youth Mental Wellness Prototype

SaathiMind is a working prototype for a confidential and empathetic youth mental wellness assistant focused on Indian students and young adults.

## What this prototype demonstrates

- Empathetic AI chat for stress, loneliness, exam anxiety, and stigma concerns.
- Safety screening that detects potential self-harm or crisis language and escalates with immediate helpline guidance.
- Daily mood check-in with practical micro-actions and culturally relevant suggestions.
- India-focused support directory (Tele-MANAS, Kiran, iCALL, and more).
- Privacy-first UX: no login, no persistence, and clear confidentiality messaging.
- Optional Google Cloud Vertex AI integration with a no-credentials local fallback.

## Tech stack

- FastAPI backend (Python)
- Static frontend (HTML, CSS, JavaScript)
- Optional: Google Cloud Vertex AI (Gemini model)

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy env template and update values if needed:
   ```bash
   copy .env.example .env
   ```
4. Run the app:
   ```bash
   uvicorn backend.main:app --reload
   ```
5. Open `http://127.0.0.1:8000`.

## Google Cloud setup (optional)

If you want real generative responses from Vertex AI:

1. Enable Vertex AI API in your Google Cloud project.
2. Authenticate locally with ADC:
   ```bash
   gcloud auth application-default login
   ```
3. Set in `.env`:
   - `USE_VERTEX_AI=true`
   - `GOOGLE_CLOUD_PROJECT=...`
   - `GOOGLE_CLOUD_LOCATION=asia-south1`

If any setting is missing or auth fails, the app automatically uses the local empathetic fallback engine.

## Safety note

This prototype is not a medical device and does not diagnose conditions. It is a supportive first-touch tool and routes users to crisis help when risk signals are detected.

## Demo scenarios

1. Exam stress: "My exams are close and I cannot focus."
2. Stigma concern: "I feel weak talking about mental health in my family."
3. Crisis phrase test: "I feel like ending everything." (should trigger immediate help banner)
4. Mood check-in with low mood and high stressors.
