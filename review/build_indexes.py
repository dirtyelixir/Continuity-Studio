#!/usr/bin/env python3
"""Generate review/module-inventory.md and review/docs-index.md from real repo data.

Reads review/module-map.json (produced by review/analyze_repo.py) plus the docs directory.
Deterministic; no network access.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "review" / "module-map.json").read_text(encoding="utf-8"))
HTTP = json.loads((ROOT / "review" / "http-and-db.json").read_text(encoding="utf-8"))


def first_sentence(text: str, limit: int = 150) -> str:
    text = " ".join(text.split())
    if not text:
        return "—"
    for stop in (". ", "。", "！", "!"):
        idx = text.find(stop)
        if 0 < idx < limit:
            return text[: idx + 1]
    return text[:limit] + ("…" if len(text) > limit else "")


lines = [
    "# Module inventory (generated)",
    "",
    f"Flat package `studio/`: **{DATA['counts']['studio_modules']} modules**, "
    f"**{DATA['counts']['studio_loc']} lines**. "
    f"Tests: **{DATA['counts']['test_files']} files**, {DATA['counts']['test_loc']} lines. "
    f"HTTP routes in `studio/app.py`: **{len(HTTP['routes'])}**. "
    f"SQLite tables (created in `studio/store.py`): {', '.join(HTTP['db_tables'])}.",
    "",
    "`deps` = internal modules it imports; `used by` = internal modules importing it; "
    "`test refs` = textual `studio.<module>` references across `tests/`. "
    "Docstrings are first-person as written in the source.",
    "",
    "| module | LOC | bytes | deps | used by | test refs | purpose (source docstring) |",
    "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
]
for m in DATA["studio_modules"]:
    name = m["module"].replace("studio.", "")
    used_by = len(DATA["imported_by"].get(m["module"], []))
    lines.append(
        f"| `{name}` | {m['loc']} | {m['bytes']} | {len(m['imports_internal'])} | "
        f"{used_by} | {m['test_refs']} | {first_sentence(m['docstring'])} |"
    )

lines += [
    "",
    "## Hub modules (most imported)",
    "",
    "| module | imported by |",
    "| --- | ---: |",
]
for mod, importers in sorted(
    DATA["imported_by"].items(), key=lambda kv: -len(kv[1])
)[:15]:
    if importers:
        lines.append(f"| `{mod.replace('studio.', '')}` | {len(importers)} |")

lines += [
    "",
    "## Modules with no textual test reference",
    "",
    "A test may still exercise these through another module's public path; "
    "the list marks where the mapping is not explicit.",
    "",
]
no_refs = [
    m["module"].replace("studio.", "")
    for m in DATA["studio_modules"]
    if m["test_refs"] == 0 and not m["module"].endswith("__init__")
]
lines.append(", ".join(f"`{n}`" for n in no_refs) or "—")
lines.append("")
(ROOT / "review" / "module-inventory.md").write_text("\n".join(lines), encoding="utf-8")

doc_lines = ["# Documentation index (generated)", "", "| doc | bytes | first heading / line |", "| --- | ---: | --- |"]
for path in sorted((ROOT / "docs").glob("*")):
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    head = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    doc_lines.append(f"| `docs/{path.name}` | {path.stat().st_size} | {first_sentence(head.lstrip('# '), 120)} |")
doc_lines.append("")
(ROOT / "review" / "docs-index.md").write_text("\n".join(doc_lines), encoding="utf-8")
print("wrote review/module-inventory.md and review/docs-index.md")
