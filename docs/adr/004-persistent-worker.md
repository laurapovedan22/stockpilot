# ADR 004 — Persistent jobs

Decision: PostgreSQL queue, row locking, renewable leases, owner fencing, two total
attempts and transactional publication. Dataset advisory locks serialize mutations.
Reason: training should survive API restarts and expose durable result IDs.
Tradeoff: additional DB load and heartbeat transactions; orphan artifact cleanup is separate.
