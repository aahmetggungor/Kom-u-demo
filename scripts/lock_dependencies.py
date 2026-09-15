import importlib.metadata as metadata
from pathlib import Path

rows = sorted(
    f"{d.metadata['Name']}=={d.version}"
    for d in metadata.distributions()
    if d.metadata["Name"].lower() not in {"komsu", "pip", "setuptools"}
)
Path("requirements.lock").write_text("\n".join(rows) + "\n", encoding="utf-8")
