# SaathiMind - Youth Mental Wellness Prototype

SaathiMind is a working prototype for a confidential and empathetic youth mental wellness assistant focused on Indian students and young adults.

## What this prototype demonstrates

- Empathetic AI chat for stress, loneliness, exam anxiety, and stigma concerns.
- Safety screening that detects potential self-harm or crisis language and escalates with immediate helpline guidance.
- Daily mood check-in with practical micro-actions and culturally relevant suggestions.
- India-focused support directory (Tele-MANAS, Kiran, iCALL, and more).
- Counsellor booking flow with mode/language preferences and priority handling for high-risk text.
- Privacy-first UX: no login, no persistence, and clear confidentiality messaging.
- Optional Google Cloud Vertex AI integration with a no-credentials local fallback.
- Optional Gemini API key integration for direct model responses.

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

## Host on GitHub Pages

This repo now includes a workflow at `.github/workflows/deploy-pages.yml` that publishes the frontend to GitHub Pages on every push to `main`.

1. In GitHub, open your repository settings.
2. Go to `Settings -> Pages`.
3. Under `Build and deployment`, choose `Source: GitHub Actions`.
4. Push to `main` (or run the workflow manually from `Actions`).
5. Your site will be available at:
   - `https://sonugp2003.github.io/InnerveSaathiMind/`

Important:
- GitHub Pages hosts static files, and this frontend includes a browser fallback engine.
- Chat, safety prompts, check-in planning, and resources search work directly in-browser on your Pages URL.
- Deploying the backend is optional and gives API-backed behavior (and optional Vertex AI).

To connect the hosted frontend to a deployed backend:
1. Deploy this FastAPI backend to a service like Render, Railway, or Cloud Run.
2. Edit `frontend/env.js` and set:
   - `window.SAATHIMIND_API_BASE = 'https://your-backend-url';`
3. Commit and push again so GitHub Pages picks up the change.

If `frontend/env.js` keeps `window.SAATHIMIND_API_BASE = '';`, the app runs in browser-only mode and still works on:
- `https://sonugp2003.github.io/InnerveSaathiMind/`

## Deploy Backend on Render (One-Click)

This repo includes `render.yaml` so Render can auto-detect service settings.

1. Open Render and create a new `Blueprint` deployment.
2. Select this GitHub repository (`sonugp2003/InnerveSaathiMind`).
3. Render reads `render.yaml` and creates the API web service.
4. After deploy, copy your backend URL, for example:
   - `https://innervesaathimind-api.onrender.com`
5. Update `frontend/env.js`:
   - `window.SAATHIMIND_API_BASE = 'https://innervesaathimind-api.onrender.com';`
6. Commit and push to `main` so GitHub Pages points to the live backend.

API health check endpoint:
- `/api/health`

## Deploy Full App on Vercel

This repo now includes `vercel.json` to route all requests to FastAPI (`backend/main.py`).

1. Open your Vercel project:
   - `https://vercel.com/sonugp/saathi-mind/`
2. Import/connect this GitHub repo (`sonugp2003/InnerveSaathiMind`) if not connected yet.
3. In project settings, keep framework as `Other` and root directory as repository root.
4. Deploy from branch `main`.

After deploy, Vercel will serve:
- Frontend page at `/`
- Static assets at `/static/*`
- API routes at `/api/*`

Optional environment variables (only if you want Vertex AI mode):
- `USE_VERTEX_AI=true`
- `GOOGLE_CLOUD_PROJECT=...`
- `GOOGLE_CLOUD_LOCATION=asia-south1`
- `VERTEX_MODEL=gemini-2.5-flash`

Optional environment variables (if you want Gemini API key mode):
- `GEMINI_API_KEY=...`
- `GEMINI_MODEL=gemini-2.5-flash`

If both are configured, Vertex mode is preferred. If Vertex is unavailable, Gemini API key mode is used.

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

## Gemini API Key setup (optional)

If you want Gemini responses without Vertex setup:

1. Open `.env` (or your Vercel environment settings).
2. Set:
   - `GEMINI_API_KEY=your-key`
   - `GEMINI_MODEL=gemini-2.5-flash`
3. Keep `USE_VERTEX_AI=false` unless you also want Vertex.

The backend will call Gemini through the official Generative Language API and use local fallback if the key is missing or fails.

## Safety note

This prototype is not a medical device and does not diagnose conditions. It is a supportive first-touch tool and routes users to crisis help when risk signals are detected.

## Demo scenarios

1. Exam stress: "My exams are close and I cannot focus."
2. Stigma concern: "I feel weak talking about mental health in my family."
3. Crisis phrase test: "I feel like ending everything." (should trigger immediate help banner)
4. Mood check-in with low mood and high stressors.
5. Counsellor booking test with date/time and a brief concern.
