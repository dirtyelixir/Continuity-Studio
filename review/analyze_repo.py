#!/usr/bin/env python3
"""Static inventory for review: LOC, module imports, HTTP routes, DB tables.

Deterministic and read-only. Writes review/module-map.json + review/imports.json.
Run: .venv/bin/python review/analyze_repo.py  (from the repository root)
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "studio"


def loc(path: pathlib.Path) -> int:
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
    except OSError:
        return 0


def module_name(path: pathlib.Path) -> str:
    return "studio." + path.stem if path.parent == PKG else path.stem


def imports_of(path: pathlib.Path) -> dict:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:  # pragma: no cover - reported, not hidden
        return {"error": str(exc)}
    out: dict[str, list[str]] = {"internal": [], "third_party": []}
    self_stem = path.stem
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("studio"):
                    out["internal"].append(alias.name.split(".")[-1])
                else:
                    out["third_party"].append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level or mod == "studio" or mod.startswith("studio."):
                # Relative (level 1 == the flat `studio/` package) or explicit package.
                target = mod[len("studio.") :] if mod.startswith("studio.") else mod
                if target:
                    base = target.split(".")[0]
                    out["internal"].append(base)
                else:  # `from . import a, b, c` — the aliases are the modules
                    for alias in node.names:
                        out["internal"].append(alias.name.split(".")[0])
            else:
                out["third_party"].append(mod.split(".")[0] if mod else "")
    for key in out:
        out[key] = sorted(
            x
            for x in set(out[key])
            if x and x != self_stem and not x.startswith("_") or x == "_")
    return out


def routes(path: pathlib.Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        r"@app\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']", re.IGNORECASE
    )
    found = [
        {"method": m.upper(), "path": p}
        for m, p in pattern.findall(text)
    ]
    router = re.compile(
        r"@router\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']", re.IGNORECASE
    )
    found += [
        {"method": m.upper(), "path": p, "router": True} for m, p in router.findall(text)
    ]
    return sorted(found, key=lambda r: (r["path"], r["method"]))


def tables(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return sorted(set(re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", text)))


def docstring_of(path: pathlib.Path) -> str:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return ""
    doc = ast.get_docstring(tree) or ""
    return " ".join(doc.split())


def style_stats(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    non_empty = [line for line in lines if line.strip()]
    return {
        "lines": len(lines),
        "non_empty": len(non_empty),
        "avg_chars": round(len(text) / max(len(non_empty), 1), 1),
        "lines_over_120": sum(1 for line in non_empty if len(line) > 120),
        "lines_with_semicolon": sum(
            1 for line in non_empty if ";" in line and not line.strip().startswith("#")
        ),
    }


def main() -> int:
    tests_dir = ROOT / "tests"
    test_text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(tests_dir.glob("test_*.py"))
    ) if tests_dir.exists() else ""
    modules = []
    for path in sorted(PKG.glob("*.py")):
        entry = imports_of(path)
        stem = path.stem
        modules.append(
            {
                "module": module_name(path),
                "file": str(path.relative_to(ROOT)),
                "loc": loc(path),
                "bytes": path.stat().st_size,
                "docstring": docstring_of(path)[:600],
                "imports_internal": entry.get("internal", []),
                "imports_external": entry.get("third_party", []),
                "style": style_stats(path),
                "test_refs": test_text.count(f"studio.{stem}") + test_text.count(f"studio import {stem}"),
                "error": entry.get("error"),
            }
        )
    modules.sort(key=lambda m: -m["loc"])

    internal_edges = {
        m["module"]: [i for i in m["imports_internal"] if (PKG / f"{i}.py").exists()]
        for m in modules
    }
    reverse: dict[str, list[str]] = {m["module"]: [] for m in modules}
    for src, deps in internal_edges.items():
        for dep in deps:
            reverse.setdefault(f"studio.{dep}", []).append(src)
    for name in reverse:
        reverse[name] = sorted(set(reverse[name]))

    tests = []
    tests_dir = ROOT / "tests"
    if tests_dir.exists():
        for path in sorted(tests_dir.glob("test_*.py")):
            tests.append(
                {"file": str(path.relative_to(ROOT)), "loc": loc(path)}
            )

    maps = {
        "generated_by": "review/analyze_repo.py",
        "studio_modules": modules,
        "internal_edges": {k: sorted(v) for k, v in internal_edges.items()},
        "imported_by": reverse,
        "tests": tests,
        "counts": {
            "studio_modules": len(modules),
            "studio_loc": sum(m["loc"] for m in modules),
            "test_files": len(tests),
            "test_loc": sum(t["loc"] for t in tests),
        },
    }
    http = {
        "routes": routes(ROOT / "studio" / "app.py"),
        "db_tables": tables(ROOT / "studio" / "store.py"),
    }
    (ROOT / "review" / "module-map.json").write_text(
        json.dumps(maps, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    (ROOT / "review" / "http-and-db.json").write_text(
        json.dumps(http, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({**maps["counts"], "routes": len(http["routes"]), "tables": len(http["db_tables"])}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
