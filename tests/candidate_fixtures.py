"""Candidate Bundle fixtures for the bench tests.

Every fixture bundle is a REAL export through TheOzolith's export tooling
(``theozolith_control.candidate.export_candidate``) with a fake base-digest
resolver and a fixed timestamp — no registry, no Docker — so the bench's
ingestion is exercised against exactly the bytes ``theozolith candidate
export`` writes, never a hand-built imitation of the format.  The image
builder double stands in for the Docker-bound verified build only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from theozolith_control import candidate as ozcandidate

from silverquillm.candidate import BuiltImage, CandidateBundle
from silverquillm.results_repo import CandidateIdentity, candidate_dirname

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
NOW = "2026-09-03T00:00:00Z"
CLAUDE_BASE = "ghcr.io/acme/theozolith-run-claude:1.2.3"
CODEX_BASE = "ghcr.io/acme/theozolith-run-codex:1.2.3"

#: A credential-shaped string no real service issued (tests plant it to prove
#: the secret-value refusal).
FAKE_ANTHROPIC_KEY = "sk-ant-api03-" + "x" * 40
#: One fabricated sample per credential family the production detector
#: recognizes (``silverquillm.candidate.credential_shapes``), keyed by the
#: shape name the detector reports.  None of these was ever issued.
FAKE_CREDENTIALS: dict[str, str] = {
    "Anthropic API key": FAKE_ANTHROPIC_KEY,
    "OpenAI API key": "sk-proj-" + "y" * 40,
    "GitHub token": "ghp_" + "A" * 36,
    "GitHub fine-grained token": "github_pat_" + "B" * 30,
    "AWS access key id": "AKIA" + "ABCDEFGHIJKLMNOP",
    # Shaped for the bench's detector, deliberately not for GitHub's push
    # protection (which wants digit runs after the prefix).
    "Slack token": "xoxb-not-a-real-slack-token-sample",
    "private key block": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----",
    "JSON Web Token": "eyJ" + "a" * 12 + "." + "b" * 12 + "." + "c" * 12,
    "bearer credential": "Bearer " + "z" * 24,
    "a value assigned to a declared secret slot": 'ANTHROPIC_API_KEY = "' + "k" * 30 + '"',
}

#: The declared slot ``ANTHROPIC_API_KEY`` used as an assignment key with a
#: non-empty value — one line per form the detector must flag, deliberately
#: spanning every length, character class and quoting a config or a log can
#: take.  No value here is a credential; the detector must not care.  Each
#: line is exactly the key, the operator and the value, so a redaction that
#: blanks it whole leaves nothing of it behind.
SLOT_ASSIGNMENTS: dict[str, str] = {
    "bare-one-char": "ANTHROPIC_API_KEY=x",
    "bare-two-chars": "ANTHROPIC_API_KEY=q7",
    "double-quoted-short": 'ANTHROPIC_API_KEY = "short"',
    "yaml-symbols": "ANTHROPIC_API_KEY: opaque/+value==",
    "json-quoted-key": '"ANTHROPIC_API_KEY": "opaque/+value=="',
    "single-quoted-spaces": "'ANTHROPIC_API_KEY' = 'value with spaces'",
    "angle-bracket-placeholder": "ANTHROPIC_API_KEY=<your key>",
    "unterminated-quote": 'ANTHROPIC_API_KEY="abc',
    "toml-multiline-opener": 'ANTHROPIC_API_KEY = """',
}

#: The same slot merely *named* — declared, mentioned in prose, or assigned
#: nothing — one line per form the detector must leave alone.  The empty
#: assignments are the shapes a worker-type definition's ``[secrets]`` table
#: and a config template use to declare a slot; they leak nothing.
SLOT_MENTIONS: dict[str, str] = {
    "declaration-array": '"secret_slots": ["ANTHROPIC_API_KEY"]',
    "toml-declaration-list": 'secrets = ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"]',
    "prose": "Set ANTHROPIC_API_KEY in your environment before running.",
    "prose-backticks": "The bench binds `ANTHROPIC_API_KEY` from its own environment.",
    "empty-bare": "ANTHROPIC_API_KEY=",
    "empty-double-quoted": 'ANTHROPIC_API_KEY = ""',
    "empty-single-quoted": "ANTHROPIC_API_KEY: ''",
    "empty-json": '"ANTHROPIC_API_KEY": "",',
    "empty-with-comment": 'ANTHROPIC_API_KEY = ""  # bound by the bench',
    "another-variable": "MY_ANTHROPIC_API_KEY=other-slot",
    "key-as-prefix": "ANTHROPIC_API_KEY_FILE=/run/secrets/key",
}


def make_source(
    root: Path,
    *,
    name: str = "fixture-claude",
    adapter: str = "claude",
    model: str = "claude-sonnet-5",
    effort: str = "",
    driver: str = "builtin:implementer",
    base: str = CLAUDE_BASE,
    setup: tuple[str, ...] = (),
    knowledge: bool = False,
    policy: bool = False,
    secrets: tuple[str, ...] = ("ANTHROPIC_API_KEY",),
    extra_lines: tuple[str, ...] = (),
) -> Path:
    """A minimal config-repo-shaped source directory holding one worker type."""
    source = root / "config-src"
    (source / "worker-types").mkdir(parents=True, exist_ok=True)
    lines = [f'base = "{base}"', "setup = [" + ", ".join(json.dumps(s) for s in setup) + "]"]
    for key, value in (
        ("driver", driver),
        ("adapter", adapter),
        ("model", model),
        ("effort", effort),
    ):
        if value:
            lines.append(f'{key} = "{value}"')
    if knowledge:
        tree = source / "knowledge" / "gold"
        tree.mkdir(parents=True, exist_ok=True)
        (tree / "AGENTS.md").write_text("# golden knowledge\n", encoding="utf-8")
        lines.append('knowledge = "knowledge/gold"')
    if policy:
        tree = source / "policy" / "gold"
        tree.mkdir(parents=True, exist_ok=True)
        (tree / "attribution.json").write_text(
            '{"attribution": {"sessionUrl": false}}\n', encoding="utf-8"
        )
        lines.append('policy = "policy/gold"')
    lines.extend(extra_lines)
    if secrets:
        lines.append("[secrets]")
        lines.extend(f'{slot} = ""' for slot in secrets)
    (source / "worker-types" / f"{name}.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return source


def export_bundle(
    root: Path,
    out: Path | None = None,
    *,
    digest: str = DIGEST_A,
    now: str = NOW,
    **source_kwargs,
) -> tuple[Path, ozcandidate.CandidateSummary]:
    """Export a fixture bundle to *out* (default ``root/bundle``) and return
    ``(bundle_dir, TheOzolith's summary)``."""
    source = make_source(root, **source_kwargs)
    name = source_kwargs.get("name", "fixture-claude")
    out = out if out is not None else root / "bundle"
    summary = ozcandidate.export_candidate(
        source, name, out, resolve_digest=lambda ref: digest, now=lambda: now
    )
    return out, summary


def identity_of(summary: ozcandidate.CandidateSummary) -> CandidateIdentity:
    return CandidateIdentity.recomputed(
        summary.base_digest, summary.instruction_hash, summary.adapter
    )


def make_candidate_dir(root: Path, *, slug: str | None = None, **export_kwargs) -> Path:
    """A checked-in-style candidate directory ``<slug>--<hash8>/`` with the
    bundle under ``bundle/`` and a README beside it."""
    name = export_kwargs.setdefault("name", "fixture-claude")
    slug = slug or name
    staging = root / f".export-{slug}"
    bundle, summary = export_bundle(staging, **export_kwargs)
    dirname = candidate_dirname(slug, identity_of(summary))
    candidate_dir = root / dirname
    candidate_dir.mkdir(parents=True)
    bundle.rename(candidate_dir / "bundle")
    (candidate_dir / "README.md").write_text(f"# {slug}\n\nA fixture candidate.\n", encoding="utf-8")
    return candidate_dir


def rewrite_manifest(bundle: Path, **overrides) -> None:
    path = bundle / ozcandidate.MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(overrides)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fake_image_builder(bundle: CandidateBundle) -> BuiltImage:
    """The image-builder double: no Docker; a deterministic fake image ID
    derived from the bundle's deterministic tag."""
    return BuiltImage(
        tag=bundle.tag, image_id="sha256:" + hashlib.sha256(bundle.tag.encode()).hexdigest()
    )
