# Future demonstration modes — agreed scope

This document records the separation between a short-lived, controlled teacher demonstration and a no-cost public showcase. The static Showcase implementation is present in this branch, but **it is not considered deployed until a Vercel URL is verified**. Teacher Live Demo is not implemented, deployed, or activated. Do not infer otherwise from this plan.

## Teacher Live Demo

- Present prepared results first; keep the saved RU/EN examples available without invoking AI.
- A protected live-analysis mode may be activated for a teacher demonstration window of **five days**, with **seven days as an absolute maximum from activation**.
- Enforce the expiry on the backend. At expiry, disable analysis endpoints server-side; hiding a frontend button is not a security control.
- Require authentication and authorize each request. Add per-account processing quotas, upload-size and duration limits, request throttling, and a hard provider-spend cap with a kill switch.
- Keep provider keys only in the backend secret manager. Log usage counters without transcripts, user URLs, or keys. Alert before the budget cap and fail closed at the cap.
- Define the activation timestamp, end timestamp, total processing quota, and spend ceiling before enabling the mode. Automatically deactivate at the earlier of the configured deadline or exhausted quota/budget.

## Public Showcase

- Offer precomputed RU and EN examples only. This branch serves two synthetic examples from `static/demo-data.json`; no real recording-derived data is included.
- Make **zero paid-AI calls** from the public showcase.
- Do not expose public endpoints capable of starting transcription, cloud downloads, or AI analysis. Vercel's output is a fresh static-only directory; the build includes no Python backend or serverless functions and rejects `PUBLIC_API_BASE_URL` in Showcase mode.
- Serve only sanitized demonstration artifacts; exclude real recordings, private transcripts, credentials, local databases, and user-specific cloud links.
- Confirm that the deployed origin serves the interface and prepared examples and returns no analysis service for direct `/api/meetings` requests. Record this as a deployment check once the site is live.
- The initial static summary is explicitly labeled as a prepared fictional example, not a real AI answer. A separate editorial version and the synthetic transcript are available for comparison.

## Shared deployment requirements

The planned layout remains a static frontend on Vercel and a separate Python/Faster-Whisper backend with durable storage. Before either live mode is exposed, implement backend authentication, per-user authorization, rate limits, upload and processing limits, spend controls, TLS, secret management, retention/deletion policy, backup/restore tests, and monitoring. SQLite plus an in-process worker remains a single-instance demo design; it is not a horizontally scaled production architecture.
