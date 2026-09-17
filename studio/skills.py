"""Safe local instruction-skill registry for Continuity Studio.

A *skill* is a directory containing a ``SKILL.md`` file with YAML
frontmatter (required ``name`` and ``description``) and optionally a
``studio.json`` manifest.  This module discovers skills from roots,
installs them as immutable, content-hashed snapshots, and provides the
instructions (SKILL.md body + reference texts) of enabled skills that
match a capability.

Design goals
------------
* No imports from other studio modules (bounded, self-contained).
* Stdlib + PyYAML only.
* Copy only safe text content: ``SKILL.md`` and
  ``references/**/*.md|*.txt`` (recursive, bounded, regular files).
  No scripts, symlinks or executable permissions.
* Total copied size limited to 1 MB.
* All copied content is hashed (sha256 over relative paths + bytes).
* ``registry.json`` is updated atomically (thread lock + temp-file
  replace).
* External source is never edited.

Public API
----------
``discover(roots) -> list[dict]``
``install(source, destination_root) -> dict``
``list_installed(destination_root) -> list[dict]``
``set_enabled(destination_root, skill_id, enabled, granted_permissions) -> dict``
``instructions(destination_root, capability) -> tuple[str, list[dict]]``
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import threading
from pathlib import Path

import yaml

__all__ = [
    "discover",
    "install",
    "list_installed",
    "set_enabled",
    "instructions",
    "SUPPORTED_PERMISSIONS",
    "MAX_TOTAL_BYTES",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_PERMISSIONS = ("project:read",)
MAX_TOTAL_BYTES = 1_048_576  # 1 MB

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?\r?\n)---\r?\n?", re.DOTALL)

_REFERENCE_EXTS = {".md", ".txt"}

_registry_lock = threading.Lock()
_registry_cache: dict[str, dict] = {}
_registry_cache_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _is_safe_id(value) -> bool:
    return isinstance(value, str) and bool(ID_RE.fullmatch(value))


def _validate_string_list(value, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ValueError(f"{field} must be a list of strings")
    return list(value)


def _validate_permissions(permissions) -> list[str]:
    perms = _validate_string_list(permissions, "permissions")
    unsupported = [p for p in perms if p not in SUPPORTED_PERMISSIONS]
    if unsupported:
        raise ValueError(
            f"unsupported permission(s): {', '.join(unsupported)}; "
            f"supported: {', '.join(SUPPORTED_PERMISSIONS)}"
        )
    return perms


def _skill_dir_candidates(root: Path) -> list[Path]:
    """Yield candidate skill directories for a root.

    Accepts the root itself as a skill directory (if it contains
    SKILL.md) and its direct child directories.
    """
    candidates = []
    if (root / "SKILL.md").is_file():
        candidates.append(root)
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            if entry.is_dir() and not entry.is_symlink():
                if (entry / "SKILL.md").is_file():
                    candidates.append(entry)
    return candidates


# ---------------------------------------------------------------------------
# Frontmatter / manifest parsing
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from SKILL.md text.

    Returns (frontmatter_dict, body).  Raises ValueError on malformed
    frontmatter or missing required keys.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("SKILL.md must start with YAML frontmatter ('---')")
    raw = m.group(1)
    body = text[m.end():]
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed YAML frontmatter: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("YAML frontmatter must be a mapping")
    name = data.get("name")
    description = data.get("description")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("frontmatter 'name' is required and must be a non-empty string")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("frontmatter 'description' is required and must be a non-empty string")
    return data, body


def _parse_manifest(skill_dir: Path) -> dict:
    """Parse optional studio.json manifest, applying defaults."""
    manifest_path = skill_dir / "studio.json"
    manifest = {}
    if manifest_path.is_file():
        if manifest_path.is_symlink():
            raise ValueError("studio.json must not be a symlink")
        try:
            raw = manifest_path.read_bytes()
            manifest = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"malformed studio.json: {exc}") from exc
        if not isinstance(manifest, dict):
            raise ValueError("studio.json must be a JSON object")

    skill_id = manifest.get("id")
    version = manifest.get("version", "1.0.0")
    api_version = manifest.get("api_version", 1)
    capabilities = manifest.get("capabilities")
    permissions = manifest.get("permissions")

    if capabilities is None:
        capabilities = ["direction"]
    capabilities = _validate_string_list(capabilities, "capabilities")
    if not capabilities:
        raise ValueError("capabilities must be a non-empty list of strings")

    if permissions is None:
        permissions = ["project:read"]
    permissions = _validate_permissions(permissions)

    if not isinstance(version, str) or not version.strip():
        raise ValueError("version must be a non-empty string")
    version = version.strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9_-]+)?", version):
        raise ValueError("version must be a safe semantic version (e.g. 1.0.0)")

    if not isinstance(api_version, int) or isinstance(api_version, bool):
        raise ValueError("api_version must be an integer")
    if api_version != 1:
        raise ValueError(
            f"unsupported api_version {api_version}; supported: 1"
        )

    if skill_id is not None and not _is_safe_id(skill_id):
        raise ValueError(
            f"invalid skill id {skill_id!r}; must match {ID_RE.pattern}"
        )

    return {
        "id": skill_id,
        "version": version,
        "api_version": api_version,
        "capabilities": capabilities,
        "permissions": permissions,
    }


# ---------------------------------------------------------------------------
# Content collection and hashing
# ---------------------------------------------------------------------------


def _collect_content(skill_dir: Path) -> dict[str, bytes]:
    """Collect the safe files to copy: SKILL.md + references/**.

    Returns a dict mapping relative POSIX path -> bytes.
    Enforces: no symlinks, no executable permissions, size limit.
    """
    files: dict[str, bytes] = {}
    total = 0

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise ValueError(f"missing SKILL.md in {skill_dir}")
    if skill_md.is_symlink():
        raise ValueError("SKILL.md must not be a symlink")
    _check_file_mode(skill_md)
    data = skill_md.read_bytes()
    total += len(data)
    files["SKILL.md"] = data

    refs_dir = skill_dir / "references"
    if refs_dir.exists():
        if refs_dir.is_symlink():
            raise ValueError("references/ must not be a symlink")
        for path in sorted(refs_dir.rglob("*")):
            rel = path.relative_to(skill_dir).as_posix()
            if path.is_symlink():
                raise ValueError(f"symlink not allowed: {rel}")
            # Only files under references/
            if not rel.startswith("references/"):
                continue
            if not path.is_file():
                continue
            if path.suffix.lower() not in _REFERENCE_EXTS:
                continue
            _check_file_mode(path)
            data = path.read_bytes()
            total += len(data)
            files[rel] = data

    if total > MAX_TOTAL_BYTES:
        raise ValueError(
            f"total skill size {total} bytes exceeds limit {MAX_TOTAL_BYTES}"
        )
    return files


def _check_file_mode(path: Path) -> None:
    """Reject files with executable permissions."""
    try:
        mode = stat.S_IMODE(path.lstat().st_mode)
    except OSError:
        return
    if mode & 0o111:
        raise ValueError(f"executable permission not allowed: {path.name}")


def _hash_files(files: dict[str, bytes]) -> str:
    """Deterministic sha256 over sorted (relpath, bytes)."""
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(files[rel])
        h.update(b"\x00")
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Metadata construction
# ---------------------------------------------------------------------------


def _build_metadata(
    *,
    skill_dir: Path,
    name: str,
    description: str,
    version: str,
    capabilities: list[str],
    permissions: list[str],
    skill_id: str | None,
    files: dict[str, bytes],
    content_hash: str,
    enabled: bool = False,
    granted_permissions: list[str] | None = None,
) -> dict:
    """Build the public metadata dict for a skill."""
    if granted_permissions is None:
        granted_permissions = []
    return {
        "id": skill_id,
        "name": name,
        "description": description,
        "version": version,
        "capabilities": capabilities,
        "permissions": permissions,
        "enabled": enabled,
        "granted_permissions": granted_permissions,
        "hash": content_hash,
        "skill_dir": str(skill_dir),
    }


def _resolve_skill_id(skill_dir: Path, manifest: dict, frontmatter: dict) -> str:
    """Resolve the skill id.

    Priority: studio.json ``id`` (validated) > frontmatter ``name``
    (slugified and validated) > directory name.
    """
    if manifest.get("id") is not None:
        return manifest["id"]

    # Slugify the frontmatter name as a fallback id.
    raw = frontmatter.get("name") or skill_dir.name
    slug = re.sub(r"[^a-z0-9_-]+", "-", str(raw).lower()).strip("-")
    if _is_safe_id(slug):
        return slug
    # Fall back to directory name if it's safe.
    if _is_safe_id(skill_dir.name):
        return skill_dir.name
    raise ValueError(
        f"cannot derive a safe skill id from {skill_dir.name!r} "
        f"(name={raw!r}); provide studio.json 'id'"
    )


# ---------------------------------------------------------------------------
# Registry I/O (atomic)
# ---------------------------------------------------------------------------


def _registry_path(destination_root: Path) -> Path:
    return destination_root / "registry.json"


def _load_registry(destination_root: Path) -> dict:
    reg_path = _registry_path(destination_root)
    if not reg_path.exists():
        return {"skills": {}}
    with open(reg_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "skills" not in data:
        raise ValueError(f"corrupt registry: {reg_path}")
    if not isinstance(data["skills"], dict):
        raise ValueError(f"corrupt registry: {reg_path}")
    return data


def _save_registry(destination_root: Path, registry: dict) -> None:
    reg_path = _registry_path(destination_root)
    fd, tmp = tempfile.mkstemp(dir=str(destination_root), prefix=".registry-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, reg_path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _invalidate_registry_cache(destination_root: Path) -> None:
    key = str(destination_root.resolve())
    with _registry_cache_lock:
        _registry_cache.pop(key, None)


def _unique_skill_dir_name(
    destination_root: Path,
    base_id: str,
    version: str,
    hash_prefix: str,
) -> str:
    """Build a unique installation directory name: id-version-hashprefix.

    If the name would collide, extend with a numeric suffix so that
    different content hashes or versions can coexist.
    """
    candidate = f"{base_id}-{version}-{hash_prefix}"
    if not (destination_root / candidate).exists():
        return candidate
    n = 1
    while True:
        candidate = f"{base_id}-{version}-{hash_prefix}-{n}"
        if not (destination_root / candidate).exists():
            return candidate
        n += 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover(roots: list[str]) -> list[dict]:
    """Discover skills from the given root directories.

    Each root may itself be a skill directory (contains SKILL.md) or a
    parent containing direct-child skill directories.  Returns a list
    of metadata dicts (without registry state).
    """
    if not isinstance(roots, list):
        raise ValueError("roots must be a list of strings")
    for r in roots:
        if not isinstance(r, str):
            raise ValueError("each root must be a string")

    seen: set[str] = set()
    results: list[dict] = []
    for root_str in roots:
        root = Path(root_str)
        if not root.is_dir():
            continue
        for candidate in _skill_dir_candidates(root):
            try:
                meta = _discover_one(candidate)
            except ValueError:
                continue  # skip malformed skill dirs during discovery
            # De-duplicate by resolved path
            key = str(candidate.resolve())
            if key in seen:
                continue
            seen.add(key)
            results.append(meta)
    return results


def _discover_one(skill_dir: Path) -> dict:
    """Parse a single skill directory into metadata (no install)."""
    frontmatter, _body = _parse_frontmatter(
        (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    )
    manifest = _parse_manifest(skill_dir)
    skill_id = _resolve_skill_id(skill_dir, manifest, frontmatter)
    files = _collect_content(skill_dir)
    content_hash = _hash_files(files)
    return _build_metadata(
        skill_dir=skill_dir,
        name=frontmatter["name"],
        description=frontmatter["description"],
        version=manifest["version"],
        capabilities=manifest["capabilities"],
        permissions=manifest["permissions"],
        skill_id=skill_id,
        files=files,
        content_hash=content_hash,
    )


def install(source: str, destination_root: str) -> dict:
    """Install a skill from ``source`` into ``destination_root``.

    Creates an immutable snapshot directory named
    ``id-version-hashprefix`` and records it in ``registry.json``.
    Returns the installed metadata dict.
    """
    src = Path(source)
    dest_root = Path(destination_root)

    if not isinstance(source, str) or not isinstance(destination_root, str):
        raise ValueError("source and destination_root must be strings")
    if not src.is_dir():
        raise ValueError(f"source is not a directory: {source}")
    if not (src / "SKILL.md").is_file():
        raise ValueError(f"source does not contain SKILL.md: {source}")

    dest_root.mkdir(parents=True, exist_ok=True)

    # Parse source (raises ValueError on problems).
    frontmatter, _body = _parse_frontmatter(
        (src / "SKILL.md").read_text(encoding="utf-8")
    )
    manifest = _parse_manifest(src)
    skill_id = _resolve_skill_id(src, manifest, frontmatter)
    files = _collect_content(src)
    content_hash = _hash_files(files)

    hash_prefix = content_hash[:12]
    with _registry_lock:
        dir_name = _unique_skill_dir_name(dest_root, skill_id, manifest["version"], hash_prefix)
        install_dir = dest_root / dir_name
        # Copy files into the snapshot dir.
        install_dir.mkdir(parents=True, exist_ok=True)
        for rel, data in files.items():
            target = install_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            # Write with 0o644 (no exec bits).
            target.write_bytes(data)
            target.chmod(0o644)

        # Build registry entry.
        registry = _load_registry(dest_root)
        registry["skills"][dir_name] = {
            "id": skill_id,
            "name": frontmatter["name"],
            "description": frontmatter["description"],
            "version": manifest["version"],
            "capabilities": manifest["capabilities"],
            "permissions": manifest["permissions"],
            "enabled": False,
            "granted_permissions": [],
            "hash": content_hash,
            "skill_dir": dir_name,
        }
        _save_registry(dest_root, registry)
        _invalidate_registry_cache(dest_root)

    return _build_metadata(
        skill_dir=install_dir,
        name=frontmatter["name"],
        description=frontmatter["description"],
        version=manifest["version"],
        capabilities=manifest["capabilities"],
        permissions=manifest["permissions"],
        skill_id=dir_name,
        files=files,
        content_hash=content_hash,
        enabled=False,
        granted_permissions=[],
    )


def list_installed(destination_root: str) -> list[dict]:
    """List all installed skills from the registry."""
    dest_root = Path(destination_root)
    if not isinstance(destination_root, str):
        raise ValueError("destination_root must be a string")
    registry = _load_registry(dest_root)
    results = []
    for dir_name, entry in sorted(registry["skills"].items()):
        skill_dir = dest_root / dir_name
        results.append(
            _build_metadata(
                skill_dir=skill_dir,
                name=entry["name"],
                description=entry["description"],
                version=entry["version"],
                capabilities=entry["capabilities"],
                permissions=entry["permissions"],
                skill_id=dir_name,
                files={},
                content_hash=entry["hash"],
                enabled=entry.get("enabled", False),
                granted_permissions=entry.get("granted_permissions", []),
            )
        )
    return results


def set_enabled(
    destination_root: str,
    skill_id: str,
    enabled: bool,
    granted_permissions: list[str],
) -> dict:
    """Enable or disable an installed skill, granting permissions.

    ``skill_id`` is the installation directory name (the unique ``id``
    returned by ``install``).  When enabling, all permissions declared
    by the skill must be included in ``granted_permissions``.
    Returns the updated metadata dict.
    """
    dest_root = Path(destination_root)
    if not isinstance(destination_root, str):
        raise ValueError("destination_root must be a string")
    if not isinstance(skill_id, str):
        raise ValueError("skill_id must be a string")
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a bool")
    granted_permissions = _validate_string_list(granted_permissions, "granted_permissions")

    # Validate granted permissions against supported set.
    unsupported = [p for p in granted_permissions if p not in SUPPORTED_PERMISSIONS]
    if unsupported:
        raise ValueError(
            f"unsupported permission(s): {', '.join(unsupported)}; "
            f"supported: {', '.join(SUPPORTED_PERMISSIONS)}"
        )

    with _registry_lock:
        registry = _load_registry(dest_root)
        if skill_id not in registry["skills"]:
            raise ValueError(f"unknown skill_id: {skill_id!r}")
        entry = registry["skills"][skill_id]

        if enabled:
            # All declared permissions must be granted.
            required = set(entry["permissions"])
            granted = set(granted_permissions)
            missing = required - granted
            if missing:
                raise ValueError(
                    f"missing required permission(s) to enable: {', '.join(sorted(missing))}"
                )
            entry["enabled"] = True
            entry["granted_permissions"] = sorted(granted_permissions)
        else:
            entry["enabled"] = False
            entry["granted_permissions"] = sorted(granted_permissions)

        _save_registry(dest_root, registry)
        _invalidate_registry_cache(dest_root)

    skill_dir = dest_root / skill_id
    return _build_metadata(
        skill_dir=skill_dir,
        name=entry["name"],
        description=entry["description"],
        version=entry["version"],
        capabilities=entry["capabilities"],
        permissions=entry["permissions"],
        skill_id=skill_id,
        files={},
        content_hash=entry["hash"],
        enabled=entry["enabled"],
        granted_permissions=entry["granted_permissions"],
    )


def instructions(destination_root: str, capability: str, *, additional_capabilities=()) -> tuple[str, list[dict]]:
    """Return joined instruction text and provenance metadata.

    Collects all *enabled* skills whose capabilities include
    ``capability`` (or the ``'*'`` wildcard).  Each skill contributes:
    * its SKILL.md body (after frontmatter)
    * all safe reference text files (references/**/*.md|*.txt),
      each prefixed with its relative path.

    Returns ``(text, metadata_list)`` where ``metadata_list`` contains
    provenance dicts for each included skill.
    """
    dest_root = Path(destination_root)
    if not isinstance(destination_root, str):
        raise ValueError("destination_root must be a string")
    if not isinstance(capability, str) or not capability:
        raise ValueError("capability must be a non-empty string")
    requested = {capability, *additional_capabilities}
    if any(not isinstance(c, str) or not c for c in requested):
        raise ValueError('capabilities must be non-empty strings')

    registry = _load_registry(dest_root)
    chunks: list[str] = []
    meta_list: list[dict] = []

    for dir_name in sorted(registry["skills"]):
        entry = registry["skills"][dir_name]
        if not entry.get("enabled"):
            continue
        caps = entry.get("capabilities", [])
        if not requested.intersection(caps) and "*" not in caps:
            continue

        skill_dir = dest_root / dir_name
        files = _collect_content(skill_dir)
        if _hash_files(files) != entry["hash"]:
            raise ValueError(f"Installed skill integrity check failed: {dir_name}")
        # Read SKILL.md body
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8")
        _fm, body = _parse_frontmatter(text)

        chunk_parts: list[str] = []
        chunk_parts.append(f"## Skill: {entry['name']} ({entry['id']})")
        chunk_parts.append(body.strip())

        # Append reference texts.
        refs_dir = skill_dir / "references"
        if refs_dir.is_dir():
            for path in sorted(refs_dir.rglob("*")):
                rel = path.relative_to(skill_dir).as_posix()
                if path.is_file() and path.suffix.lower() in _REFERENCE_EXTS:
                    ref_text = path.read_text(encoding="utf-8")
                    chunk_parts.append(f"### Reference: {rel}\n\n{ref_text.strip()}")

        chunks.append("\n\n".join(chunk_parts))
        meta_list.append(
            {
                "id": dir_name,
                "name": entry["name"],
                "version": entry["version"],
                "hash": entry["hash"],
                "skill_dir": dir_name,
                "capabilities": entry["capabilities"],
                "permissions": entry["permissions"],
            }
        )

    return "\n\n---\n\n".join(chunks), meta_list
