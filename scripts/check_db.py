import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
url = os.environ["KOMSU_ADMIN_DATABASE_URL"].replace("@localhost:", "@127.0.0.1:")
try:
    with create_engine(url, connect_args={"connect_timeout": 5}).connect() as connection:
        print(connection.execute(text("SELECT version()")).scalar())
except Exception as exc:
    print(type(exc).__name__)
    raise SystemExit(1) from None
