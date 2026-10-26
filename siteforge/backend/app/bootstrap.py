import argparse, getpass
from app.db import SessionLocal
from app.domains.identity_projects.models import Organization, Company, User
from app.domains.identity_projects.security import hasher
from app.domains.identity_projects.seed import seed


def main():
    parser = argparse.ArgumentParser(
        description="Create an organization and its first administrator"
    )
    parser.add_argument("--organization", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    email = args.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        parser.error("Valid email required")
    password = getpass.getpass("Administrator password (12+ characters): ")
    if len(password) < 12 or len(password) > 128:
        parser.error("Password must be 12–128 characters")
    if password != getpass.getpass("Confirm password: "):
        parser.error("Passwords differ")
    with SessionLocal() as db:
        if db.query(User).filter_by(email=email).first():
            parser.error("Email already registered")
        seed(db)
        org = Organization(name=args.organization)
        db.add(org)
        db.flush()
        c = Company(
            organization_id=org.id,
            name=args.organization,
            name_key=args.organization.casefold(),
            company_type="Contractor",
        )
        db.add(c)
        db.flush()
        db.add(
            User(
                organization_id=org.id,
                company_id=c.id,
                name=args.name,
                email=email,
                password_hash=hasher.hash(password),
                organization_admin=True,
            )
        )
        db.commit()
    print("Organization and administrator created. No sample credentials were stored.")


if __name__ == "__main__":
    main()
