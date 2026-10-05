# Configuration

Run `make demo` for the default setup. Copy `.env.example` to `.env` when you need
different ports or options.

## Ports and data

The interface uses port 5173 and the API uses 8000. Set `WEB_PORT` and `API_PORT`
to change them. Both bind to localhost; PostgreSQL stays on the Docker network.

PostgreSQL, uploads and forecast artifacts use named Docker volumes. Restarting
with `make up` keeps them. The migration service runs before the API and worker.
Back up the database and artifact volume together to retain saved forecast results.

CSV previews expire after 24 hours. The worker removes expired uploads hourly.
Local scenario and decision history is retained.

## Read-only demo mode

Prepare the data with `make demo`, then set `APP_MODE=public_demo` and restart
with `make up`. Shared imports, stock edits, training and purchase decisions are
disabled. Visitors can run bounded simulations in separate browser sessions.

Simulations allow two active jobs globally and three submissions per minute per
session. The assistant allows ten messages per minute per session. Public results
and conversations expire after 24 hours. Keep `AI_ENABLED=false` in this mode.

For hosting, use HTTPS and a reverse proxy, keep the database private and replace
the development credentials. Configure forwarded headers for the trusted proxy.
Session limits do not replace authentication or protection against abusive traffic.

## Optional LLM provider

The offline assistant needs no key. To try the LLM provider locally, set
`OPENAI_API_KEY`, `OPENAI_MODEL` and `AI_ENABLED=true` in the backend configuration.
Usage is billed to the configured account. Keep the key out of Git and the frontend.

The provider can call at most four read tools per message. The default deadline is
20 seconds, configurable with `AI_TIMEOUT_SECONDS`. Provider failures fall back to
offline explanations. Public demo mode always uses the offline assistant.

## Troubleshooting

Use `docker compose ps` to check services and
`docker compose logs migrate api worker` for startup or job errors.
`/api/v1/jobs/{id}?dataset_id=...` exposes job status and a safe error message.

For browser tests on a different port, set `E2E_BASE_URL`, for example
`http://127.0.0.1:15173`, before running `npm run e2e` from `frontend`.
