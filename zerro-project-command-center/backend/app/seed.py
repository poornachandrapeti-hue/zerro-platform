from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .models import Contractor, Discipline, Milestone, Project, Risk, SubTask, WorkPackage


SAMPLE_SUB_TASKS: dict[str, list[tuple[str, str, str, str, str, str]]] = {
    # package name contains key → tasks: code, name, owner, weight, planned, actual
    "piping fabrication": [
        ("PF-01", "Material cutting & beveling", "Yard Supervisor", "20", "95", "90"),
        ("PF-02", "Fit-up & tack welding", "Piping Foreman", "25", "90", "85"),
        ("PF-03", "Root & fill welding", "Welding Lead", "30", "85", "80"),
        ("PF-04", "NDT & dimensional check", "QA/QC", "25", "80", "75"),
    ],
    "piping erection": [
        ("PE-01", "Spool transportation", "Logistics", "15", "80", "70"),
        ("PE-02", "Pipe rack erection", "Erection Lead", "35", "75", "60"),
        ("PE-03", "Tie-in joints", "Piping Foreman", "30", "70", "55"),
        ("PE-04", "Support & alignment", "Site Engineer", "20", "78", "68"),
    ],
    "welding": [
        ("WLD-01", "WPS & welder qualification", "Welding Engineer", "20", "100", "100"),
        ("WLD-02", "Production welding", "Welding Lead", "45", "78", "72"),
        ("WLD-03", "RT / UT inspection", "NDT Agency", "20", "75", "70"),
        ("WLD-04", "Repair & rework", "QA/QC", "15", "70", "65"),
    ],
    "equipment erection": [
        ("EQ-01", "Foundation readiness", "Civil Coord", "20", "90", "85"),
        ("EQ-02", "Equipment setting", "Mechanical Lead", "40", "70", "65"),
        ("EQ-03", "Grouting & alignment", "Millwright", "25", "65", "60"),
        ("EQ-04", "Nozzle & piping connect", "Piping Foreman", "15", "60", "55"),
    ],
    "cable": [
        ("CB-01", "Tray / trench readiness", "Electrical Foreman", "20", "80", "75"),
        ("CB-02", "Cable pulling", "Cable Crew", "40", "65", "60"),
        ("CB-03", "Glanding & dressing", "Technician", "20", "55", "50"),
        ("CB-04", "Megger & continuity", "Testing Engineer", "20", "45", "40"),
    ],
    "foundation": [
        ("FD-01", "Excavation & PCC", "Civil Foreman", "25", "100", "100"),
        ("FD-02", "Rebar & formwork", "Bar Bender Lead", "30", "90", "82"),
        ("FD-03", "Concreting", "Site Engineer", "30", "85", "75"),
        ("FD-04", "Curing & handover", "QA/QC", "15", "80", "70"),
    ],
}


def _match_tasks(package_name: str) -> list[tuple[str, str, str, str, str, str]]:
    lowered = package_name.lower()
    for key, tasks in SAMPLE_SUB_TASKS.items():
        if key in lowered:
            return tasks
    return [
        ("ST-01", "Mobilization & permits", "Supervisor", "20", "80", "70"),
        ("ST-02", "Main execution", "Discipline Lead", "50", "60", "55"),
        ("ST-03", "Inspection & punch list", "QA/QC", "20", "40", "35"),
        ("ST-04", "Close-out documents", "Document Controller", "10", "20", "15"),
    ]


def seed_sub_tasks_for_packages(db: Session, packages: list[WorkPackage]) -> None:
    for package in packages:
        if package.sub_tasks:
            continue
        for code, name, owner, weight, planned, actual in _match_tasks(package.name):
            db.add(
                SubTask(
                    work_package_id=package.id,
                    code=code,
                    name=name,
                    owner=owner,
                    weight=Decimal(weight),
                    planned_progress=Decimal(planned),
                    actual_progress=Decimal(actual),
                    status="On Track" if Decimal(actual) >= Decimal(planned) - Decimal("5") else "At Risk",
                    start_date=package.start_date,
                    target_date=package.target_date,
                    notes="",
                )
            )


def ensure_sub_tasks(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(SubTask)):
        return
    packages = db.scalars(select(WorkPackage).options(selectinload(WorkPackage.sub_tasks))).all()
    seed_sub_tasks_for_packages(db, list(packages))
    db.commit()


def seed_database(db: Session) -> None:
    if db.scalar(select(Project.id).limit(1)):
        ensure_sub_tasks(db)
        return

    contractors = {
        "LNT": Contractor(code="LNT", name="Larsen & Toubro Construction", contact_name="R. Kumar", phone="+91 90000 10001"),
        "KEC": Contractor(code="KEC", name="KEC International", contact_name="S. Rao", phone="+91 90000 10002"),
        "TCE": Contractor(code="TCE", name="Tata Consulting Engineers", contact_name="A. Dutta", phone="+91 90000 10003"),
        "VOL": Contractor(code="VOL", name="Voltas Projects", contact_name="P. Nair", phone="+91 90000 10004"),
    }
    db.add_all(contractors.values())

    project = Project(
        code="NRP-RPTU-01", name="Numaligarh Refinery Expansion", client="NRL", location="Assam, India",
        start_date=date(2025, 1, 15), planned_finish=date(2026, 12, 30), forecast_finish=date(2027, 1, 18),
        approved_budget=Decimal("2150000000"), currency="INR", status="At Risk",
    )
    db.add(project)
    db.flush()

    discipline_specs = [
        ("MECHANICAL", "Mechanical", "42", "78", "69", "920000000", date(2026, 11, 15)),
        ("ELECTRICAL", "Electrical", "25", "62", "65", "510000000", date(2026, 12, 5)),
        ("CIVIL", "Civil", "33", "86", "81", "720000000", date(2026, 10, 20)),
    ]
    disciplines: dict[str, Discipline] = {}
    for code, name, weight, planned, actual, budget, target in discipline_specs:
        item = Discipline(project_id=project.id, code=code, name=name, weight=Decimal(weight), planned_progress=Decimal(planned), actual_progress=Decimal(actual), budget=Decimal(budget), target_date=target)
        db.add(item)
        db.flush()
        disciplines[code] = item

    packages = [
        ("MECH-PIP-FAB", "Piping Fabrication", "Fabrication Yard", "MECHANICAL", "LNT", "24", "88", "82", "240000000", "212000000", "198000000", date(2025, 3, 1), date(2026, 9, 30), "At Risk"),
        ("MECH-PIP-ERE", "Piping Erection", "Process Unit", "MECHANICAL", "LNT", "28", "76", "64", "310000000", "292000000", "238000000", date(2025, 7, 1), date(2026, 11, 15), "Delayed"),
        ("MECH-EQP-ERE", "Equipment Erection", "Unit 30", "MECHANICAL", "TCE", "22", "71", "68", "190000000", "174000000", "151000000", date(2025, 8, 10), date(2026, 10, 22), "At Risk"),
        ("MECH-NDT", "Welding and NDT", "All Areas", "MECHANICAL", "TCE", "16", "80", "74", "110000000", "98000000", "83000000", date(2025, 5, 20), date(2026, 11, 10), "At Risk"),
        ("MECH-INS", "Painting and Insulation", "Pipe Rack", "MECHANICAL", "VOL", "10", "54", "51", "70000000", "59000000", "41000000", date(2026, 1, 10), date(2026, 12, 10), "On Track"),
        ("ELE-TRAY", "Cable Tray Installation", "Process Unit", "ELECTRICAL", "KEC", "24", "76", "79", "105000000", "98000000", "84000000", date(2025, 8, 1), date(2026, 9, 25), "On Track"),
        ("ELE-CABLE", "Cable Laying", "RPTU", "ELECTRICAL", "KEC", "30", "61", "66", "165000000", "157000000", "121000000", date(2025, 11, 1), date(2026, 11, 20), "On Track"),
        ("ELE-EQP", "Equipment Installation", "Substation", "ELECTRICAL", "TCE", "20", "68", "64", "95000000", "88000000", "69000000", date(2025, 9, 15), date(2026, 10, 30), "At Risk"),
        ("ELE-TERM", "Termination and Testing", "All Areas", "ELECTRICAL", "KEC", "26", "43", "45", "145000000", "133000000", "92000000", date(2026, 1, 5), date(2026, 12, 5), "On Track"),
        ("CIV-EARTH", "Earthworks", "RPTU", "CIVIL", "LNT", "14", "100", "100", "80000000", "76000000", "75000000", date(2025, 1, 20), date(2025, 8, 30), "Completed"),
        ("CIV-PILE", "Piling", "Process Unit", "CIVIL", "LNT", "22", "100", "96", "180000000", "171000000", "164000000", date(2025, 2, 15), date(2026, 2, 20), "At Risk"),
        ("CIV-FDN", "Foundations", "Pipe Rack", "CIVIL", "TCE", "30", "87", "78", "230000000", "219000000", "185000000", date(2025, 5, 1), date(2026, 9, 30), "Delayed"),
        ("CIV-STR", "Structures", "Substation", "CIVIL", "TCE", "22", "73", "69", "145000000", "136000000", "104000000", date(2025, 8, 1), date(2026, 10, 20), "At Risk"),
        ("CIV-BLD", "Buildings and Finishing", "Admin Block", "CIVIL", "VOL", "12", "52", "55", "85000000", "79000000", "52000000", date(2025, 10, 10), date(2026, 12, 5), "On Track"),
    ]
    created_packages: list[WorkPackage] = []
    for code, name, area, discipline_code, contractor_code, weight, planned, actual, budget, committed, actual_cost, start, target, status in packages:
        package = WorkPackage(
            discipline_id=disciplines[discipline_code].id, contractor=contractors[contractor_code], code=code, name=name,
            area=area, weight=Decimal(weight), planned_progress=Decimal(planned), actual_progress=Decimal(actual),
            budget=Decimal(budget), committed_cost=Decimal(committed), actual_cost=Decimal(actual_cost), start_date=start,
            target_date=target, status=status,
        )
        db.add(package)
        created_packages.append(package)

    db.flush()
    seed_sub_tasks_for_packages(db, created_packages)

    db.add_all([
        Milestone(project_id=project.id, name="Mechanical completion - Unit 30", discipline_code="MECHANICAL", planned_date=date(2026, 9, 28), forecast_date=date(2026, 10, 10), status="Delayed"),
        Milestone(project_id=project.id, name="Substation-2 energization", discipline_code="ELECTRICAL", planned_date=date(2026, 10, 6), forecast_date=date(2026, 10, 6), status="On Track"),
        Milestone(project_id=project.id, name="Pipe rack foundations released", discipline_code="CIVIL", planned_date=date(2026, 10, 12), forecast_date=date(2026, 10, 18), status="At Risk"),
    ])
    db.add_all([
        Risk(project_id=project.id, title="Piping erection behind baseline", discipline_code="MECHANICAL", severity="Critical", owner="Construction", due_date=date(2026, 9, 18), mitigation="Release Area 30A access and add a second erection crew.", status="Open"),
        Risk(project_id=project.id, title="Foundation F-14 concrete hold", discipline_code="CIVIL", severity="High", owner="Civil", due_date=date(2026, 9, 20), mitigation="Expedite client approval for revised reinforcement detail.", status="Open"),
        Risk(project_id=project.id, title="HT cable drum delivery variance", discipline_code="ELECTRICAL", severity="Medium", owner="Procurement", due_date=date(2026, 9, 24), mitigation="Prioritize critical feeders and use approved alternate drum allocation.", status="Open"),
    ])

    project_two = Project(
        code="VTM-2026-04", name="Vizag Terminal Modernization", client="VPT", location="Visakhapatnam, India",
        start_date=date(2025, 3, 2), planned_finish=date(2027, 3, 15), forecast_finish=date(2027, 3, 9),
        approved_budget=Decimal("1480000000"), currency="INR", status="On Track",
    )
    db.add(project_two)
    db.flush()
    for code, name, weight, planned, actual, budget, target in [
        ("MECHANICAL", "Mechanical", "45", "74", "76", "666000000", date(2027, 2, 15)),
        ("ELECTRICAL", "Electrical", "25", "65", "68", "370000000", date(2027, 2, 28)),
        ("CIVIL", "Civil", "30", "73", "71", "444000000", date(2027, 1, 30)),
    ]:
        db.add(Discipline(project_id=project_two.id, code=code, name=name, weight=Decimal(weight), planned_progress=Decimal(planned), actual_progress=Decimal(actual), budget=Decimal(budget), target_date=target))

    db.commit()
