"""Unit tests for studio/skills.py — safe local instruction-skill registry.

Tests cover:
* discover (root-as-skill, child dirs, defaults)
* install (immutable snapshot, tamper-independent copy, hash pinning)
* enable/permissions (required grants, unsupported permissions)
* unsupported api_version
* path traversal / symlinks / executable permissions / size limit
* injection via malicious IDs
* instructions (enabled only, capability matching, wildcard, disabled
  supply nothing)
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio import skills  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def make_skill(
    root: Path,
    name: str = "Test Skill",
    description: str = "A test skill",
    studio_json: dict | None = None,
    body: str = "Do the thing.",
    refs: dict[str, str] | None = None,
    subdir: str | None = None,
) -> Path:
    """Create a minimal skill directory and return its path."""
    skill_dir = root / (subdir or "my-skill")
    skill_dir.mkdir(parents=True, exist_ok=True)
    fm = f"---\nname: {name}\ndescription: {description}\n---\n"
    (skill_dir / "SKILL.md").write_text(fm + body, encoding="utf-8")
    if studio_json is not None:
        (skill_dir / "studio.json").write_text(
            json.dumps(studio_json), encoding="utf-8"
        )
    if refs:
        refs_dir = skill_dir / "references"
        refs_dir.mkdir(exist_ok=True)
        for rel, content in refs.items():
            p = refs_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
    return skill_dir


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


def test_discover_root_as_skill(tmpdir):
    make_skill(tmpdir, name="Root Skill", description="root skill desc")
    results = skills.discover([str(tmpdir)])
    assert len(results) == 1
    r = results[0]
    assert r["name"] == "Root Skill"
    assert r["description"] == "root skill desc"
    assert r["capabilities"] == ["direction"]
    assert r["version"] == "1.0.0"
    assert r["permissions"] == ["project:read"]
    assert r["enabled"] is False
    assert r["granted_permissions"] == []
    assert len(r["hash"]) == 64
    assert r["id"] is not None


def test_discover_child_dirs(tmpdir):
    make_skill(tmpdir, name="A", description="a", subdir="skill-a")
    make_skill(tmpdir, name="B", description="b", subdir="skill-b")
    results = skills.discover([str(tmpdir)])
    assert len(results) == 2
    names = {r["name"] for r in results}
    assert names == {"A", "B"}


def test_discover_nonexistent_root(tmpdir):
    results = skills.discover([str(tmpdir / "nope")])
    assert results == []


def test_discover_multiple_roots(tmpdir):
    root2 = tmpdir / "other"
    root2.mkdir()
    make_skill(tmpdir, name="X", description="x", subdir="sx")
    make_skill(root2, name="Y", description="y", subdir="sy")
    results = skills.discover([str(tmpdir), str(root2)])
    assert len(results) == 2


def test_discover_invalid_roots_type(tmpdir):
    with pytest.raises(ValueError):
        skills.discover("not-a-list")  # type: ignore
    with pytest.raises(ValueError):
        skills.discover([1, 2])  # type: ignore


def test_discover_skips_malformed(tmpdir):
    # Valid skill
    make_skill(tmpdir, name="Good", description="good", subdir="good")
    # Malformed: missing frontmatter
    bad = tmpdir / "bad"
    bad.mkdir()
    (bad / "SKILL.md").write_text("no frontmatter here", encoding="utf-8")
    results = skills.discover([str(tmpdir)])
    assert len(results) == 1
    assert results[0]["name"] == "Good"


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


def test_install_creates_snapshot(tmpdir):
    src = make_skill(tmpdir, name="Install Me", description="desc", subdir="src")
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    assert result["name"] == "Install Me"
    assert result["enabled"] is False
    assert result["granted_permissions"] == []
    # Snapshot dir exists and is named id-version-hashprefix
    snap = dest / result["id"]
    assert snap.is_dir()
    assert (snap / "SKILL.md").is_file()
    # Registry exists
    reg = json.loads((dest / "registry.json").read_text(encoding="utf-8"))
    assert result["id"] in reg["skills"]
    entry = reg["skills"][result["id"]]
    assert entry["enabled"] is False
    assert entry["granted_permissions"] == []
    assert entry["hash"] == result["hash"]


def test_install_pinning_tamper_independent(tmpdir):
    """After install, changing the source must not affect the snapshot."""
    src = make_skill(
        tmpdir,
        name="Pinned",
        description="d",
        subdir="pin-src",
        body="original body",
        refs={"notes.md": "ref v1"},
    )
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    hash_before = result["hash"]
    snap = dest / result["id"]

    # Tamper the source.
    (src / "SKILL.md").write_text(
        "---\nname: Pinned\ndescription: d\n---\nTAMPERED body", encoding="utf-8"
    )
    (src / "references" / "notes.md").write_text("ref v2", encoding="utf-8")

    # Re-read snapshot: unchanged.
    snap_text = (snap / "SKILL.md").read_text(encoding="utf-8")
    assert "original body" in snap_text
    assert "TAMPERED" not in snap_text
    assert (snap / "references" / "notes.md").read_text(encoding="utf-8") == "ref v1"

    # Re-hash snapshot files to confirm hash pinning.
    files = {}
    for p in sorted(snap.rglob("*")):
        if p.is_file():
            rel = p.relative_to(snap).as_posix()
            files[rel] = p.read_bytes()
    from studio.skills import _hash_files
    assert _hash_files(files) == hash_before


def test_install_never_edits_source(tmpdir):
    src = make_skill(tmpdir, name="Src", description="s", subdir="src")
    before = {
        p.as_posix(): p.read_bytes()
        for p in sorted(src.rglob("*"))
        if p.is_file()
    }
    dest = tmpdir / "dest"
    skills.install(str(src), str(dest))
    after = {
        p.as_posix(): p.read_bytes()
        for p in sorted(src.rglob("*"))
        if p.is_file()
    }
    assert before == after


def test_install_copy_only_safe_files(tmpdir):
    src = make_skill(
        tmpdir,
        name="Safe",
        description="s",
        subdir="src",
        refs={"a.md": "text a", "sub/b.txt": "text b"},
    )
    # Add a script and a non-reference file.
    (src / "script.py").write_text("print('hi')", encoding="utf-8")
    (src / "README").write_text("readme", encoding="utf-8")
    (src / "references" / "image.png").write_bytes(b"\x89PNG")
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    snap = dest / result["id"]
    rels = {p.relative_to(snap).as_posix() for p in snap.rglob("*") if p.is_file()}
    assert rels == {"SKILL.md", "references/a.md", "references/sub/b.txt"}


def test_install_executable_permission_rejected(tmpdir):
    src = make_skill(tmpdir, name="Exec", description="e", subdir="src")
    (src / "SKILL.md").chmod(0o755)
    dest = tmpdir / "dest"
    with pytest.raises(ValueError, match="executable"):
        skills.install(str(src), str(dest))


def test_install_symlink_rejected(tmpdir):
    src = make_skill(tmpdir, name="Sym", description="s", subdir="src")
    # Replace SKILL.md with a symlink.
    real = src / "SKILL.md"
    real_text = real.read_text(encoding="utf-8")
    real.unlink()
    (src / "_SKILL_real.md").write_text(real_text, encoding="utf-8")
    os.symlink(src / "_SKILL_real.md", real)
    dest = tmpdir / "dest"
    with pytest.raises(ValueError, match="symlink"):
        skills.install(str(src), str(dest))


def test_install_size_limit(tmpdir):
    src = make_skill(
        tmpdir, name="Big", description="b", subdir="src", refs={"pad.md": "x"}
    )
    # Grow an existing reference file past 1MB.
    big = src / "references" / "pad.md"
    big.write_bytes(b"x" * (1_048_577))
    dest = tmpdir / "dest"
    with pytest.raises(ValueError, match="exceeds limit"):
        skills.install(str(src), str(dest))


def test_install_malformed_frontmatter(tmpdir):
    bad = tmpdir / "bad"
    bad.mkdir()
    (bad / "SKILL.md").write_text("---\nname: X\n---\nbody", encoding="utf-8")
    dest = tmpdir / "dest"
    with pytest.raises(ValueError):
        skills.install(str(bad), str(dest))


def test_install_missing_description(tmpdir):
    bad = tmpdir / "bad2"
    bad.mkdir()
    (bad / "SKILL.md").write_text("---\nname: X\n---\nbody", encoding="utf-8")
    dest = tmpdir / "dest"
    with pytest.raises(ValueError):
        skills.install(str(bad), str(dest))


# ---------------------------------------------------------------------------
# studio.json manifest
# ---------------------------------------------------------------------------


def test_manifest_api_version_supported(tmpdir):
    src = make_skill(
        tmpdir,
        name="API",
        description="d",
        subdir="api-src",
        studio_json={"id": "api-skill", "version": "2.0.0", "api_version": 1},
    )
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    assert result["id"].startswith("api-skill-2.0.0-")


def test_manifest_unsupported_api_version(tmpdir):
    src = make_skill(
        tmpdir,
        name="API2",
        description="d",
        subdir="api-src",
        studio_json={"id": "api2", "api_version": 2},
    )
    dest = tmpdir / "dest"
    with pytest.raises(ValueError, match="api_version"):
        skills.install(str(src), str(dest))


def test_manifest_unsupported_permission(tmpdir):
    src = make_skill(
        tmpdir,
        name="Perm",
        description="d",
        subdir="perm-src",
        studio_json={"id": "perm", "permissions": ["network:read"]},
    )
    dest = tmpdir / "dest"
    with pytest.raises(ValueError, match="unsupported permission"):
        skills.install(str(src), str(dest))


def test_manifest_bad_json(tmpdir):
    bad = tmpdir / "badjson"
    bad.mkdir()
    (bad / "SKILL.md").write_text(
        "---\nname: X\ndescription: d\n---\nbody", encoding="utf-8"
    )
    (bad / "studio.json").write_text("{not json", encoding="utf-8")
    dest = tmpdir / "dest"
    with pytest.raises(ValueError, match="studio.json"):
        skills.install(str(bad), str(dest))


def test_manifest_malicious_id(tmpdir):
    src = make_skill(
        tmpdir,
        name="Mal",
        description="d",
        subdir="mal-src",
        studio_json={"id": "../../etc/passwd"},
    )
    dest = tmpdir / "dest"
    with pytest.raises(ValueError, match="invalid skill id"):
        skills.install(str(src), str(dest))


def test_manifest_malicious_id_traversal_rejected(tmpdir):
    """A studio.json id with path separators would escape the dest root."""
    src = make_skill(
        tmpdir,
        name="Mal2",
        description="d",
        subdir="mal2",
        studio_json={"id": "../escape"},
    )
    dest = tmpdir / "dest"
    with pytest.raises(ValueError, match="invalid skill id"):
        skills.install(str(src), str(dest))


def test_install_injection_id_stays_in_dest(tmpdir):
    """Even when an id is derived, the snapshot must stay inside dest."""
    src = make_skill(
        tmpdir,
        name="A.B/C",
        description="d",
        subdir="inj2",
        studio_json={"id": "a-b_c"},
    )
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    snap = dest / result["id"]
    assert snap.is_dir()
    assert snap.resolve().is_relative_to(dest.resolve())
    # id must be a safe filename
    import re as _re
    assert _re.fullmatch(r"[a-z0-9][a-z0-9_-]*", result["id"].split("-1.0.0-")[0])


# ---------------------------------------------------------------------------
# list_installed
# ---------------------------------------------------------------------------


def test_list_installed(tmpdir):
    src = make_skill(tmpdir, name="L1", description="d", subdir="l1")
    src2 = make_skill(tmpdir, name="L2", description="d", subdir="l2")
    dest = tmpdir / "dest"
    skills.install(str(src), str(dest))
    skills.install(str(src2), str(dest))
    results = skills.list_installed(str(dest))
    assert len(results) == 2
    for r in results:
        assert r["enabled"] is False


def test_list_installed_empty(tmpdir):
    dest = tmpdir / "dest"
    dest.mkdir()
    assert skills.list_installed(str(dest)) == []


# ---------------------------------------------------------------------------
# set_enabled
# ---------------------------------------------------------------------------


def test_set_enabled_requires_permissions(tmpdir):
    src = make_skill(tmpdir, name="En", description="d", subdir="en")
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    # Enable without granting project:read -> fails.
    with pytest.raises(ValueError, match="missing required"):
        skills.set_enabled(str(dest), result["id"], True, [])
    # Enable with grant -> works.
    updated = skills.set_enabled(str(dest), result["id"], True, ["project:read"])
    assert updated["enabled"] is True
    assert updated["granted_permissions"] == ["project:read"]


def test_set_enabled_disable(tmpdir):
    src = make_skill(tmpdir, name="En2", description="d", subdir="en2")
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    skills.set_enabled(str(dest), result["id"], True, ["project:read"])
    updated = skills.set_enabled(str(dest), result["id"], False, [])
    assert updated["enabled"] is False


def test_set_enabled_unknown_id(tmpdir):
    dest = tmpdir / "dest"
    dest.mkdir()
    with pytest.raises(ValueError, match="unknown skill_id"):
        skills.set_enabled(str(dest), "nope", True, [])


def test_set_enabled_unsupported_grant(tmpdir):
    src = make_skill(tmpdir, name="En3", description="d", subdir="en3")
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    with pytest.raises(ValueError, match="unsupported"):
        skills.set_enabled(str(dest), result["id"], True, ["network:write"])


# ---------------------------------------------------------------------------
# instructions
# ---------------------------------------------------------------------------


def test_instructions_enabled_only(tmpdir):
    src = make_skill(
        tmpdir,
        name="Instr",
        description="d",
        subdir="instr",
        body="MAIN BODY",
        refs={"note.md": "REFERENCE TEXT"},
        studio_json={"id": "instr", "capabilities": ["direction"]},
    )
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    # Disabled by default -> no instructions.
    text, meta = skills.instructions(str(dest), "direction")
    assert text == ""
    assert meta == []
    # Enable.
    skills.set_enabled(str(dest), result["id"], True, ["project:read"])
    text, meta = skills.instructions(str(dest), "direction")
    assert "MAIN BODY" in text
    assert "REFERENCE TEXT" in text
    assert "note.md" in text
    assert len(meta) == 1
    assert meta[0]["id"] == result["id"]
    assert meta[0]["skill_dir"] == result["id"]


def test_instructions_disabled_supply_nothing(tmpdir):
    src = make_skill(
        tmpdir, name="OffSkill", description="d", subdir="off", studio_json={"id": "off"}
    )
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    skills.set_enabled(str(dest), result["id"], True, ["project:read"])
    # Now disable again.
    skills.set_enabled(str(dest), result["id"], False, [])
    text, meta = skills.instructions(str(dest), "direction")
    assert text == ""
    assert meta == []


def test_instructions_capability_match(tmpdir):
    src = make_skill(
        tmpdir,
        name="Cap",
        description="d",
        subdir="cap",
        studio_json={"id": "cap", "capabilities": ["custom-cap"]},
    )
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    skills.set_enabled(str(dest), result["id"], True, ["project:read"])
    # Wrong capability -> nothing.
    text, meta = skills.instructions(str(dest), "other")
    assert text == ""
    # Right capability -> text.
    text, meta = skills.instructions(str(dest), "custom-cap")
    assert "Cap" in text
    assert len(meta) == 1


def test_instructions_wildcard(tmpdir):
    src = make_skill(
        tmpdir,
        name="Wild",
        description="d",
        subdir="wild",
        studio_json={"id": "wild", "capabilities": ["*"]},
    )
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    skills.set_enabled(str(dest), result["id"], True, ["project:read"])
    text, meta = skills.instructions(str(dest), "anything")
    assert "Wild" in text
    assert len(meta) == 1


def test_instructions_new_capability_no_default_changes(tmpdir):
    """A skill with a new capability is discoverable without touching defaults."""
    src = make_skill(
        tmpdir,
        name="NewCap",
        description="d",
        subdir="newcap",
        studio_json={"id": "newcap", "capabilities": ["rendering"]},
    )
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    # discover sees it with its capability
    found = skills.discover([str(dest)])
    names = {r["name"] for r in found}
    assert "NewCap" in names
    # instructions for 'direction' doesn't include it (not enabled anyway,
    # and wrong capability)
    skills.set_enabled(str(dest), result["id"], True, ["project:read"])
    text, meta = skills.instructions(str(dest), "direction")
    assert "NewCap" not in text
    text2, meta2 = skills.instructions(str(dest), "rendering")
    assert "NewCap" in text2


def test_instructions_invalid_capability(tmpdir):
    dest = tmpdir / "dest"
    dest.mkdir()
    with pytest.raises(ValueError):
        skills.instructions(str(dest), "")
    with pytest.raises(ValueError):
        skills.instructions(str(dest), 42)  # type: ignore


# ---------------------------------------------------------------------------
# path traversal in references
# ---------------------------------------------------------------------------


def test_references_traversal_via_symlink(tmpdir):
    src = make_skill(
        tmpdir, name="Trav", description="d", subdir="trav", refs={"a.md": "a"}
    )
    refs = src / "references"
    # Symlink pointing outside the skill dir.
    outside = tmpdir / "outside.txt"
    outside.write_text("OUTSIDE", encoding="utf-8")
    os.symlink(outside, refs / "link.txt")
    dest = tmpdir / "dest"
    with pytest.raises(ValueError, match="symlink"):
        skills.install(str(src), str(dest))


def test_studio_json_symlink(tmpdir):
    src = make_skill(tmpdir, name="SJs", description="d", subdir="sjs")
    real_manifest = tmpdir / "real_manifest.json"
    real_manifest.write_text('{"id": "ok"}', encoding="utf-8")
    os.unlink(src / "studio.json") if (src / "studio.json").exists() else None
    os.symlink(real_manifest, src / "studio.json")
    dest = tmpdir / "dest"
    with pytest.raises(ValueError, match="symlink"):
        skills.install(str(src), str(dest))


# ---------------------------------------------------------------------------
# atomic registry
# ---------------------------------------------------------------------------


def test_registry_atomic_replace(tmpdir):
    src = make_skill(
        tmpdir,
        name="AtomSkill",
        description="d",
        subdir="atom",
        studio_json={"id": "atom"},
    )
    dest = tmpdir / "dest"
    result = skills.install(str(src), str(dest))
    reg_path = dest / "registry.json"
    before = reg_path.read_bytes()
    # set_enabled should replace atomically; content must be valid JSON.
    skills.set_enabled(str(dest), result["id"], True, ["project:read"])
    after = reg_path.read_bytes()
    assert before != after
    reg = json.loads(after.decode("utf-8"))
    assert reg["skills"][result["id"]]["enabled"] is True


def test_path_traversal_source_not_dir(tmpdir):
    with pytest.raises(ValueError, match="not a directory"):
        skills.install(str(tmpdir / "nope"), str(tmpdir / "d"))


def test_install_source_missing_skill_md(tmpdir):
    d = tmpdir / "noskill"
    d.mkdir()
    with pytest.raises(ValueError, match="SKILL.md"):
        skills.install(str(d), str(tmpdir / "d"))
