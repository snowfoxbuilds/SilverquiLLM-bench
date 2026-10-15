"""Command groups for the tooling in ``silverquillm.tools``.

Each command hands its arguments to the module's own ``main(argv)``, so a tool's
flags, help text and exit status are its parser's, unchanged by the move from
``scripts/``. Modules load only when their command runs.
"""

from __future__ import annotations

import importlib
import sys

import click

_PASSTHROUGH = {"ignore_unknown_options": True, "allow_extra_args": True, "help_option_names": []}


def _tool(group: click.Group, name: str, module: str, summary: str, package: str = "silverquillm.tools") -> None:
    @group.command(name, help=summary, short_help=summary, context_settings=_PASSTHROUGH, add_help_option=False)
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    def command(args: tuple[str, ...]) -> None:
        tool = importlib.import_module(f"{package}.{module}")
        # argparse names itself after argv[0]; show the full command in usage lines.
        program = sys.argv[0]
        sys.argv[0] = f"silverquillm {group.name} {name}"
        try:
            status = tool.main(list(args))
        finally:
            sys.argv[0] = program
        raise SystemExit(status)


@click.group("data")
def data() -> None:
    """Fetch and build the reference data under data/ (sets, replays, id maps)."""


@click.group("build")
def build() -> None:
    """Generate benchmark inputs: workspaces, card specs, stubs and printed classes."""


@click.group("audit")
def audit() -> None:
    """Maintain Audited Tests: the promotion gate and test-source codemods."""


@click.group("qualify")
def qualify() -> None:
    """Qualify an agent CLI version's telemetry before its accounting is trusted."""


@click.group("replay")
def replay() -> None:
    """Analyse replay-validation reports."""


_tool(data, "fetch-hob-set", "fetch_hob_set", "Fetch raw HOB print data into data/sets/hob.json.")
_tool(data, "fetch-fra-set", "fetch_fra_set", "Fetch raw FRA print data into data/sets/fra.json.")
_tool(data, "card-id-map", "build_card_id_map", "Build data/replays/card_id_map.json from Scryfall.")
_tool(data, "token-id-map", "build_token_id_map", "Build data/replays/token_id_map.json from a replay corpus.")
_tool(data, "download-replays", "download_replays", "Download 17lands replays listed on a replay page.")

_tool(build, "fra-hard", "build_fra_hard", "Build fra-hard assets from pinned raw sets; seed the oracle once.")
_tool(build, "port-from-known-best", "port_from_known_best", "Port a Beta benchmark's files from the Known-Best Workspace.")
_tool(build, "printed-classes", "generate_printed_classes", "Regenerate the printed-ability block of card_impl.py files.")
_tool(build, "fdn-specs", "generate_fdn_specs", "Generate FDN card specs and implementation templates.")
_tool(build, "audited-stubs", "generate_audited_stubs", "Generate the SOS stub card classes.")

_tool(audit, "check-promotion", "check_promotion_candidate", "Run the promotion gate on one candidate test.")
_tool(audit, "printed-identity", "printed_identity_codemod", "Rewrite name-string card identification to printed classes.")

_tool(qualify, "claude-telemetry", "qualify_claude_telemetry", "Qualify a Claude Code version from a real run.")
_tool(qualify, "codex-telemetry", "qualify_codex_telemetry", "Qualify a Codex version against scripted ground truth.")

# A grading input staged at its old scripts/ path; see evaluator.REPLAY_SUPPORT.
_tool(replay, "triage", "triage_divergences", "Cluster a replay-validation report's divergences by root cause.", "silverquillm")

COMMANDS = (data, build, audit, qualify, replay)
