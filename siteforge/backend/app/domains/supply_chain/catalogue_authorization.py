"""Centralized permission predicate for organization-wide catalogue review."""


def can_approve_catalogue(organization_admin: bool, role_permissions) -> bool:
    """Only organization admins or explicitly granted catalogue approvers qualify."""
    return bool(organization_admin or "procurement.catalogue.approve" in (role_permissions or ()))
