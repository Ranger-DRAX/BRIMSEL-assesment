#!/usr/bin/env python3
"""Cross-platform verification script for Little English Buddy.

Executes all automated checks:
- Backend: ruff lint, mypy typecheck, pytest test matrix
- Frontend: type-check, vitest unit tests, next build

Usage:
    python scripts/verify.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"

# Virtualenv python/executables
if sys.platform == "win32":
    VENV_PY = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    VENV_RUFF = BACKEND_DIR / ".venv" / "Scripts" / "ruff.exe"
    VENV_MYPY = BACKEND_DIR / ".venv" / "Scripts" / "mypy.exe"
    VENV_PYTEST = BACKEND_DIR / ".venv" / "Scripts" / "pytest.exe"
    NPM_CMD = "npm.cmd"
else:
    VENV_PY = BACKEND_DIR / ".venv" / "bin" / "python"
    VENV_RUFF = BACKEND_DIR / ".venv" / "bin" / "ruff"
    VENV_MYPY = BACKEND_DIR / ".venv" / "bin" / "mypy"
    VENV_PYTEST = BACKEND_DIR / ".venv" / "bin" / "pytest"
    NPM_CMD = "npm"


def run_step(name: str, cmd: list[str], cwd: Path) -> bool:
    """Run a single verification step and report status."""
    print(f"\n{'=' * 60}")
    print(f"▶ {name}")
    print(f"  Command: {' '.join(str(c) for c in cmd)}")
    print(f"  Cwd:     {cwd}")
    print(f"{'=' * 60}")

    start = time.monotonic()
    result = subprocess.run(cmd, cwd=cwd)
    duration = time.monotonic() - start

    if result.returncode == 0:
        print(f"✔ {name} PASSED in {duration:.2f}s")
        return True
    else:
        print(f"✘ {name} FAILED with exit code {result.returncode} in {duration:.2f}s")
        return False


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Little English Buddy Full Verification Suite")
    parser.add_argument("--with-e2e", action="store_true", help="Include Playwright E2E tests")
    args = parser.parse_args()

    print("\n🔍 Running Little English Buddy Full Verification Suite\n")

    steps = [
        # 1. Backend Linting
        ("Backend Lint (ruff)", [str(VENV_RUFF), "check", "app", "tests"], BACKEND_DIR),
        # 2. Backend Type Check
        ("Backend Type Check (mypy)", [str(VENV_MYPY), "app", "tests"], BACKEND_DIR),
        # 3. Backend Unit & API Tests
        ("Backend Test Suite (pytest)", [str(VENV_PYTEST), "-v"], BACKEND_DIR),
        # 4. Frontend Type Check
        ("Frontend Type Check (tsc)", [NPM_CMD, "run", "type-check"], FRONTEND_DIR),
        # 5. Frontend Unit Tests (Vitest)
        ("Frontend Unit Tests (vitest)", [NPM_CMD, "test"], FRONTEND_DIR),
        # 6. Frontend Production Build
        ("Frontend Production Build (next build)", [NPM_CMD, "run", "build"], FRONTEND_DIR),
    ]

    if args.with_e2e:
        steps.append(
            ("End-to-End Tests (playwright)", [NPM_CMD, "run", "test:e2e"], FRONTEND_DIR)
        )

    failed = []
    for name, cmd, cwd in steps:
        success = run_step(name, cmd, cwd)
        if not success:
            failed.append(name)

    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    if not failed:
        print("🎉 ALL CHECKS PASSED!")
        return 0
    else:
        print(f"❌ {len(failed)} step(s) failed:")
        for f in failed:
            print(f"  - {f}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
