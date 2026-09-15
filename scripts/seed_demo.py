import json
import os
from pathlib import Path

from dotenv import load_dotenv
from komsu.db import make_engine, tenant_session
from komsu.domain import ingest
from komsu.schemas import ReportIn
from komsu.security import Principal
from komsu.worker import process_one

load_dotenv()
identity = json.loads(Path(".env.session.json").read_text(encoding="utf-8"))
engine = make_engine(os.environ["KOMSU_DATABASE_URL"])
principal = Principal(identity["tenant_id"], identity["user_id"], identity["role"])
rows = [
    json.loads(line)
    for line in Path("data/disaster.synthetic.jsonl").read_text(encoding="utf-8").splitlines()
][:12]
for row in rows:
    row.pop("gold")
    with tenant_session(engine, principal.tenant_id) as session:
        ingest(session, principal, ReportIn.model_validate(row), 10000)
while process_one(engine, principal.tenant_id):
    pass
print("Seeded and processed 12 synthetic reports; semantic merge not automatically performed")
