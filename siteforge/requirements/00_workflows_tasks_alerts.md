# Shared approvals, tasks, notifications and escalations

## Workflow engine

- Versioned policies keyed by project, module, record type, discipline, company, risk/amount thresholds and action. Submission captures policy version, business record version and eligible assigned reviewers.
- Support sequential stages and parallel reviewers. Each stage explicitly defines all-required or a configured quorum. Required technical, client, QA or HSE gates cannot be skipped to reach quorum.
- Workflow instance states: Submitted → In Review → Approved / Rejected / Returned / Cancelled. Returned records can be revised and resubmitted in a new review attempt. Business fulfillment uses a separate domain state.
- Reviewer actions include approve, reject, return, comment and permitted delegation. Reject/return/revoke require reasons. Signature evidence records actor identity, timestamp and reviewed revision; legal digital-signature services are a separate optional verified integration.
- Lock decisions against simultaneous approve/reject. The final reviewer calls the domain application interface; approval and the authorized domain transition commit atomically in the monolith or use a recoverable pending-application state with reconciliation.
- PendingApplication or integration failure must not appear as a completed business approval. Retry idempotently; expose remediation tasks.
- Material changes to quantity, amount, drawing revision, scope or recipient invalidate earlier affected approvals according to policy. Cosmetic edits need explicit classification, not user-selected bypass.

## Tasks

Task fields: project, module/source ID, title, owner, creator, priority, due date, reminder policy, status, linked dependencies, completion evidence and version. States: Open, In Progress, Blocked, Completed, Cancelled. Completion evidence is validated by the source module where required.

## Notifications

- MVP: in-app inbox and unread badge. Email is optional and enabled only with configured delivery settings. SMS, WhatsApp and push are later opt-in connectors.
- Trigger on assignment, submission, decision, return, imminent expiry, overdue task, blocked work, hold issue/release and integration failure. Notifications link to an authorized record and show minimal permitted information.
- Deduplicate by source event, recipient, channel and rule version. Store delivery status; retries cannot resend successful deliveries. Respect per-user preferences except explicitly defined critical mandatory alerts.
- Urgent safety/quality stop alerts go immediately to affected supervisors and function leads. Routine reminders can be grouped; use configured project timezone and working calendars.

## Escalation

Each policy sets due duration, warning offsets, overdue intervals, hierarchy recipients and maximum escalation level. Suggested configurable starting policy: one reminder before due, escalation at due breach, next-level escalation after one working day. Do not hardcode this across all modules. A safety emergency uses immediate escalation.

Escalation increases visibility; it does not grant approval rights or auto-approve an overdue request. Pause/resume SLAs only with a configured reason, actor and history. Missing/inactive recipients generate a configuration issue.

## Operations and acceptance

Implement background scheduling with durable jobs, outbox event publishing, retry/backoff, dead-letter review and administrative health view. Verify repeated jobs, simultaneous decisions, reassigned users, timezone boundaries, holidays, notification access checks and revoked permissions. All templates and routing policies need validation and audit history.
