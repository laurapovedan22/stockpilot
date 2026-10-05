# Clean source installation, 5 October 2026

An export of 145 files returned by `git ls-files --cached --others --exclude-standard`
was copied into `.verification/clean-20261005`. The ignored verification directory
contained no `.env`, raw UCI workbook, models, node_modules or Python environment.
This check preceded the repository's first commit, so it used a source export
rather than a Git clone. Backend source hashes were compared at the initial
verification build: zero differences. The later dashboard expiry filter was verified
with a PostgreSQL regression and deployed to the main installation.
Docker images and dependency layers were cached on this computer.

From that directory, PowerShell commands actually executed:

```powershell
$env:API_PORT='18000'
$env:WEB_PORT='15173'
docker compose -p stockpilot-verification-20261005 up --build -d
docker compose -p stockpilot-verification-20261005 exec api python -m stockpilot.cli demo
docker compose -p stockpilot-verification-20261005 exec api python -m stockpilot.cli demo
```

Fresh PostgreSQL/artifact/upload volumes were created. Migration 0001 succeeded,
API became healthy, and worker completed synthetic training and replenishment.
Both demo calls returned the same resources:

- Dataset: `6d5f77f3-050f-5342-b717-028f2bfd8f00`
- Forecast: `a2b29755-bb2a-4034-9dce-15a69acdd84c`
- Recommendation: `c5eb614d-8f67-4bbc-9330-891a8f231983`

The actual forecast manifest is [clean-install-forecast.json](clean-install-forecast.json).
Desktop/mobile screenshots: [dashboard](clean-install-desktop.png),
[scenario](clean-install-mobile.png). Both were inspected visually.

From the main workspace's installed frontend test environment:

```powershell
$env:E2E_BASE_URL='http://127.0.0.1:15173'
npm run e2e
```

Four checks passed: desktop/mobile main flows and axe checks across eight pages per
viewport. The two optional historical checks skipped because UCI was not installed
in this fresh synthetic-only instance. No browser exceptions or root horizontal
overflow were detected in the main flow. Automated axe checks are limited evidence,
not complete accessibility certification. The temporary Compose services are stopped
after verification; their volumes are preserved. The main installation uses 5173/8000.
