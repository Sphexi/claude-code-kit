#!/usr/bin/env python3
"""Generate the marketplace plugin trees, marketplace.json, notices and catalogue; build Cowork zips.

Exit codes: 0 success, 1 drift (``--check``) or stale shared blocks, 2 build error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inline_shared  # noqa: E402
from bundles import BUILTIN_AGENTS, BUNDLES, CORE, EXTRAS, Bundle  # noqa: E402

PLUGIN_DIRNAME = ".claude-plugin"
PLUGIN_MANIFEST = "plugin.json"
CLAUDE_DIR = "claude"
VENDOR_DIR = "vendor"
PLUGINS_DIR = "plugins"
TEMPLATES_DIR = Path("build") / "templates"
KIT_FILE = Path("build") / "kit.json"
MARKETPLACE_FILE = f"{PLUGIN_DIRNAME}/marketplace.json"
NOTICES_FILE = "THIRD_PARTY_NOTICES.md"
CATALOGUE_FILE = "docs/plugins.md"
MANIFEST_FILE = "claude/plugins.manifest.json"

HOOK_LIMIT = 9500
HOOK_TITLE_RESERVE = "# Code Standards (part 99 of 99) — applied for this session\n\n"
DEFAULT_LEVEL = "terse-full"

#: Pinned zip timestamp: the DOS epoch, the earliest a zip entry can express.
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

#: ``(file stem, exact source text, replacement)`` rewrites applied when an output style
#: becomes a Cowork level file. Each must match or the build fails.
LEVEL_SUBSTITUTIONS: tuple[tuple[str, str, str], ...] = ()

#: Root entries a merged bundle member may carry.
BUNDLEABLE = frozenset({".claude-plugin", "agents", "commands", "skills", "UPSTREAM.md",
                        "README.md", "LICENSE"})

NOISE = frozenset({"__pycache__", ".DS_Store"})

SUBAGENT_REF = re.compile(r'subagent_type\s*[=:]\s*"([A-Za-z0-9:_-]+)"')
RESERVED_PREFIXES = ("claude-", "anthropic-", "anthropics-", "cc-plugin-")

Index = dict[str, dict[str, Path]]
Files = dict[str, bytes]


class BuildError(Exception):
    """The outputs could not be generated."""


def repo_root() -> Path:
    """Return the repository root, resolved from this file."""
    return Path(__file__).resolve().parents[1]


def text_bytes(text: str) -> bytes:
    """Encode text as UTF-8 with LF line endings."""
    return text.replace("\r\n", "\n").encode("utf-8")


def json_bytes(data: object) -> bytes:
    """Encode JSON with two-space indent, real Unicode and a trailing newline."""
    return text_bytes(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path) -> dict:
    """Load a JSON file, raising ``BuildError`` when it is missing or invalid."""
    if not path.is_file():
        raise BuildError(f"missing file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BuildError(f"{path}: invalid JSON — {exc}") from exc


def read_template(root: Path, name: str) -> str:
    """Return the text of ``build/templates/<name>``."""
    path = root / TEMPLATES_DIR / name
    if not path.is_file():
        raise BuildError(f"missing template: {path}")
    return path.read_text(encoding="utf-8")


def fill(template: str, values: dict[str, str], name: str) -> str:
    """Replace ``{{TOKEN}}`` placeholders and fail on any left unfilled."""
    for token, value in values.items():
        template = template.replace("{{" + token + "}}", value)
    if "{{" in template:
        raise BuildError(f"{name}: unfilled placeholder near {template[template.index('{{'):][:40]!r}")
    return template


def strip_frontmatter(text: str) -> str:
    """Return `text` without a leading YAML frontmatter block."""
    if not text.startswith("---"):
        return text
    lines = text.splitlines(keepends=True)
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            return "".join(lines[index + 1:]).lstrip("\n")
    return text


def frontmatter_field(text: str, key: str) -> str | None:
    """Return a top-level frontmatter value, or ``None``."""
    if not text.startswith("---\n"):
        return None
    for line in text.split("\n")[1:]:
        if line.rstrip() == "---":
            return None
        if line.startswith(f"{key}:"):
            return line[len(key) + 1:].strip().strip("'\"") or None
    return None


def apply_substitutions(stem: str, text: str) -> str:
    """Apply the declared level substitutions for `stem`, failing when one no longer matches."""
    for target, old, new in LEVEL_SUBSTITUTIONS:
        if target != stem:
            continue
        if old not in text:
            raise BuildError(f"{stem}: declared substitution no longer matches: {old!r}")
        text = text.replace(old, new)
    return text


# --------------------------------------------------------------------------- #
# hook payload chunking
# --------------------------------------------------------------------------- #


def split_sections(text: str) -> list[str]:
    """Split at lines starting ``## `` outside code fences; the preamble joins the first section."""
    sections: list[list[str]] = [[]]
    in_fence = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if line.startswith("## ") and not in_fence and any(sections[-1]):
            sections.append([])
        sections[-1].append(line)
    return ["".join(s) for s in sections if s]


def chunk_text(text: str, title: str, limit: int = HOOK_LIMIT) -> list[str]:
    """Pack whole ``## `` sections into chunks of at most `limit` characters, each titled."""
    reserve = len(HOOK_TITLE_RESERVE.replace("Code Standards", title))
    budget = limit - reserve
    packed: list[str] = []
    for section in split_sections(text.strip("\n") + "\n"):
        if len(section) > budget:
            heading = section.splitlines()[0]
            raise BuildError(f"section {heading!r} is {len(section)} characters; "
                             f"the per-chunk limit is {budget}")
        if packed and len(packed[-1]) + len(section) <= budget:
            packed[-1] += section
        else:
            packed.append(section)
    total = len(packed)
    return [f"# {title} (part {n} of {total}) — applied for this session\n\n{body}"
            for n, body in enumerate(packed, start=1)]


def hooks_json(filenames: list[str], description: str) -> bytes:
    """Render a SessionStart hook file with one ``cat`` command per payload file."""
    commands = [{"type": "command", "command": f'cat "${{CLAUDE_PLUGIN_ROOT}}/hooks/{name}"'}
                for name in filenames]
    return json_bytes({"description": description,
                       "hooks": {"SessionStart": [{"hooks": commands}]}})


def hook_files(prefix: str, chunks: list[str]) -> Files:
    """Name chunks ``hooks/<prefix>-N.md``."""
    return {f"hooks/{prefix}-{n}.md": text_bytes(chunk) for n, chunk in enumerate(chunks, start=1)}


# --------------------------------------------------------------------------- #
# validation and indexing
# --------------------------------------------------------------------------- #


def vendor_dir(root: Path) -> Path:
    """Return ``claude/vendor``."""
    return root / CLAUDE_DIR / VENDOR_DIR


def validate_bundles(root: Path) -> None:
    """Fail unless the bundle table is consistent with ``claude/vendor/``."""
    vendor = vendor_dir(root)
    on_disk = {p.name for p in vendor.iterdir() if p.is_dir()} if vendor.is_dir() else set()
    names = [b.name for b in BUNDLES]
    problems: list[str] = []
    if len(set(names)) != len(names):
        problems.append(f"duplicate bundle names: {names}")
    if CORE not in names:
        problems.append("no core bundle")
    assigned: dict[str, str] = {}
    for bundle in BUNDLES:
        if bundle.name.startswith(RESERVED_PREFIXES):
            problems.append(f"{bundle.name}: reserved plugin-name prefix")
        problems += [f"{bundle.name}: depends on unknown bundle {d!r}"
                     for d in bundle.depends_on if d not in names]
        for plugin in bundle.plugins:
            if plugin in assigned:
                problems.append(f"{plugin}: in both {assigned[plugin]} and {bundle.name}")
            elif plugin not in on_disk:
                problems.append(f"{bundle.name}: vendored plugin {plugin!r} does not exist")
            assigned[plugin] = bundle.name
    problems += [f"{p}: in EXTRAS and in bundle {assigned[p]}" for p in EXTRAS if p in assigned]
    problems += [f"{p}: vendored but in no bundle and not in EXTRAS"
                 for p in sorted(on_disk - set(assigned) - set(EXTRAS))]
    if problems:
        raise BuildError("bundle table is inconsistent:\n  " + "\n  ".join(problems))


def own_skill_dirs(root: Path) -> list[Path]:
    """Return the authored skill directories."""
    skills = root / CLAUDE_DIR / "skills"
    return sorted(p for p in skills.iterdir() if p.is_dir()) if skills.is_dir() else []


def own_agent_files(root: Path) -> list[Path]:
    """Return the authored agent files."""
    agents = root / CLAUDE_DIR / "agents"
    return sorted(agents.glob("*.md")) if agents.is_dir() else []


def bundle_index(root: Path, bundle: Bundle) -> Index:
    """Map each component kind to ``{shipped name: source}``, failing on name collisions."""
    vendor = vendor_dir(root)
    index: Index = {"agents": {}, "commands": {}, "skills": {}}
    collisions: list[str] = []

    def claim(kind: str, key: str, path: Path) -> None:
        folded = {k.casefold(): k for k in index[kind]}
        prior = folded.get(key.casefold())
        if prior is not None:
            collisions.append(f"{kind[:-1]} {key}: {index[kind][prior]} and {path}")
        index[kind][key] = path

    if bundle.name == CORE:
        for path in own_agent_files(root):
            claim("agents", frontmatter_field(path.read_text(encoding="utf-8"), "name") or path.stem,
                  path)
        for path in own_skill_dirs(root):
            claim("skills", path.name, path)

    for plugin in bundle.plugins:
        source = vendor / plugin
        extra = sorted(p.name for p in source.iterdir()
                       if p.name not in BUNDLEABLE and not p.name.startswith("NOTICE"))
        if extra:
            raise BuildError(f"{bundle.name}: {plugin} carries {extra}, which a merged bundle "
                             "cannot relocate; move it to EXTRAS")
        for path in sorted((source / "agents").glob("*.md")):
            name = frontmatter_field(path.read_text(encoding="utf-8"), "name")
            if not name:
                raise BuildError(f"{plugin}/agents/{path.name} declares no name")
            claim("agents", name, path)
        for path in sorted((source / "commands").glob("*.md")):
            prior = index["commands"].get(path.stem)
            if prior is not None and prior.read_bytes() != path.read_bytes():
                collisions.append(f"command {path.stem}: {prior} and {path}")
            index["commands"].setdefault(path.stem, path)
        skills = source / "skills"
        for path in sorted(p for p in skills.iterdir() if p.is_dir()) if skills.is_dir() else []:
            claim("skills", path.name, path)
    if collisions:
        raise BuildError(f"{bundle.name}: name collision inside the bundle:\n  "
                         + "\n  ".join(collisions))
    return index


def agent_references(index: Index) -> dict[str, set[str]]:
    """Return every ``subagent_type`` a bundle's files name, mapped to the files naming it."""
    files = list(index["agents"].values()) + list(index["commands"].values())
    for skill in index["skills"].values():
        files += sorted(skill.rglob("*.md"))
    refs: dict[str, set[str]] = {}
    for path in files:
        for ref in SUBAGENT_REF.findall(path.read_text(encoding="utf-8")):
            refs.setdefault(ref, set()).add(path.name)
    return refs


def check_references(indexes: dict[str, Index]) -> None:
    """Fail when a bundle names an agent outside itself, its dependencies, core and the built-ins."""
    provided = {name: set(index["agents"]) for name, index in indexes.items()}
    problems: list[str] = []
    for bundle in BUNDLES:
        reachable = set(BUILTIN_AGENTS) | provided[bundle.name] | provided.get(CORE, set())
        for dep in bundle.depends_on:
            reachable |= provided.get(dep, set())
        for ref, where in sorted(agent_references(indexes[bundle.name]).items()):
            if ref in reachable or ref.split(":", 1)[-1] in reachable:
                continue
            owners = sorted(n for n, agents in provided.items() if ref.split(":", 1)[-1] in agents)
            hint = f"; add {owners} to depends_on" if owners else "; no bundle provides it"
            problems.append(f"{bundle.name}: {ref} (in {', '.join(sorted(where))}){hint}")
    if problems:
        raise BuildError("unresolved subagent references:\n  " + "\n  ".join(problems))


# --------------------------------------------------------------------------- #
# plugin trees
# --------------------------------------------------------------------------- #


def tree_files(source: Path, dest: str) -> Files:
    """Read every file under `source` into ``{dest/relative: bytes}``, skipping caches."""
    files: Files = {}
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        if not path.is_file() or any(part in NOISE for part in rel.parts) or path.suffix == ".pyc":
            continue
        files[f"{dest}/{rel.as_posix()}"] = path.read_bytes()
    return files


def spdx_sort_key(spdx: str) -> tuple[bool, str]:
    """Order MIT first, then the rest alphabetically."""
    return (spdx != "MIT", spdx)


def license_expression(bundle: Bundle, manifest: dict, kit: dict) -> str:
    """Return the SPDX ``AND`` of the kit's license and every member's."""
    by_name = {p["name"]: p["license"] for p in manifest["plugins"]}
    found = {kit["license"]} | {by_name[p] for p in bundle.plugins}
    return " AND ".join(sorted(found, key=spdx_sort_key))


def plugin_json(bundle: Bundle, manifest: dict, kit: dict) -> bytes:
    """Render a generated ``plugin.json`` (dependencies live on the marketplace entry)."""
    keywords = sorted(set(bundle.plugins) | (set(bundle.tags) if bundle.name == CORE else set()))
    return json_bytes({
        "name": bundle.name,
        "version": kit["version"],
        "description": bundle.description,
        "author": kit["owner"],
        "homepage": kit["homepage"],
        "repository": kit["repository"],
        "license": license_expression(bundle, manifest, kit),
        "keywords": keywords,
    })


def notice_files(root: Path, bundle: Bundle) -> Files:
    """Copy each member's ``LICENSE`` and ``UPSTREAM.md`` into ``notices/<member>/``."""
    files: Files = {}
    for plugin in bundle.plugins:
        for name in ("LICENSE", "UPSTREAM.md"):
            path = vendor_dir(root) / plugin / name
            if not path.is_file():
                raise BuildError(f"{bundle.name}: {plugin} has no {name}")
            files[f"notices/{plugin}/{name}"] = path.read_bytes()
    return files


def dependency_text(bundle: Bundle) -> str:
    """Describe a bundle's declared dependencies for its README."""
    if not bundle.depends_on:
        return "This plugin has no dependencies."
    names = ", ".join(f"`{d}`" for d in bundle.depends_on)
    return (f"**Depends on:** {names}. Some commands call an agent that lives in another plugin "
            "because upstream duplicates were collapsed to one canonical copy; without those "
            "plugins installed, those steps have no agent to call.")


def member_lines(bundle: Bundle, index: Index) -> list[str]:
    """List each member plugin with the components it contributes."""
    by_plugin: dict[str, dict[str, list[str]]] = {}
    for kind, entries in index.items():
        for name, path in entries.items():
            owner = next((p for p in bundle.plugins if f"/{p}/" in path.as_posix() + "/"), None)
            if owner:
                by_plugin.setdefault(owner, {}).setdefault(kind, []).append(name)
    lines = []
    for plugin in bundle.plugins:
        parts = by_plugin.get(plugin, {})
        detail = "; ".join(f"{kind}: " + ", ".join(f"`{n}`" for n in sorted(parts[kind]))
                           for kind in ("agents", "commands", "skills") if parts.get(kind))
        lines.append(f"- **{plugin}** — {detail or 'no components'}")
    return lines


def common_values(bundle: Bundle, manifest: dict, kit: dict) -> dict[str, str]:
    """Return the placeholders shared by both plugin README templates."""
    return {
        "NAME": bundle.name,
        "VERSION": kit["version"],
        "DESCRIPTION": bundle.description,
        "MARKETPLACE": kit["marketplace"],
        "REPOSITORY": kit["repository"],
        "LICENSE": license_expression(bundle, manifest, kit),
    }


def agent_model(path: Path) -> str:
    """Return an agent file's declared model."""
    return frontmatter_field(path.read_text(encoding="utf-8"), "model") or "inherit"


def core_hook_parts(root: Path) -> tuple[list[str], Files]:
    """Chunk the code standards and return the hook file names with their contents."""
    source = root / "shared" / "code-standards.md"
    if not source.is_file():
        raise BuildError(f"missing code standards source: {source}")
    files = hook_files("code-standards", chunk_text(source.read_text(encoding="utf-8"),
                                                    "Code Standards"))
    return [Path(name).name for name in files], files


def core_files(root: Path, bundle: Bundle, index: Index, manifest: dict, kit: dict) -> Files:
    """Compose the core plugin: authored agents, skills and styles plus the standards hook."""
    files: Files = {f"{PLUGIN_DIRNAME}/{PLUGIN_MANIFEST}": plugin_json(bundle, manifest, kit)}
    agents = own_agent_files(root)
    if not agents:
        raise BuildError(f"no agent definitions under {root / CLAUDE_DIR / 'agents'}")
    for path in agents:
        files[f"agents/{path.name}"] = path.read_bytes()
    for name, path in sorted(index["skills"].items()):
        files.update(tree_files(path, f"skills/{name}"))
    styles = sorted((root / CLAUDE_DIR / "output-styles").glob("*.md"))
    if not styles:
        raise BuildError(f"no output styles under {root / CLAUDE_DIR / 'output-styles'}")
    for path in styles:
        files[f"output-styles/{path.name}"] = path.read_bytes()
    names, hooks = core_hook_parts(root)
    files.update(hooks)
    files["hooks/hooks.json"] = hooks_json(
        names, "Applies the kit's comment and test standards at session start.")
    files.update(notice_files(root, bundle))

    own = [p.name for p in own_skill_dirs(root)]
    vendored = sorted(set(index["skills"]) - set(own))
    values = common_values(bundle, manifest, kit) | {
        "AGENT_COUNT": str(len(agents)),
        "AGENT_LIST": "\n".join(f"- `{p.stem}` ({agent_model(p)})" for p in agents),
        "SKILL_COUNT": str(len(index["skills"])),
        "OWN_SKILL_LIST": "\n".join(f"- `{n}`" for n in own),
        "VENDOR_SKILL_LIST": ", ".join(f"`{n}`" for n in vendored),
        "STYLE_COUNT": str(len(styles)),
        "HOOK_PARTS": "one file" if len(names) == 1 else f"{len(names)} files",
        "BUNDLE_LIST": "\n".join(f"- **{b.name}** — {b.description}"
                                 for b in BUNDLES if b.name != CORE),
    }
    files["README.md"] = text_bytes(fill(read_template(root, "README.core.md"), values,
                                         "README.core.md"))
    files["LICENSE"] = (root / "LICENSE").read_bytes()
    return files


def bundle_files(root: Path, bundle: Bundle, index: Index, manifest: dict, kit: dict) -> Files:
    """Compose one non-core plugin from its members' agents, commands and skills."""
    files: Files = {f"{PLUGIN_DIRNAME}/{PLUGIN_MANIFEST}": plugin_json(bundle, manifest, kit)}
    for name, path in index["agents"].items():
        files[f"agents/{name}.md"] = path.read_bytes()
    for name, path in index["commands"].items():
        files[f"commands/{name}.md"] = path.read_bytes()
    for name, path in index["skills"].items():
        files.update(tree_files(path, f"skills/{name}"))
    files.update(notice_files(root, bundle))
    values = common_values(bundle, manifest, kit) | {
        "DEPENDS": dependency_text(bundle),
        "AGENT_COUNT": str(len(index["agents"])),
        "COMMAND_COUNT": str(len(index["commands"])),
        "SKILL_COUNT": str(len(index["skills"])),
        "PLUGIN_COUNT": str(len(bundle.plugins)),
        "PLUGIN_LIST": "\n".join(member_lines(bundle, index)),
    }
    files["README.md"] = text_bytes(fill(read_template(root, "README.bundle.md"), values,
                                         "README.bundle.md"))
    files["LICENSE"] = (root / "LICENSE").read_bytes()
    return files


# --------------------------------------------------------------------------- #
# marketplace.json, notices, catalogue
# --------------------------------------------------------------------------- #


def marketplace_json(kit: dict) -> bytes:
    """Render ``.claude-plugin/marketplace.json`` from the bundle table and ``kit.json``."""
    entries: list[dict] = []
    for bundle in BUNDLES:
        entry: dict = {
            "name": bundle.name,
            "source": f"./{PLUGINS_DIR}/{bundle.name}",
            "description": bundle.description,
            "category": bundle.category,
            "tags": list(bundle.tags),
        }
        if bundle.depends_on:
            entry["dependencies"] = list(bundle.depends_on)
        entries.append(entry)
    entries += [dict(e) for e in kit.get("external", [])]
    return json_bytes({
        "name": kit["marketplace"],
        "description": kit["description"],
        "version": kit["version"],
        "owner": kit["owner"],
        "plugins": entries,
    })


def check_marketplace(kit: dict) -> None:
    """Fail when a generated marketplace entry would not install."""
    seen: set[str] = set()
    for bundle in BUNDLES:
        name = bundle.name
        if name.startswith(RESERVED_PREFIXES):
            raise BuildError(f"{name}: reserved plugin-name prefix")
        seen.add(name)
    for ext in kit.get("external", []):
        if ext["name"] in seen:
            raise BuildError(f"external entry {ext['name']!r} duplicates a bundle name")
        if ext["name"].startswith(RESERVED_PREFIXES):
            raise BuildError(f"{ext['name']}: reserved plugin-name prefix")
        seen.add(ext["name"])
    for bundle in BUNDLES:
        for dep in bundle.depends_on:
            if dep not in seen:
                raise BuildError(f"{bundle.name}: dependency {dep!r} is not a marketplace entry")


def repo_slug(kit: dict) -> str:
    """Return ``owner/repo`` from the kit's repository URL."""
    return kit["repository"].split("github.com/", 1)[-1].strip("/")


def files_cell(items: list[str]) -> str:
    """Render a file list as a table cell."""
    return ", ".join(f"`{i}`" for i in items) if items else "—"


def notices_markdown(manifest: dict, kit: dict) -> bytes:
    """Render ``THIRD_PARTY_NOTICES.md`` from the manifest."""
    sources = manifest["upstream_sources"]
    plugins = manifest["plugins"]
    apache = [p["name"] for p in plugins if p["license"] == "Apache-2.0"]
    out = [
        "# Third-party notices",
        "",
        "<!-- Generated by build/build_plugins.py from claude/plugins.manifest.json — do not edit. -->",
        "",
        f"claude-code-kit is released under the {kit['license']} license (`LICENSE`). It redistributes the "
        "third-party plugins listed below, each under its own license. Every vendored plugin directory "
        "carries its upstream `LICENSE` and an `UPSTREAM.md` recording its source, pinned commit and "
        "local changes.",
        "",
    ]
    for key, src in sources.items():
        owned = [p for p in plugins if p["upstream_marketplace"] == key]
        licenses = ", ".join(sorted({p["license"] for p in owned}, key=spdx_sort_key))
        out += [
            f"## {src['repo'].split('github.com/', 1)[-1]}",
            "",
            f"- Repository: {src['repo']}",
            f"- Author: {src['author']}",
            f"- License: {licenses}",
            f"- Pinned commit: `{src['vendored_at']}`",
            "",
            "| Plugin | Bundle | License | Modified | Files modified | Files added |",
            "|---|---|---|---|---|---|",
        ]
        for p in sorted(owned, key=lambda p: p["name"]):
            out.append(f"| `{p['name']}` | {('`' + p['bundle'] + '`') if p['bundle'] else 'extra'} | "
                       f"{p['license']} | {'yes' if p['local_modifications'] else 'no'} | "
                       f"{files_cell(p['files_modified'])} | {files_cell(p['files_added'])} |")
        out.append("")
    out += [
        "## Apache License 2.0",
        "",
        "The following plugins are licensed under the Apache License 2.0. A copy of the license is "
        "included in each plugin's directory. Files changed from upstream carry a notice and are "
        "listed in that plugin's `UPSTREAM.md`.",
        "",
        *[f"- `{n}`" for n in sorted(apache)],
        "",
        "## Adapted content",
        "",
        "- `claude/skills/systematic-debugging` adapts the methodology of the `systematic-debugging` "
        "skill in [obra/superpowers](https://github.com/obra/superpowers) (MIT, Copyright (c) 2025 "
        "Jesse Vincent / Prime Radiant). It is a rewrite, not a copy.",
        "- The CLAUDE.md scoring rubric in the `project-architect` agent is adapted from "
        "`claude-md-management` in `anthropics/claude-plugins-official` (Apache-2.0).",
        "- The visual-direction section of the `frontend-engineer` agent is adapted from "
        "`frontend-design` in `anthropics/claude-plugins-official` (Apache-2.0).",
        "",
        "## External plugins",
        "",
        "Listed in the marketplace and not redistributed here:",
        "",
        *[f"- `{e['name']}` — {e['homepage']} ({e.get('license', 'license not recorded')})"
          for e in kit.get("external", [])],
        "",
    ]
    return text_bytes("\n".join(out))


SUMMARY_LIMIT = 200
SUMMARY_STOPS = ("\\n\\n", "\n\n", "Examples:", "<example>", "Example:")


def frontmatter_description(text: str) -> str:
    """Return the frontmatter ``description``, joining folded, literal and plain multi-line forms."""
    if not text.startswith("---\n"):
        return ""
    lines = text.split("\n")[1:]
    for i, line in enumerate(lines):
        if line.rstrip() == "---":
            return ""
        if not line.startswith("description:"):
            continue
        head = line[len("description:"):].strip()
        block = head in ("", "|", ">", "|-", ">-", "|+", ">+")
        parts = [] if block else [head]
        for follow in lines[i + 1:]:
            if follow.rstrip() == "---" or (follow and not follow[0].isspace()):
                break
            parts.append(follow.strip())
        joiner = "\n" if head.startswith("|") else " "
        return joiner.join(parts).strip().strip("'\"")
    return ""


def body_summary(text: str) -> str:
    """Return the first prose line of a document body, for files with no description."""
    for line in strip_frontmatter(text).splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "<", "```", "---", "|")):
            return stripped
    return ""


def summarise(text: str) -> str:
    """Cut a description to its opening sentences, at most ``SUMMARY_LIMIT`` characters, table-safe."""
    for stop in SUMMARY_STOPS:
        text = text.split(stop, 1)[0]
    text = " ".join(text.replace("\\n", " ").split())
    summary = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if summary and len(summary) + 1 + len(sentence) > SUMMARY_LIMIT:
            break
        summary = f"{summary} {sentence}".strip()
        if len(summary) >= 60:
            break
    if len(summary) > SUMMARY_LIMIT:
        summary = summary[:SUMMARY_LIMIT - 1].rsplit(" ", 1)[0] + "…"
    return summary.replace("|", "\\|")


def component_summary(path: Path) -> str:
    """Summarise an agent or command file, or a skill directory's ``SKILL.md``."""
    source = path / "SKILL.md" if path.is_dir() else path
    if not source.is_file():
        return ""
    text = source.read_text(encoding="utf-8")
    return summarise(frontmatter_description(text) or body_summary(text))


def component_origin(root: Path, path: Path, licenses: dict[str, dict], kit: dict) -> tuple[str, str, str]:
    """Return ``(origin, source, license)`` cells for a component path."""
    try:
        plugin = path.relative_to(vendor_dir(root)).parts[0]
    except ValueError:
        return "Custom", "this kit", kit.get("license", "MIT")
    entry = licenses[plugin]
    slug = entry["source_repo"].split("github.com/", 1)[-1]
    return "Vendored", f"`{plugin}` from [{slug}]({entry['source_repo']})", entry["license"]


def component_table(rows: list[tuple[str, str, str, str, str]]) -> list[str]:
    """Render component rows as a Markdown table."""
    out = ["| Name | What it does | Origin | Source | License |", "|---|---|---|---|---|"]
    out += [f"| {name} | {summary} | {origin} | {source} | {spdx} |"
            for name, summary, origin, source, spdx in rows]
    return out


def component_sections(root: Path, bundle: Bundle, index: Index, licenses: dict[str, dict],
                       kit: dict) -> list[str]:
    """Render one table per component kind a bundle ships."""
    out: list[str] = []
    kinds = (("Agents", "agents", "`{}`"), ("Commands", "commands", f"`/{bundle.name}:{{}}`"),
             ("Skills", "skills", "`{}`"))
    for heading, kind, label in kinds:
        if not index[kind]:
            continue
        rows = [(label.format(name), component_summary(path),
                 *component_origin(root, path, licenses, kit))
                for name, path in sorted(index[kind].items())]
        out += ["", f"### {heading}", "", *component_table(rows)]
    if bundle.name == CORE:
        styles = sorted((root / CLAUDE_DIR / "output-styles").glob("*.md"))
        rows = [(f"`{frontmatter_field(p.read_text(encoding='utf-8'), 'name') or p.stem}`",
                 component_summary(p), *component_origin(root, p, licenses, kit)) for p in styles]
        out += ["", "### Output styles", "", *component_table(rows)]
        out += ["", "### Hooks", "", *component_table([(
            "`SessionStart`",
            "Adds the comment and test standards to every session's context.",
            "Custom", "this kit", kit.get("license", "MIT"))])]
    return out


def catalogue_markdown(root: Path, kit: dict, manifest: dict, indexes: dict[str, Index]) -> bytes:
    """Render ``docs/plugins.md`` from the catalogue template."""
    licenses = {p["name"]: p for p in manifest["plugins"]}
    index_lines = [f"- [`{b.name}`](#{b.name}) — {b.description}" for b in BUNDLES]
    index_lines += [f"- `{e['name']}` — {e['description']}" for e in kit.get("external", [])]
    sections: list[str] = []
    for bundle in BUNDLES:
        index = indexes[bundle.name]
        counts = ", ".join(f"{len(index[k])} {k}" for k in ("agents", "commands", "skills")
                           if index[k])
        lines = [f"## {bundle.name}", "", bundle.description, "",
                 f"- Install: `/plugin install {bundle.name}@{kit['marketplace']}`",
                 f"- Dependencies: {', '.join(f'`{d}`' for d in bundle.depends_on) or 'none'}",
                 f"- License: {license_expression(bundle, manifest, kit)}",
                 f"- Contents: {counts}"]
        lines += component_sections(root, bundle, index, licenses, kit)
        lines += ["", "### Upstream plugins", "",
                  "| Upstream plugin | Source | License | Modified |", "|---|---|---|---|"]
        for plugin in bundle.plugins:
            entry = licenses[plugin]
            lines.append(f"| `{plugin}` | {entry['source_repo']} | {entry['license']} | "
                         f"{'yes' if entry['local_modifications'] else 'no'} |")
        sections.append("\n".join(lines))
    extras = "\n".join(f"- `{name}` — {why}" for name, why in sorted(EXTRAS.items()))
    external = "\n".join(
        f"- `{e['name']}` — {e['description']} Installed from {e['homepage']}." for e in kit.get("external", [])
    )
    values = {
        "VERSION": kit["version"],
        "REPOSITORY_SLUG": repo_slug(kit),
        "MARKETPLACE": kit["marketplace"],
        "INDEX": "\n".join(index_lines),
        "PLUGIN_SECTIONS": "\n\n".join(sections),
        "EXTRAS": extras,
        "EXTERNAL": external or "None.",
    }
    return text_bytes(fill(read_template(root, "plugins-catalogue.md"), values,
                           "plugins-catalogue.md"))


PLUGINS_README = """# plugins

Generated by `build/build_plugins.py` from `claude/`, `shared/` and `build/kit.json`. Do not edit:
change the source and regenerate. See `docs/architecture.md`.
"""


def generate(root: Path) -> tuple[Files, dict[str, Files]]:
    """Return every generated file keyed by repo-relative path, and each plugin's own tree."""
    kit = read_json(root / KIT_FILE)
    manifest = read_json(root / MANIFEST_FILE)
    validate_bundles(root)
    check_marketplace(kit)
    indexes = {b.name: bundle_index(root, b) for b in BUNDLES}
    check_references(indexes)

    outputs: Files = {f"{PLUGINS_DIR}/README.md": text_bytes(PLUGINS_README)}
    trees: dict[str, Files] = {}
    for bundle in BUNDLES:
        builder = core_files if bundle.name == CORE else bundle_files
        tree = builder(root, bundle, indexes[bundle.name], manifest, kit)
        if any(name.split("/", 1)[0] == "bin" for name in tree):
            raise BuildError(f"{bundle.name}: a top-level bin/ is refused by Cowork")
        trees[bundle.name] = tree
        outputs.update({f"{PLUGINS_DIR}/{bundle.name}/{rel}": data for rel, data in tree.items()})
    outputs[MARKETPLACE_FILE] = marketplace_json(kit)
    outputs[NOTICES_FILE] = notices_markdown(manifest, kit)
    outputs[CATALOGUE_FILE] = catalogue_markdown(root, kit, manifest, indexes)
    return outputs, trees


# --------------------------------------------------------------------------- #
# writing and checking
# --------------------------------------------------------------------------- #


def existing_plugin_files(root: Path) -> set[str]:
    """Return every file currently under ``plugins/`` as a repo-relative path."""
    base = root / PLUGINS_DIR
    if not base.is_dir():
        return set()
    return {p.relative_to(root).as_posix() for p in base.rglob("*") if p.is_file()}


def compare(root: Path, outputs: Files) -> tuple[list[str], list[str], list[str]]:
    """Return ``(stale, missing, extra)`` repo-relative paths."""
    stale, missing = [], []
    for rel, data in sorted(outputs.items()):
        path = root / rel
        if not path.is_file():
            missing.append(rel)
        elif path.read_bytes() != data:
            stale.append(rel)
    extra = sorted(existing_plugin_files(root) - set(outputs))
    return stale, missing, extra


def write_outputs(root: Path, outputs: Files) -> list[str]:
    """Write every output, delete unproduced files under ``plugins/``; return the paths removed."""
    for rel, data in sorted(outputs.items()):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    removed = sorted(existing_plugin_files(root) - set(outputs))
    for rel in removed:
        (root / rel).unlink()
    base = root / PLUGINS_DIR
    for directory in sorted((p for p in base.rglob("*") if p.is_dir()), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()
    return removed


# --------------------------------------------------------------------------- #
# Cowork zips
# --------------------------------------------------------------------------- #


def level_files(root: Path) -> dict[str, str]:
    """Derive the Cowork level texts from the output styles."""
    styles = sorted((root / CLAUDE_DIR / "output-styles").glob("*.md"))
    if not styles:
        raise BuildError("no output styles to derive levels from")
    return {s.stem: apply_substitutions(s.stem, strip_frontmatter(s.read_text(encoding="utf-8")))
            for s in styles}


def cowork_core_files(root: Path, core: Files) -> Files:
    """Return the core tree plus the Cowork-only terseness skill and session-rules hook."""
    header = root / "cowork" / "hooks" / "session-rules.header.md"
    skill = root / "cowork" / "skills" / "terseness"
    if not header.is_file() or not skill.is_dir():
        raise BuildError("cowork/ overlay is incomplete")
    levels = level_files(root)
    if DEFAULT_LEVEL not in levels:
        raise BuildError(f"default level {DEFAULT_LEVEL!r} has no output style")

    files = dict(core)
    files.update(tree_files(skill, "skills/terseness"))
    for stem, body in levels.items():
        files[f"skills/terseness/levels/{stem}.md"] = text_bytes(body)

    session = header.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + levels[DEFAULT_LEVEL].lstrip()
    session_files = hook_files("session-rules", chunk_text(session, "Response Style"))
    files.update(session_files)
    standards = sorted((n for n in core if re.fullmatch(r"hooks/code-standards-\d+\.md", n)),
                       key=lambda n: int(re.findall(r"\d+", n)[-1]))
    files["hooks/hooks.json"] = hooks_json(
        [Path(n).name for n in standards] + [Path(n).name for n in session_files],
        "Applies the kit's comment and test standards and the default terseness level at session start.")
    return files


def write_zip(files: Files, destination: Path) -> None:
    """Write a reproducible zip: sorted entries, pinned timestamps, mode 0644."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])


def zip_name(kit: dict, bundle: str) -> str:
    """Return a plugin's zip filename."""
    return f"{kit['zip_prefix']}-{bundle}-{kit['version']}.zip"


# --------------------------------------------------------------------------- #
# command line
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="build_plugins.py",
        description="Generate plugins/, marketplace.json, notices and the catalogue; build Cowork zips.")
    parser.add_argument("--check", action="store_true",
                        help="compare against the committed outputs; write nothing; exit 1 on drift")
    parser.add_argument("--zip", action="store_true", dest="make_zip",
                        help="check for drift, then write one Cowork zip per plugin")
    parser.add_argument("--version", default=None, metavar="X.Y.Z",
                        help="with --zip: must equal build/kit.json version (a leading 'v' is stripped)")
    parser.add_argument("--output-dir", type=Path, default=None, metavar="DIR",
                        help="with --zip: destination directory (default: dist/)")
    parser.add_argument("--bundle", action="append", default=None, metavar="NAME",
                        help="with --zip: only this plugin (repeatable)")
    parser.add_argument("--repo-root", type=Path, default=None, metavar="PATH",
                        help="repository root; defaults to the parent of build/")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the generator and return the process exit code."""
    args = build_parser().parse_args(argv)
    root = (args.repo_root or repo_root()).resolve()

    shared = inline_shared.main(["--check", "--repo-root", str(root)])
    if shared:
        print("error: shared blocks are stale; run python build/inline_shared.py", file=sys.stderr)
        return 1 if shared == 1 else 2

    try:
        outputs, trees = generate(root)
        kit = read_json(root / KIT_FILE)
        if args.make_zip and args.version is not None and args.version.lstrip("v") != kit["version"]:
            raise BuildError(f"--version {args.version!r} differs from build/kit.json "
                             f"version {kit['version']!r}")
        if args.bundle and set(args.bundle) - set(trees):
            raise BuildError(f"unknown plugin(s): {sorted(set(args.bundle) - set(trees))}")
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.check or args.make_zip:
        stale, missing, extra = compare(root, outputs)
        for label, paths in (("stale", stale), ("missing", missing), ("extra", extra)):
            for rel in paths:
                print(f"{label}: {rel}", file=sys.stderr)
        if stale or missing or extra:
            return 1
        if args.check:
            print(f"ok: {len(outputs)} generated file(s) match")
            return 0
        out_dir = (args.output_dir or root / "dist").resolve()
        try:
            for name in args.bundle or list(trees):
                files = cowork_core_files(root, trees[name]) if name == CORE else trees[name]
                destination = out_dir / zip_name(kit, name)
                write_zip(files, destination)
                print(f"built: {destination.name} ({destination.stat().st_size / 1024:.0f} KiB)")
        except BuildError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0

    removed = write_outputs(root, outputs)
    print(f"wrote {len(outputs)} generated file(s); removed {len(removed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
