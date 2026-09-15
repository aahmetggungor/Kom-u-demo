import os

from alembic import context
from dotenv import load_dotenv
from komsu.models import Base
from sqlalchemy import create_engine, pool

load_dotenv()
url = os.environ.get(
    "KOMSU_ADMIN_DATABASE_URL", os.environ.get("KOMSU_DATABASE_URL", "sqlite:///./komsu.db")
)
target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
