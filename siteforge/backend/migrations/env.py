from alembic import context
from sqlalchemy import create_engine, pool
from app.config import settings
from app.db import Base
from app.domains.identity_projects import models
from app.domains.engineering_documents import models as document_models
from app.domains.coordination import models as coordination_models
from app.domains.supply_chain import models as procurement_models

from app.domains.partner_portal import models as partner_models
from app.domains.stores_inventory import models as stores_models

_ = (models, document_models, coordination_models, procurement_models, partner_models, stores_models)

config = context.config


def offline():
    context.configure(
        url=settings.database_url, target_metadata=Base.metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()


def online():
    engine = create_engine(settings.database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=Base.metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    offline()
else:
    online()
