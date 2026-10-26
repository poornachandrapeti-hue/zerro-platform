# Phase 4 — reservation aggregate-balance fail-closed gate

Added the same validated aggregate-balance prerequisite already used for atomic lot acceptance to the lot reservation path, after the stock row lock and before computing availability or writing a reservation. Rejects negative/non-finite on-hand or reserved quantities and aggregate reservations exceeding on-hand.

This is an application guard, not completed live PostgreSQL concurrency validation. Lot reservation and issuing feature flags remain unchanged and disabled by default. The one existing ledger remains authoritative.
