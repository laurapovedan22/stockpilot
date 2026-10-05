# Running and deployment preparation

No deployment has been performed or authorized. Compose is intended for a local
single-user installation, with loopback web/API ports and no default DB exposure.
`make up` preserves data. No normal command deletes volumes.

Before public hosting, review the limitations in the README and methodology. Both
lockfiles are generated; pin resolved image digests as needed, run migrations on a
dedicated database and review the actual hosting network/security configuration.
Local isolation, concurrent rate-limit/expiry tests and desktop/mobile browser checks
have passed; they do not establish security for a future hosting configuration.

## Local data lifecycle

PostgreSQL uses a named volume. API/worker share upload and artifact volumes. A one-shot
service applies migration 0001 before both start. The synthetic seed command is
explicit and idempotent. `make demo` waits for a queued forecast, with a 600-second
timeout and terminal failure reporting.

Preview files expire in 24 hours. Worker maintenance runs hourly and removes expired
files under the configured upload directory, public scenarios/daily rows, public
conversations/messages and terminal public jobs. Local scenario history is retained.
Expired public resources are unavailable immediately, even before cleanup. Expired
queued or abandoned jobs are failed by the queue; cleanup skips conversations currently
locked by requests. The assistant's ten-per-minute limit is atomic across datasets.
Import report rows are sampled; actual confirmation reads and revalidates the same
checksum-verified file. Missing/expired previews require a new preview.

## Optional public demo configuration

`API_PORT` and `WEB_PORT` configure loopback host ports (defaults 8000/5173).
An isolated source-export installation was verified with fresh volumes on 18000/15173;
see [the recorded procedure](evidence/clean-install.md). Browser checks can use
`E2E_BASE_URL` to target another local installation.

Seed and prepare resources in local mode first, then restart with `APP_MODE=public_demo`.
Keep `AI_ENABLED=false`. Confirm direct API calls cannot import, edit inventory, train
or record decisions. Simulations use owner-scoped random cookie hashes, bounded inputs,
two active jobs globally and three submissions per minute/session. Users can establish
new sessions; production anti-abuse/authentication is outside this local prototype.

Use HTTPS, a controlled reverse proxy, a private database and restricted network
access. Configure forwarded headers only for the actual trusted proxy, including
HTTPS detection for Secure cookies. Do not simply expose local Compose ports and
development DB credentials. This project has no enterprise or multi-user authentication.

## Optional model provider

For local experiments only, set a backend-only `OPENAI_API_KEY`, a currently available
`OPENAI_MODEL` and `AI_ENABLED=true`. No key is required for CI or offline explanations.
The provider uses bounded Responses API coordination, at most four total read-tool
calls and a configurable total deadline (default 20 seconds).
Any experiment consumes the account's paid quota; no external LLM evaluation was run.
Public mode never invokes this provider.

## Preparing GitHub

Review the files selected by Git before publishing. Local notes, credentials,
original datasets and generated artifacts are excluded by `.gitignore`.

```sh
git status
git add README.md AGENTS.md LICENSE THIRD_PARTY_NOTICES.md .gitignore .env.example \
  compose.yaml Makefile backend frontend data/sample data/synthetic docs scripts .github
git commit -m "Implement StockPilot inventory planning demo"
git remote add origin YOUR_REAL_REPOSITORY_URL
git push -u origin main
```

Check the current branch name before pushing; rename deliberately if needed.
Never add `.env`, raw UCI files, model artifacts, uploads or caches.
