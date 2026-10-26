# Phase 6 — transfer destination-lot provenance

Implemented: same-project destination-lot provenance planning, uniquely linked to a planned source receipt lot, exact quantity and destination warehouse, with audit, duplicate protection and custody checks.

Not implemented: atomic balanced source/destination posting, QA authorization/release for transfer-derived lots, inter-project destination planning, physical availability and backend database migration validation. The stock posting endpoint continues to fail closed with 503; do not enable transfer posting.

Next: implement a transfer-specific stock posting kind with debit and credit in one transaction; add QA release binding and coverage accounting for transfer-derived destination lots; validate against PostgreSQL before activation.
