import json
from pathlib import Path

from komsu.app import create_app
from komsu.config import Settings

target = Path("packages/contracts/openapi.json")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(
    json.dumps(
        create_app(Settings(environment="test", _env_file=None)).openapi(),
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
print("OpenAPI contract exported")
