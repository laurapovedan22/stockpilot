# ADR 001 — Modular monolith

Decision: one FastAPI application, one shared PostgreSQL schema and a separate
worker process from the same image. Domain calculations do not import HTTP code.
Reason: sufficient for the 20-product planning scope and reviewable by one developer.
Tradeoff: the DB is a shared dependency; module boundaries require discipline.
