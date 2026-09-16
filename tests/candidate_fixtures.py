"""Real Karn standalone-definition fixtures, with deterministic identities and no runtime packages."""
from __future__ import annotations
import json
import uuid
from pathlib import Path
from karn.definition import canonical, new_definition
from silverquillm.candidate import BuiltImage, CandidateBundle, load_candidate_bundle
from silverquillm.promotion import promote
from silverquillm.results_repo import CandidateIdentity

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
#: spanning every length, character class, quoting and escaping a config or
#: a log can take.  No value here is a credential; the detector must not
#: care.  Each line is exactly the key, the operator and the value, so a
#: redaction that blanks it whole leaves nothing of it behind.  The JSON
#: forms are serializer output (``json.dumps`` of the pair, braces dropped),
#: so the escaping is exactly what a real config or log line carries.
SLOT_ASSIGNMENTS: dict[str, str] = {
    "bare-one-char": "ANTHROPIC_API_KEY=x",
    "bare-two-chars": "ANTHROPIC_API_KEY=q7",
    "double-quoted-short": 'ANTHROPIC_API_KEY = "short"',
    "yaml-symbols": "ANTHROPIC_API_KEY: opaque/+value==",
    "json-quoted-key": '"ANTHROPIC_API_KEY": "opaque/+value=="',
    "json-escaped-quote": json.dumps({"ANTHROPIC_API_KEY": 'left7"right9'})[1:-1],
    "json-escaped-backslash": json.dumps({"ANTHROPIC_API_KEY": "tail\\"})[1:-1],
    "single-quoted-spaces": "'ANTHROPIC_API_KEY' = 'value with spaces'",
    "single-quoted-escaped-quote": "'ANTHROPIC_API_KEY' = 'it\\'s'",
    "yaml-doubled-single-quote": "ANTHROPIC_API_KEY: 'it''s'",
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


def make_source(root, *, name="fixture-claude", adapter="claude", model="claude-sonnet-5", effort="", driver="configured", base=CLAUDE_BASE, setup=(), knowledge=False, policy=False, secrets=("ANTHROPIC_API_KEY",), extra_lines=(), digest=DIGEST_A):
    source=Path(root)/"definition-src"
    source.mkdir(parents=True,exist_ok=True)
    document=new_definition(name=name,mode="automaton",image=digest,main=["/bin/true"],definition_version=3).document
    document["definition_id"]=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps([name,adapter,model,effort,driver,base,setup,knowledge,policy,secrets],sort_keys=True)))
    runtime=document["runtime"]
    runtime["environment"]={"BENCHMARK_ADAPTER":adapter,"BENCHMARK_MODEL":model,"BENCHMARK_EFFORT":effort}
    runtime["mounts"]=[dict(name=n,target=t,source=dict(kind="runtime",value=n),persistent=False,access="read_only" if n=="input" else "read_write",purpose=n) for n,t in (("workspace","/work"),("input","/in"),("output","/out"))]
    runtime["files"]=[dict(name="prompt",mount="input",path="prompt.md",direction="input",schema={"type":"string"}),dict(name="proposal",mount="output",path="proposal.json",direction="output",schema={"type":"object"})]
    runtime["credentials"]=[dict(name="credential-"+str(i),source=dict(type="raw",secret=slot.lower().replace("_","-")),delivery=dict(type="environment",variable=slot)) for i,slot in enumerate(secrets)]
    if extra_lines:runtime["environment"]["FIXTURE_EXTRA"]="\n".join(extra_lines)
    (source/"definition.json").write_bytes(canonical(document)+b"\n")
    return source


def export_bundle(root, out=None, *, digest=DIGEST_A, now=NOW, **source_kwargs):
    source=make_source(root,digest=digest,**source_kwargs)
    out=Path(out) if out is not None else Path(root)/"bundle"
    out.mkdir(parents=True,exist_ok=False)
    (out/"definition.json").write_bytes((source/"definition.json").read_bytes())
    return out,load_candidate_bundle(out)


def identity_of(summary):
    return summary.identity


def make_candidate_dir(root, *, slug=None, **export_kwargs):
    name=export_kwargs.setdefault("name","fixture-claude")
    bundle,_=export_bundle(Path(root)/(".export-"+(slug or name)),**export_kwargs)
    return promote(bundle,candidates_dir=root,slug=slug or name).candidate_dir


def rewrite_manifest(bundle,**overrides):
    path=Path(bundle)/"definition.json"
    value=json.loads(path.read_text())
    value.update(overrides)
    path.write_bytes(canonical(value)+b"\n")


def fake_image_builder(bundle):
    return BuiltImage(tag=bundle.manifest["image"],image_id=bundle.manifest["image"])
