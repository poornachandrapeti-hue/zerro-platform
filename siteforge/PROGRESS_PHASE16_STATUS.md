# Phase 16 — guarded overall EPCC dashboard integration

- Reuses Engineering and Procurement approved milestone earnings via their existing source-validated API logic; does not recalculate from readiness counts.
- Uses approved Planning-weighted supervisor-verified Construction percentage, keeping reported and accepted measurements separate.
- Requires cross-stage scheme approval, complete full-project access, matching Planning publication, and approved source milestone policies. Missing evidence returns `overall_percent: null` with stage-specific errors.
- Adds a traceability table showing stage weight, earned value, policy version, and eligibility, using existing UI classes/colors.
- No project-stage earnings are written back to Engineering, Procurement, Quality or Construction.
- A scheme containing Commissioning remains unavailable until authoritative approved earning integration is built.

## Verification limits
- Targeted isolated tests can check calculations; staging PostgreSQL migrations, role-by-role HTTP integration, and full TypeScript production build must still be run.
- Reinspection final-state reconciliation and supersession of approved policies are not complete. Procurement may correctly remain N/A when inspection histories are ambiguous.
- The live dashboard can be incomplete. Historical cutoff snapshots and complete Progress RBAC are still outstanding.
