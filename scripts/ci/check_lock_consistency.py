"""Fail if lockfile pins violate requirements floors or diverge across locks.

Guards the class of bug where requirements-ingestion.lock resolved certifi
below the declared >=2026.10.19 floor while installing into the same image
as requirements-core.lock. Deterministic; runs offline.

Usage: python scripts/ci/check_lock_consistency.py  (exit 1 + report on drift)
"""

import re
import sys
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[2]

# requirements-*.txt declare floors; requirements-*.lock must satisfy them
# and agree with each other where a package is pinned in more than one.
LOCK_FOR_TXT = {
    "requirements-core.txt": "requirements-core.lock",
    "requirements-ingestion.txt": "requirements-ingestion.lock",
}

LOCKS = [
    "requirements-core.lock",
    "requirements-ingestion.lock",
    "requirements-ci.lock",
]

PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([0-9][^\s\\]*)")
# Optional extras suffix ([...]) so lines like "pwdlib[argon2]>=0.3.1" parse.
FLOOR_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?>=(\S+?)\s*(?:,|$|#)")


def _norm(name: str) -> str:
    """PEP 503 name normalization so pin/floor lookups can't diverge on
    '-' vs '_' vs '.' spellings of the same distribution."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_pins(path: Path) -> dict:
    pins = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = PIN_RE.match(line.strip())
        if m:
            pins[_norm(m.group(1))] = m.group(2)
    return pins


def parse_floors(path: Path) -> dict:
    floors = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or line.startswith("-"):
            continue
        m = FLOOR_RE.match(line)
        if m:
            floors.setdefault(_norm(m.group(1)), m.group(2))
    return floors


def main() -> int:
    errors = []
    lock_pins = {name: parse_pins(ROOT / name) for name in LOCKS}

    # 1. Every floor must be satisfied by the corresponding lock pin.
    for txt, lock in LOCK_FOR_TXT.items():
        for pkg, floor in parse_floors(ROOT / txt).items():
            pin = lock_pins.get(lock, {}).get(pkg)
            if pin is None:
                continue  # not pinned in that lock (e.g. optional extra)
            if Version(pin) < Version(floor):
                errors.append(f"{lock}: {pkg}=={pin} below {txt} floor >={floor}")

    # 2. A package pinned in core and ingestion locks must pin identically
    #    (Dockerfile installs both into the same site-packages, last wins).
    shared = set(lock_pins["requirements-core.lock"]) & set(
        lock_pins["requirements-ingestion.lock"]
    )
    for pkg in sorted(shared):
        a = lock_pins["requirements-core.lock"][pkg]
        b = lock_pins["requirements-ingestion.lock"][pkg]
        if a != b:
            errors.append(
                f"pin mismatch: {pkg} core=={a} ingestion=={b} (same image)"
            )

    if errors:
        print("Lockfile consistency check FAILED:")
        for e in errors:
            print(f"  - {e}")
        print(
            "\nFix: regenerate with -c constraints, e.g.\n"
            "  uv pip compile --generate-hashes --python-platform x86_64-unknown-linux-gnu "
            "--python-version 3.11 --index-strategy unsafe-best-match "
            "--extra-index-url https://download.pytorch.org/whl/cpu "
            "requirements-ingestion.txt -c requirements-core.lock -o requirements-ingestion.lock"
        )
        return 1
    print(f"OK: {len(shared)} shared pins agree; all floors satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
