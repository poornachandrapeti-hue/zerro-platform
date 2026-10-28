from sqlalchemy.orm.attributes import flag_modified

from .models import Discipline, Role

# Assigned by an administrator per user and per project through a project membership.
DRAWING_DELETION_ROLE = "Drawing Deletion Authority"

GRANTS = {
    DRAWING_DELETION_ROLE: ["projects.view", "drawings.view", "engineering.drawings.delete"],
    "Project Manager": [
        "projects.view",
        "projects.edit",
        "projects.contact.view",
        "projects.contact.edit",
        "projects.manage_areas",
        "construction.view",
        "planning.view",
        "planning.manage",
        "projects.documents.upload",
        "projects.documents.delete",
        "drawings.view",
        "procurement.view",
        "procurement.commercial.view",
        "quality.view",
        "hse.view",
        "hr.view",
        "manpower.view",
        "financials.view", "contracts.view_summary", "contracts.approve",
    ],
    "Commercial Manager": [
        "projects.view",
        "projects.commercial.view",
        "projects.commercial.edit",
        "procurement.view",
        "procurement.commercial.view",
        "financials.view", "financials.manage", "contracts.view_summary", "contracts.view_commercial",
    ],
    "Finance Manager": [
        "projects.view",
        "projects.commercial.view",
        "procurement.view",
        "procurement.commercial.view",
        "financials.view", "financials.manage", "financials.approve",
    ],
    "Contract Manager": [
        "projects.view", "projects.commercial.view", "projects.commercial.edit",
        "contracts.view_summary", "contracts.view_commercial", "contracts.manage_draft",
        "contracts.manage_terms", "contracts.manage_obligations", "contracts.manage_variations",
        "contracts.manage_sharing", "contracts.approve", "contracts.sign", "contracts.activate",
    ],
}

ROLE_NAMES = [
    "Project Manager",
    "HR",
    "Discipline Head",
    "Planning",
    "Planning Head",
    "Planning Engineer",
    "Contractor Planner",
    "Equipment Manager",
    "Site Engineer",
    "QA/QC",
    "HSE",
    "Client/PMC Reviewer",
    "Viewer",
    "Engineering Engineer",
    "Document Controller",
    "Procurement Manager",
    "Procurement Officer",
    "Stores Officer",
    "Commercial Manager",
    "Finance Manager",
    "Finance Officer",
    "Billing Engineer",
    "Construction Manager",
    "Supervisor",
    "Commissioning Manager",
    "System Engineer",
    "Contract Manager",
    "Manpower Coordinator",
    "Equipment Coordinator",
    DRAWING_DELETION_ROLE,
]


def default_permissions(name):
    if name in GRANTS:
        extras = {"Project Manager": ["stores.requests.view", "stores.requests.review","stores.quality_handoff.approve"]}
        return list(dict.fromkeys([*GRANTS[name], *extras.get(name, [])]))
    permissions = ["projects.view"]
    if name == "Finance Officer":
        permissions += ["financials.view", "financials.manage"]
    elif name == "Billing Engineer":
        permissions += ["financials.view"]
    if name == "Engineering Engineer":
        permissions += ["drawings.view", "drawings.edit", "quality.view"]
    elif name == "Discipline Head":
        permissions += [
            "drawings.view",
            "drawings.edit",
            "drawings.review",
            "drawings.release",
        ]
    elif name == "Client/PMC Reviewer":
        permissions += ["drawings.view", "drawings.client_review", "quality.view", "hse.view"]
    elif name == "Document Controller":
        permissions += ["drawings.view", "drawings.edit", "transmittals.issue", "quality.view"]
    elif name == "Site Engineer":
        permissions += [
            "drawings.view",
            "procurement.view",
            "procurement.requirement.edit",
            "construction.view",
            "construction.edit",
            "quality.view",
            "quality.edit",
            "hse.view",
            "hse.edit",
        ]
    elif name == "Contractor Planner":
        permissions += ["planning.partner.view"]
    elif name == "Planning Head":
        permissions += ["planning.view", "planning.manage"]
    elif name == "Planning Engineer":
        permissions += ["planning.view", "planning.manage"]
    elif name == "Planning":
        permissions += ["drawings.view", "drawings.plan", "procurement.view", "construction.view", "quality.view", "planning.view", "planning.manage"]
    elif name == "Construction Manager":
        permissions += ["drawings.view", "construction.view", "construction.edit", "quality.view", "quality.edit", "hse.view"]
    elif name == "Supervisor":
        permissions += ["construction.view", "quality.view", "hse.view", "hse.edit"]
    elif name == "HSE":
        permissions += ["hse.view", "hse.plan"]
    elif name == "QA/QC":
        permissions += ["procurement.view", "quality.view", "quality.plan", "hse.view","stores.quality_handoff.approve"]
    elif name == "Procurement Officer":
        permissions += ["procurement.view", "procurement.requisition.edit", "procurement.rfq.edit", "procurement.po.edit", "procurement.receipt.edit", "procurement.invoice.edit", "quality.view"]
    elif name == "Procurement Manager":
        permissions += [
            "procurement.view",
            "procurement.requisition.edit",
            "procurement.requisition.review",
            "procurement.master.edit",
            "procurement.commercial.view",
            "procurement.rfq.edit",
            "procurement.po.edit",
            "procurement.receipt.edit",
            "procurement.stock.edit",
            "procurement.invoice.edit",
        ]
    elif name == "Stores Officer":
        permissions += ["procurement.view", "procurement.receipt.edit", "procurement.stock.edit", "quality.view"]
    if name == "Discipline Head":
        permissions += ["planning.view"]
        permissions += [
            "procurement.view",
            "procurement.requirement.edit",
            "procurement.requirement.review",
            "procurement.requisition.review",
            "procurement.quotation.technical",
            "construction.view",
            "quality.view",
            "hse.view",
        ]
    if name == "HR":
        permissions += ["hr.view", "hr.edit", "hr.restricted", "hr.request"]
    elif name in (
        "Discipline Head",
        "Planning",
    "Planning Head",
    "Planning Engineer",
    "Contractor Planner",
    "Equipment Manager",
        "Site Engineer",
        "QA/QC",
        "HSE",
        "Construction Manager",
        "Supervisor",
        "Manpower Coordinator",
    ):
        permissions += ["hr.view"]
    if name in ("Discipline Head", "Planning", "Site Engineer", "Construction Manager", "Supervisor"):
        permissions += ["hr.request"]
    if name in ("HR", "Site Engineer", "Construction Manager", "Supervisor", "Manpower Coordinator"):
        permissions += ["hr.attendance"]
    if name in (
        "HR",
        "Discipline Head",
        "Planning",
    "Planning Head",
    "Planning Engineer",
    "Contractor Planner",
    "Equipment Manager",
        "Site Engineer",
        "QA/QC",
        "HSE",
        "Construction Manager",
        "Supervisor",
        "Manpower Coordinator",
    ):
        permissions += ["manpower.view"]
    if name in ("Discipline Head", "Planning", "Site Engineer", "Construction Manager", "Supervisor", "Manpower Coordinator"):
        permissions += ["manpower.demand"]
    if name in ("HR", "Manpower Coordinator"):
        permissions += ["manpower.coordinate"]
    if name in ("Manpower Coordinator", "Supervisor", "Construction Manager", "Site Engineer"):
        permissions += ["manpower.allocate"]
    if name in ("Manpower Coordinator", "Supervisor", "Site Engineer"):
        permissions += ["manpower.returns"]
    # Dedicated Stores request permissions. Procurement PO/requirement rights are not inherited.
    stores_grants = {
        "Stores Officer": ["stores.requests.view", "stores.requests.allocate"],
        "Procurement Manager": ["stores.requests.view"],
        "Site Engineer": ["stores.requests.view", "stores.requests.create"],
        "Construction Manager": ["stores.requests.view", "stores.requests.create", "stores.requests.review"],
        "Discipline Head": ["stores.requests.view", "stores.requests.review"],
        "Project Manager": ["stores.requests.view", "stores.requests.review"],
        "Planning Head": ["stores.requests.view"],
        "Planning Engineer": ["stores.requests.view"],
    }
    permissions.extend(stores_grants.get(name, []))
    return permissions


def grant_role_permissions(db):
    for name in list(dict.fromkeys([*ROLE_NAMES, *GRANTS.keys()])):
        role = db.query(Role).filter_by(name=name).first()
        if not role:
            continue
        merged = list(role.permissions or [])
        changed = False
        for permission in default_permissions(name):
            if permission not in merged:
                merged.append(permission)
                changed = True
        if changed:
            role.permissions = merged
            flag_modified(role, "permissions")
    for name, permissions in GRANTS.items():
        role = db.query(Role).filter_by(name=name).first()
        if not role:
            continue
        merged = list(role.permissions or [])
        changed = False
        for permission in permissions:
            if permission not in merged:
                merged.append(permission)
                changed = True
        if changed:
            role.permissions = merged
            flag_modified(role, "permissions")


def seed(db):
    for name in ["Civil", "Mechanical", "Electrical", "Instrumentation", "Piping"]:
        if not db.query(Discipline).filter_by(name=name).first():
            db.add(Discipline(name=name))
    for name in ROLE_NAMES:
        if not db.query(Role).filter_by(name=name).first():
            db.add(Role(name=name, permissions=default_permissions(name)))
    db.flush()
    grant_role_permissions(db)
    db.flush()
