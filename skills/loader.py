"""SkillLoader — scan, parse, and validate SKILL.md files.

SkillLoader discovers all SKILL.md files under a root directory,
parses their YAML frontmatter, validates required fields, and returns
structured Skill objects.

Usage as CLI:

    uv run python -m skills.loader /path/to/skills
    uv run python -m skills.loader /path/to/skills --validate-only
"""

from __future__ import annotations

import os
import re
import sys
import pathlib
import argparse
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml


# --- Constants ---

SKILL_FILENAME = "SKILL.md"
MAX_DESCRIPTION_LENGTH = 1024
MAX_SKILL_CONTENT_CHARS = 100000
MAX_NAME_LENGTH = 64

REQUIRED_FRONTMATTER_FIELDS = frozenset({"name", "description"})
RECOMMENDED_FRONTMATTER_FIELDS = frozenset({"version", "author", "license", "metadata"})
EXPECTED_SECTIONS = frozenset({"## Overview", "## When to Use", "## Common Pitfalls", "## Verification Checklist"})


# --- Types ---


@dataclass
class SkillValidationError:
    field: str
    message: str


@dataclass
class Skill:
    name: str
    description: str
    file_path: str
    category: str
    raw_frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    version: str = ""
    author: str = ""
    license: str = ""
    tags: list[str] = field(default_factory=list)
    related_skills: list[str] = field(default_factory=list)
    errors: list[SkillValidationError] = field(default_factory=list)
    warnings: list[SkillValidationError] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0


# --- Parser & Validator ---


class SkillLoader:
    def __init__(self, root_dir: str = "") -> None:
        self._root = pathlib.Path(root_dir or str(pathlib.Path(__file__).resolve().parent)).resolve()

    def scan(self) -> list[Skill]:
        skills = []
        if not self._root.is_dir():
            print(f"Skills directory not found: {self._root}", file=sys.stderr)
            return skills
        for path in sorted(self._root.rglob(SKILL_FILENAME)):
            skill = self._parse_file(path)
            skills.append(skill)
        return skills

    def _parse_file(self, path: pathlib.Path) -> Skill:
        raw = path.read_text(encoding="utf-8")
        category = path.parent.parent.name if path.parent.parent != self._root else ""
        skill = Skill(name="", description="", file_path=str(path), category=category)

        if not raw.startswith("---"):
            skill.errors.append(SkillValidationError("file", "File must start with dashes and no leading blank line"))
            return skill

        if len(raw) > MAX_SKILL_CONTENT_CHARS:
            skill.warnings.append(SkillValidationError("size", f"File exceeds {MAX_SKILL_CONTENT_CHARS:,} chars"))

        m = re.search(r'\n---\s*\n', raw[3:])
        if not m:
            skill.errors.append(SkillValidationError("frontmatter", "No closing dashes found for frontmatter"))
            return skill

        fm_end = m.start() + 3
        fm_text = raw[3:fm_end]
        body_text = raw[fm_end + 3:].strip()

        try:
            fm = yaml.safe_load(fm_text)
        except yaml.YAMLError as e:
            skill.errors.append(SkillValidationError("frontmatter", f"YAML parse error: {e}"))
            return skill

        if not isinstance(fm, dict):
            skill.errors.append(SkillValidationError("frontmatter", "Frontmatter must be a YAML mapping"))
            return skill

        skill.raw_frontmatter = fm

        for field in REQUIRED_FRONTMATTER_FIELDS:
            if field not in fm:
                skill.errors.append(SkillValidationError(field, f"Missing required field: '{field}'"))

        skill.name = str(fm.get("name", ""))
        skill.description = str(fm.get("description", ""))

        if skill.name and len(skill.name) > MAX_NAME_LENGTH:
            skill.errors.append(SkillValidationError("name", f"Name exceeds {MAX_NAME_LENGTH} chars"))

        if skill.description and len(skill.description) > MAX_DESCRIPTION_LENGTH:
            skill.errors.append(SkillValidationError("description", f"Description exceeds {MAX_DESCRIPTION_LENGTH} chars"))

        for field in RECOMMENDED_FRONTMATTER_FIELDS:
            if field not in fm:
                skill.warnings.append(SkillValidationError(field, f"Missing recommended field: '{field}'"))

        skill.version = str(fm.get("version", ""))
        skill.author = str(fm.get("author", ""))
        skill.license = str(fm.get("license", ""))
        meta = fm.get("metadata", {}) or {}
        if isinstance(meta, dict):
            cog = meta.get("cogitate") or meta.get("hermes") or {}
            if isinstance(cog, dict):
                skill.tags = cog.get("tags", [])
                skill.related_skills = cog.get("related_skills", [])

        if not body_text:
            skill.warnings.append(SkillValidationError("body", "Body is empty"))
        else:
            body_upper = body_text.upper()
            for section in EXPECTED_SECTIONS:
                if section.upper() not in body_upper:
                    skill.warnings.append(SkillValidationError("structure", f"Missing recommended section: {section}"))

        skill.body = body_text
        return skill

    def find_by_name(self, name: str) -> Optional[Skill]:
        for skill in self.scan():
            if skill.name.lower() == name.lower():
                return skill
        return None

    def find_by_tag(self, tag: str) -> list[Skill]:
        return [s for s in self.scan() if tag in s.tags]

    def get_categories(self) -> list[str]:
        return sorted({s.category for s in self.scan() if s.category})


# --- CLI ---


def _run_cli() -> int:
    parser = argparse.ArgumentParser(description="Validate and list skills")
    parser.add_argument("directory", nargs="?", default="", help="Root skills directory")
    parser.add_argument("--validate-only", action="store_true", help="Exit with error code if any skill has errors")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show warnings too")
    args = parser.parse_args()

    root = args.directory or str(pathlib.Path(__file__).resolve().parent)
    loader = SkillLoader(root_dir=root)
    skills = loader.scan()

    if not skills:
        print(f"No SKILL.md files found under: {root}")
        return 1

    total_errors = 0
    total_warnings = 0
    print(f"\nSkills found: {len(skills)}\n")

    for skill in skills:
        label = "PASS" if skill.valid else "FAIL"
        print(f"  {label} {skill.name or '(unnamed)'} [{skill.category}]")
        print(f"       {skill.file_path}")
        for err in skill.errors:
            print(f"       ERROR [{err.field}] {err.message}")
            total_errors += 1
        if args.verbose:
            for warn in skill.warnings:
                print(f"       WARN [{warn.field}] {warn.message}")
                total_warnings += 1
        print()

    print(f"Summary: {len(skills)} skills, {total_errors} errors, {total_warnings} warnings")
    return 1 if args.validate_only and total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(_run_cli())
