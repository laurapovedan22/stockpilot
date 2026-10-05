# Third-party notices

Original StockPilot code: MIT, Laura Poveda Nicolás, 2026.

Optional data: Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning
Repository. https://doi.org/10.24432/C5CG6D. CC BY 4.0, as declared by the
[UCI source](https://archive.ics.uci.edu/dataset/502/online+retail+ii).
Attribution applies separately from the code license. Adapter outputs exclude
customer identifiers and non-merchandise codes, normalize columns and exclude
unconfirmed final local days. Operational stock/cost/supplier fields are synthetic.
No UCI workbook is bundled. Sample CSVs are fictional and contain no customer data.

Installed version and declared license metadata is recorded in
[docs/dependency-licenses.md](docs/dependency-licenses.md).
Upstream projects generally declare: FastAPI, Pydantic, SQLAlchemy, Alembic, React,
Vite, TanStack Query, Testing Library and Vitest (MIT); NumPy, pandas, scikit-learn
(BSD); XGBoost and Playwright (Apache-2.0); D3 (ISC); psycopg (LGPL); PostgreSQL
(PostgreSQL License). Consult the license files of resolved wheels/npm packages,
including binary/transitive libraries. This list is not a completed license audit.
The inventory comes from installed artifacts; it does not replace review of
binary/transitive license files or redistribution obligations for Docker images.
