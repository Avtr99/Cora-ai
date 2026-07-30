"""Sync version from root package.json into the backend and frontend packages."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PACKAGE_JSON = ROOT / "package.json"
VERSION_FILE = ROOT / "src" / "version.py"
FRONTEND_PACKAGE_JSON = ROOT / "frontend" / "package.json"


def main() -> None:
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    version = package["version"]

    VERSION_FILE.write_text(
        f'"""Single-source package version, synced from root package.json by release-it."""\n\n__version__ = "{version}"\n',
        encoding="utf-8",
    )

    frontend_package = json.loads(FRONTEND_PACKAGE_JSON.read_text(encoding="utf-8"))
    frontend_package["version"] = version
    FRONTEND_PACKAGE_JSON.write_text(
        json.dumps(frontend_package, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Synced version {version} to {VERSION_FILE} and {FRONTEND_PACKAGE_JSON}")


if __name__ == "__main__":
    main()
