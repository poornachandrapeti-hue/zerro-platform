# Foundation requirements

- Multi-organization isolation.
- Global unambiguous email login identity.
- Secure cookie sessions with CSRF and origin checks.
- Organization admin is separate from project roles.
- Role, project, company and discipline scope remain separate.
- Membership scope is ALL or explicitly SELECTED; missing scope is never unrestricted.
- Users and companies must belong to the correct organization; assignment companies must participate in the project.
- Only organization admins manage users and memberships initially.
- Personnel and accounts are separate concepts.
- Project codes unique ignoring case within an organization.
- Drafts require code/name only; activation requires client, lead PM, location, schedule and disciplines.
- Active requires actual start. Completed requires actual finish. Hold/cancellation require reasons.
- Prevent future actual dates and invalid finish/start ordering.
- PM creation synchronizes project membership; former PM access requires explicit review.
- Project updates use record versions.
- Units contain Areas, which contain Blocks.
- Audit changes and never record credentials.
- Commercial, personnel and business workflow details are out of phase-one scope.
