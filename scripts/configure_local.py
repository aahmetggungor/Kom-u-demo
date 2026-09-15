"""Generate local-only random credentials without printing them."""

import base64
import secrets
from pathlib import Path

path = Path(".env")
if path.exists():
    raise SystemExit(".env exists; preserving current credentials")
admin = secrets.token_hex(24)
runtime = secrets.token_hex(24)
audio_key = base64.b64encode(secrets.token_bytes(32)).decode()
path.write_text(
    f"KOMSU_DB_PASSWORD={admin}\nKOMSU_APP_PASSWORD={runtime}\nKOMSU_DATABASE_URL=postgresql+psycopg://komsu_app:{runtime}@127.0.0.1:55432/komsu\nKOMSU_ADMIN_DATABASE_URL=postgresql+psycopg://postgres:{admin}@127.0.0.1:55432/komsu\nKOMSU_AUDIO_MASTER_KEY_B64={audio_key}\nKOMSU_AUDIO_KEY_ID=development-audio-v1\nKOMSU_ENVIRONMENT=development\n",
    encoding="utf-8",
)
print("Created ignored .env with random local credentials")
