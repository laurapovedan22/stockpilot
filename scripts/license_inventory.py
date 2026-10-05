"""Record declared metadata of installed dependencies; not a legal license audit."""

import importlib.metadata as metadata
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cell(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")


def main() -> None:
    rows = set()
    for distribution in metadata.distributions():
        info = distribution.metadata
        license_name = info.get("License-Expression") or info.get("License")
        if not license_name or len(license_name) > 150:
            classifiers = [
                value.rsplit(" :: ", 1)[-1]
                for value in info.get_all("Classifier", [])
                if value.startswith("License ::")
            ]
            license_name = "; ".join(classifiers) or "See installed LICENSE files"
        rows.add(("Python", info["Name"], distribution.version, license_name))
    for path in (ROOT / "frontend/node_modules").rglob("package.json"):
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if package.get("name") and package.get("version"):
            declared = package.get("license") or "See installed LICENSE files"
            if isinstance(declared, dict):
                declared = declared.get("type", str(declared))
            rows.add(("npm", package["name"], package["version"], str(declared)))
    lines = [
        "# Installed dependency license metadata",
        "",
        f"Generated from installed artifacts on {date.today().isoformat()}. Versions are locked",
        "in backend/uv.lock and frontend/package-lock.json. Metadata is informational;",
        "binary libraries and redistribution obligations require their own LICENSE review.",
        "Docker base images are outside this Python/npm inventory.",
        "",
        "| Ecosystem | Package | Version | Declared license |",
        "|---|---|---|---|",
    ]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in sorted(rows))
    output = ROOT / "docs/dependency-licenses.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Recorded {len(rows)} installed package declarations in {output}")


if __name__ == "__main__":
    main()
