from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clone or update external dependency repositories")
    parser.add_argument("--manifest", default="vendor/repositories.json")
    parser.add_argument("--lock-file", default="vendor/repositories.lock.json")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def run_git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def load_manifest(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    repositories = data.get("repositories")
    if not isinstance(repositories, list):
        raise ValueError("repositories manifest must contain a repositories list")
    return [item for item in repositories if isinstance(item, dict)]


def ensure_repo(root: Path, entry: dict[str, Any], update: bool) -> dict[str, Any]:
    target = root / str(entry["target"]).replace("/", "\\") if not Path(str(entry["target"])).is_absolute() else Path(str(entry["target"]))
    url = str(entry["url"])
    branch = str(entry.get("branch") or "main")
    target.parent.mkdir(parents=True, exist_ok=True)

    if not target.exists():
        run_git(["git", "clone", "--branch", branch, url, str(target)])
    elif update:
        run_git(["git", "fetch", "--all", "--tags"], cwd=target)
        run_git(["git", "checkout", branch], cwd=target)
        run_git(["git", "pull", "--ff-only", "origin", branch], cwd=target)

    commit = run_git(["git", "rev-parse", "HEAD"], cwd=target)
    return {
        "name": entry["name"],
        "url": url,
        "target": str(target),
        "branch": branch,
        "commit": commit,
    }


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    lock_path = Path(args.lock_file)
    repo_root = Path.cwd()

    entries = load_manifest(manifest_path)
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for entry in entries:
        try:
            result = ensure_repo(repo_root, entry, args.update)
            results.append(result)
            print(f"[ok] {entry['name']} -> {result['commit']}")
        except Exception as exc:
            message = f"{entry.get('name', 'unknown')}: {exc}"
            failures.append(message)
            print(f"[error] {message}")
            if args.strict or entry.get("required"):
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                lock_path.write_text(json.dumps({"repositories": results}, ensure_ascii=False, indent=2), encoding="utf-8")
                return 1

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps({"repositories": results, "failures": failures}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())