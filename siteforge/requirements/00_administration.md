# Administration & Shared Services

## Scope and owner

Organization Administrator owns account/company/permission configuration. Domain administrators manage their own policy masters where granted. Organization admin status grants no automatic technical, financial, QA or HSE decision authority.

## Requirements

- ADM-001: Manage login users, active status, company and profile; unique normalized email; secure onboarding/password reset with expiry and token hashing. Preserve existing login/session/CSRF controls.
- ADM-002: Manage company types and activation; protect referenced company history and handle inactive-company assignments explicitly.
- ADM-003: Manage roles and granular permissions through audited grants; project memberships specify company and explicit discipline scope. No public arbitrary role escalation.
- ADM-004: Configure project hierarchy, approval routes, thresholds, delegated approvers and escalation recipients with effective dates and versions.
- ADM-005: Enforce last-active-administrator protection; deactivation revokes sessions and identifies outstanding responsibilities for reassignment.
- ADM-006: Supply discipline/UOM/currency/calendar/reason-code masters with archival instead of unsafe deletion.
- ADM-007: Provide policy validation and missing-configuration dashboard; technical domain rules need domain-authorized owners.
- ADM-008: Provide authorized audit search and filtered export with confidential fields excluded.
- ADM-009: Manage connector configuration/secret references and health, disabled until verified. Never expose secret values in UI/logs/exports.
- ADM-010: Provide durable job/outbox failure review, safe retry and reconciliation visibility with administrative permissions.
- ADM-011: Maintain email/template preferences and mandatory-critical alert rules; administration cannot change reviewer rights by changing recipients.
- ADM-012: Maintain backups/restore procedures, retention controls and operational environment documentation. Production deployment needs HTTPS, secure cookies and managed secrets.

## Screens

Users, companies, roles/permissions, project assignments, masters, workflow/alert policies, connector health, audit and job/reconciliation views. Domain-sensitive records are not visible merely because these menus are available.

## Acceptance

No default credential; wrong-organization assignment denied; last admin cannot be removed; revoked sessions fail; future permission seeds do not silently broaden current memberships; critical missing reviewer configuration is visible; audits exclude secrets; job replay remains idempotent.

See the other `00_` files for authoritative shared scope. Track ADM IDs individually in the coverage tracker.
