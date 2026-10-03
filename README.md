# Audio Summarizer

Upload an audio file, get a transcript and a summary.

- Guest login using a cookie (no signup)
- Audio is stored in Supabase Storage, data in Supabase Postgres
- Speech to text with Gnani, summary with Groq
- Each file shows its progress: upload → transcribe → summarize

## Structure

```
frontend/   Next.js
backend/    FastAPI (uv)
```

## Running locally

**Backend**

```bash
cd backend
cp .env.example .env   # add your Supabase, Gnani and Groq keys
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Tables and the storage bucket are created automatically on startup.

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. API calls are proxied to the backend on port 8000.

## How it works

1. On page load you get a guest user id, saved in a cookie.
2. The browser uploads the file directly to Supabase using a signed URL, so the progress bar is real.
3. The backend sends the file to Gnani's batch STT API and polls until the transcript is ready.
4. The transcript is sent to Groq for a summary.
5. The frontend polls every few seconds and updates the status.

If something fails you can hit Retry. It picks up from the step that failed.

## Notes

- Max file size is 50 MB (Supabase free tier).
- I used Gnani's batch API because the normal one only takes audio up to 60 seconds.
- API docs are at http://localhost:8000/docs
