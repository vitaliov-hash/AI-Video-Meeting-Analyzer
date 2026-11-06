# Future demonstration modes — agreed scope

This document records the separation between a short-lived, controlled teacher demonstration and a no-cost public showcase. Teacher Preview guardrails are implemented locally on `feature/teacher-live-guard`; they are **disabled, not deployed, and not tunnel-tested**. The public/static Showcase remains a separate build mode. Do not infer live readiness from a successful local build.

## Teacher Live Demo

- Use a separate Vercel Preview project/environment and the local Windows Python backend through a free temporary HTTPS tunnel. Do not put a provider key in Vercel or the browser.
- The backend mode is off by default. It requires a teacher password (20+ chars), an independent HMAC token secret (32+ chars), exact single HTTPS CORS origin, DeepSeek provider, loopback bind, and a separate database directory. Invalid configuration stops startup.
- All `/api/*` requests except login require a signed bearer token; preflight is handled through exact-origin CORS. Login is limited to 5 attempts per 15 minutes per client; authenticated API requests are limited to 120 per minute per client. No client address is logged.
- Exactly two new analysis attempts are allowed for the whole activation period. The SQLite counter is atomic and survives restarts; failed attempts consume a slot; duplicate cloud links bypass a new slot and analysis.
- Default lifetime is five days; config rejects durations over seven days. Lifetime starts once and is persisted. Tokens expire after at most eight hours or at session end. A local kill file immediately blocks new requests and pending jobs before they send a summary request.
- Uploads are capped at 100 MB maximum, recognized transcript at 8,000 characters, prompt at 32,000 UTF-8 bytes, and model output at 600 tokens. FFmpeg extraction has a 15-minute timeout; Whisper inference can take longer and is not forcibly interrupted while a native model call is running. The worker checks expiry/kill switch before AI summarization.
- Data and uploads are isolated under `.teacher-demo-data`, not the user's personal meeting database. `.env` stays local to the Windows backend. Kill switch: `python -m meeting_analyzer.teacher_demo --disable`.
- The background job writes phase/status to SQLite and the frontend polls it. A job can keep running while Windows, FastAPI, SQLite, network and tunnel stay up; this path has not been verified through a public tunnel. Process crashes do not preserve the in-flight worker; startup marks interrupted meetings failed.
- No tunnel, live backend, teacher Vercel project or live paid API request has been started. Activation and the actual presentation still require owner approval and a rights-cleared recording.

## Public Showcase

- Offer precomputed RU and EN examples only. This branch serves two synthetic examples from `static/demo-data.json`; no real recording-derived data is included.
- Make **zero paid-AI calls** from the public showcase.
- Do not expose public endpoints capable of starting transcription, cloud downloads, or AI analysis. Vercel's output is a fresh static-only directory; the build includes no Python backend or serverless functions and rejects `PUBLIC_API_BASE_URL` in Showcase mode.
- Serve only sanitized demonstration artifacts; exclude real recordings, private transcripts, credentials, local databases, and user-specific cloud links.
- Confirm that the deployed origin serves the interface and prepared examples and returns no analysis service for direct `/api/meetings` requests. Record this as a deployment check once the site is live.
- The initial static summary is explicitly labeled as a prepared fictional example, not a real AI answer. A separate editorial version and the synthetic transcript are available for comparison.
- `vercel.json` runs the guarded `--vercel` mode: production and all ordinary builds are Showcase. Only Vercel Preview plus `TEACHER_PREVIEW_BUILD=1` can build the Teacher Preview UI, and that build refuses an absent/non-HTTPS backend origin.

## Shared deployment requirements

The layout is a static frontend on Vercel and a separate Python/Faster-Whisper backend on the user's Windows PC for the short supervised teacher demo. Before activation, configure the exact preview origin and temporary tunnel URL, confirm the Vercel Preview build output, run an authorized smoke, and confirm a rights-cleared source recording. This $0 design is single-instance and temporary; it is not production hosting. Public Showcase remains static and has no reachable analysis backend.
