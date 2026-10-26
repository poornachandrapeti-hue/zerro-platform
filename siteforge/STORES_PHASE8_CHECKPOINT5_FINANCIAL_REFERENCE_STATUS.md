# Phase 8 Checkpoint 5 — Financials Reference Reconciliation

Implemented read-only project-scoped Stores financial reference review at:
`GET /api/projects/{pid}/stores/phase8/financial-reference-reconciliation`

Connects Stores material requests, issue handovers, posted-return references and explicit Contracts obligation links. It reports missing financial cost-code, valuation and contractual recovery authorization, and never invents amounts or invoices. Neither journal entries nor contractor deductions are created.

Current Financials models own cost codes, budgets, supplier invoice verification and finance contracts. Stores requests do not yet have an authoritative Finance allocation/cost-code or approved unit valuation reference; therefore all rows remain **Blocked** for financial posting and recovery, even when contract references exist.

**Remaining functionality:** create a reviewed explicit Stores-to-Finance cost attribution contract using existing Financials authority; integrate verified price/ownership/recovery terms, historical corrections, downstream Finance UI and separate Command Center runtime. Database/Docker tests deferred. Keep physical posting gates disabled.
