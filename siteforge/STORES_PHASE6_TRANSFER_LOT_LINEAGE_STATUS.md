# Phase 6 — Transfer lot lineage foundation (not physical posting)

## Implemented
- One transfer → one provisional source lot plan, with organization/project-scoped lookup and row locking.
- Source lot must be located in the transfer's source warehouse and match the Procurement item.
- The planned quantity must equal the fully received and undamaged transfer quantity.
- Provenance checks: posted inbound/outbound lot quantities, prior unposted transfer plans, full attribution of legacy stock postings, and current QA accepted quantity.
- Idempotent identical plan retry; conflicting plan requests rejected.
- New `stores_transfer_lot_lineage` table records future destination lot / paired stock posting references without pretending a goods-receipt lot has physically moved.
- Existing `/post-stock` remains HTTP 503 and all live inventory transfer posting stays disabled.

## Endpoint
`POST /api/projects/{pid}/stores/material-transfers/{transfer_id}/source-lot-plan`

Payload `{ "source_receipt_lot_id": 123, "quantity": "5.000", "evidence": "Physical count and batch certificate" }`.

## Outstanding for a real atomic transfer
1. An authoritative destination lot type with transfer provenance rather than a synthetic GRN, plus QA and downstream issue/return support for transfer lots.
2. Two matching posted ledger legs and provenance allocations, inserted and balance-updated in one PostgreSQL transaction, with idempotency and crash-safe retry.
3. All relevant stock writers (including legacy adjustments and reverse flows) must honor transfer-specific types and locks.
4. PostgreSQL migration/runtime/concurrency tests and inter-project ownership rules; none executed here.

**No transfer posting is active. This checkpoint is a safe schema and source-lot planning foundation, NOT full atomic transfer posting.**
