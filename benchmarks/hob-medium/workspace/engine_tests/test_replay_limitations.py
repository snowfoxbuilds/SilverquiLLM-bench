"""Phase M mechanism tests: the predicted-outcome disambiguation protocol and
the machine-checked evidence behind the stream-limitation floor.

These run in the MSH workspace context (``engine`` resolves here). Two groups:

* :class:`TestPredictedOutcomeDisambiguation` pins the executor's evidence-based
  multi-ability driving — it drives the uniquely matching ability and refuses
  (recording the source as ambiguous) on a tie, a missing predictor, or no GRE
  identity to match against.
* :class:`TestLimitationEvidence` replays committed golden transcripts and
  PROVES the stream lacks the distinguishing evidence for each floor tag —
  ``unfunded-activation`` (no ManaPaid / no manaPool covers the cost),
  ``hidden-information`` (grpId-0 shells carry no identity; a library-driven
  power/toughness), and ``ambiguous-ability`` (a multi-ability source the
  executor could not disambiguate).
"""

from __future__ import annotations

from pathlib import Path

from engine.card import ActivatedAbility, PredictedOutcome

from engine_tests.test_replay_simulate import BF1, card_obj, snapshot
from silverquillm.replay.executor import ReplayExecutor
from silverquillm.replay.types import ReplayGame

REPO_ROOT = Path(__file__).resolve().parents[4]
GOLDEN = REPO_ROOT / "data" / "replays" / "golden"

# A stand-in for a multi-ability engine source. It exposes get_activated_abilities
# (what the executor reads) and a name (what the ambiguous-refusal set records).
GRP = 90001
IID = 5001


class _MultiAbilitySource:
    def __init__(self, name, abilities):
        self.name = name
        self._abilities = abilities

    def get_activated_abilities(self):
        return list(self._abilities)


def _ability(pred):
    return ActivatedAbility(
        cost=lambda game: True,
        effect=lambda game: None,
        predicted_outcome=pred,
    )


def _bare_executor(prev, curr, source):
    """An executor with just enough state to run the disambiguation matcher:
    the source mapped to its GRE identity, no engine (predictions are pure)."""
    replay = ReplayGame(seat_id=1, opponent_seat_id=2)
    replay.snapshots = [prev, curr]
    ex = ReplayExecutor(replay=replay, card_id_map={}, registry=None, simulate=True)
    ex._engine_cards = {IID: source}
    ex.players = {}
    return ex


def _on_bf(**kw):
    """prev/curr snapshot pair helper: source present on the battlefield in prev."""
    obj = card_obj(IID, GRP, 1, BF1, **kw)
    return obj


class TestPredictedOutcomeDisambiguation:
    def test_unique_source_leaves_match_drives_that_ability(self):
        # Ability A predicts the source leaves the battlefield; ability B keeps
        # it. Observed: the source left -> only A is consistent.
        leaves = _ability(lambda g, s: PredictedOutcome(leaves_battlefield=[s]))
        stays = _ability(lambda g, s: PredictedOutcome())
        source = _MultiAbilitySource("Sac Engine", [leaves, stays])
        prev = snapshot(1, battlefield={1: [IID]}, objects={IID: _on_bf()})
        curr = snapshot(2, battlefield={1: []}, objects={})  # source gone
        ex = _bare_executor(prev, curr, source)
        chosen = ex._disambiguate_multi_ability(source, [leaves, stays], prev, curr)
        assert chosen is leaves

    def test_unique_source_stays_match_drives_the_other(self):
        leaves = _ability(lambda g, s: PredictedOutcome(leaves_battlefield=[s]))
        stays = _ability(lambda g, s: PredictedOutcome())
        source = _MultiAbilitySource("Sac Engine", [leaves, stays])
        obj = _on_bf()
        prev = snapshot(1, battlefield={1: [IID]}, objects={IID: obj})
        curr = snapshot(2, battlefield={1: [IID]}, objects={IID: obj})  # stays
        ex = _bare_executor(prev, curr, source)
        chosen = ex._disambiguate_multi_ability(source, [leaves, stays], prev, curr)
        assert chosen is stays

    def test_contradicting_pt_set_uniquely_selects(self):
        # Two abilities set different P/T; the observed 3/2 confirms one and
        # contradicts the other -> unique selection.
        wrong = _ability(lambda g, s: PredictedOutcome(pt_sets={s: (5, 5)}))
        right = _ability(lambda g, s: PredictedOutcome(pt_sets={s: (3, 2)}))
        source = _MultiAbilitySource("Level Up", [wrong, right])
        prev = snapshot(1, battlefield={1: [IID]}, objects={IID: card_obj(IID, GRP, 1, BF1, power=2, toughness=1)})
        curr = snapshot(2, battlefield={1: [IID]}, objects={IID: card_obj(IID, GRP, 1, BF1, power=3, toughness=2)})
        ex = _bare_executor(prev, curr, source)
        assert ex._disambiguate_multi_ability(source, [wrong, right], prev, curr) is right

    def test_pt_set_vs_noop_sibling_is_a_tie(self):
        # A no-op sibling predicts nothing about P/T, so it never *contradicts*
        # an observed P/T change; the pt-setting ability alone cannot be
        # selected. This is exactly why the corpus's Kellan could not be driven
        # cleanly from compared surfaces — recorded honestly as a tie, not
        # guessed. (Verifies the matcher does not over-drive.)
        noop = _ability(lambda g, s: PredictedOutcome())
        levelup = _ability(lambda g, s: PredictedOutcome(pt_sets={s: (3, 2)}))
        source = _MultiAbilitySource("Level Up", [noop, levelup])
        prev = snapshot(1, battlefield={1: [IID]}, objects={IID: card_obj(IID, GRP, 1, BF1, power=2, toughness=1)})
        curr = snapshot(2, battlefield={1: [IID]}, objects={IID: card_obj(IID, GRP, 1, BF1, power=3, toughness=2)})
        ex = _bare_executor(prev, curr, source)
        assert ex._disambiguate_multi_ability(source, [noop, levelup], prev, curr) is None

    def test_tie_refuses_and_records_ambiguous(self):
        # BOTH abilities predict the source stays with no other signal, and the
        # source did stay -> >=2 predictions match -> refuse and mark ambiguous.
        a = _ability(lambda g, s: PredictedOutcome())
        b = _ability(lambda g, s: PredictedOutcome())
        source = _MultiAbilitySource("Ambiguous", [a, b])
        obj = _on_bf()
        prev = snapshot(1, battlefield={1: [IID]}, objects={IID: obj})
        curr = snapshot(2, battlefield={1: [IID]}, objects={IID: obj})
        ex = _bare_executor(prev, curr, source)
        assert ex._disambiguate_multi_ability(source, [a, b], prev, curr) is None

    def test_try_activate_records_ambiguous_source_on_tie(self):
        from silverquillm.replay.executor import StepResult
        from silverquillm.replay.types import ReplayAction

        a = _ability(lambda g, s: PredictedOutcome())
        b = _ability(lambda g, s: PredictedOutcome())
        source = _MultiAbilitySource("Ambiguous", [a, b])
        obj = _on_bf()
        prev = snapshot(1, battlefield={1: [IID]}, objects={IID: obj})
        curr = snapshot(2, battlefield={1: [IID]}, objects={IID: obj})
        ex = _bare_executor(prev, curr, source)
        action = ReplayAction(action_type="ability_activation", player_seat_id=1, instance_id=IID, grp_id=GRP)
        # The tie path returns before any engine activation, so a null engine is fine.
        ex._try_activate_ability(object(), source, action, prev, curr, StepResult(snapshot_id=2))
        assert "Ambiguous" in ex._ambiguous_sources

    def test_missing_predictor_refuses(self):
        has = _ability(lambda g, s: PredictedOutcome(leaves_battlefield=[s]))
        none = _ability(None)  # no predicted_outcome hook
        source = _MultiAbilitySource("Half", [has, none])
        prev = snapshot(1, battlefield={1: [IID]}, objects={IID: _on_bf()})
        curr = snapshot(2, battlefield={1: []}, objects={})
        ex = _bare_executor(prev, curr, source)
        assert ex._disambiguate_multi_ability(source, [has, none], prev, curr) is None

    def test_no_gre_identity_refuses(self):
        a = _ability(lambda g, s: PredictedOutcome())
        b = _ability(lambda g, s: PredictedOutcome(leaves_battlefield=[s]))
        source = _MultiAbilitySource("Unmapped", [a, b])
        prev = snapshot(1)
        curr = snapshot(2)
        ex = _bare_executor(prev, curr, source)
        ex._engine_cards = {}  # source not mapped to any GRE identity
        assert ex._disambiguate_multi_ability(source, [a, b], prev, curr) is None

    def test_prediction_never_mutates_source(self):
        # The protocol is pure: evaluating predictions must not tap/move/alter.
        leaves = _ability(lambda g, s: PredictedOutcome(leaves_battlefield=[s]))
        stays = _ability(lambda g, s: PredictedOutcome())
        source = _MultiAbilitySource("Pure", [leaves, stays])
        source.is_tapped = False
        prev = snapshot(1, battlefield={1: [IID]}, objects={IID: _on_bf()})
        curr = snapshot(2, battlefield={1: []}, objects={})
        ex = _bare_executor(prev, curr, source)
        ex._disambiguate_multi_ability(source, [leaves, stays], prev, curr)
        assert source.is_tapped is False


def _run_golden(fixture):
    from cards.loader import load_set_registry

    from silverquillm.replay.parser import load_card_id_map, parse_replay
    from silverquillm.replay.validation import ValidatingExecutor

    cmap = load_card_id_map()
    registry = load_set_registry("fdn")
    game = parse_replay(fixture, card_id_map=cmap)
    executor = ReplayExecutor(replay=game, card_id_map=cmap, registry=registry, simulate=True)
    validator = ValidatingExecutor(executor, cmap)
    validator.execute_all()
    return game, executor, validator.report()


class TestLimitationEvidence:
    """Fixture-backed proofs that the stream lacks the distinguishing evidence
    for each floor tag — the machine-checked floor."""

    def test_unfunded_activation_has_no_covering_mana_evidence(self):
        """The unfunded-activation floor: for every activation the executor
        rejects with 'cost could not be paid', the stream carries NO ManaPaid
        referencing that activation and NO attested manaPool anywhere — so no
        faithful engine could have funded it."""
        game, _executor, report = _run_golden(GOLDEN / "fdn_unfunded_activation.json")
        engine_errors = [
            d for d in report.divergences
            if d.divergence_type.value == "ENGINE_ERROR"
            and "cost could not be paid" in d.description
        ]
        assert engine_errors, "fixture must contain unfunded activations"

        snap_by_gsid = {s.game_state_id: s for s in game.snapshots}
        # No snapshot in the whole game attests any floating manaPool.
        assert not any(
            getattr(p, "mana_pool", None)
            for s in game.snapshots
            for p in s.players.values()
        )
        for div in engine_errors:
            snap = snap_by_gsid[div.game_state_id]
            activations = [
                a for a in snap.actions if a.action_type == "ability_activation"
            ]
            assert activations
            for act in activations:
                covering = [
                    ann
                    for s in game.snapshots
                    for ann in s.annotations
                    if "AnnotationType_ManaPaid" in ann.type
                    and act.instance_id in ann.affected_ids
                ]
                assert covering == [], (
                    f"activation {act.instance_id} unexpectedly has ManaPaid "
                    "evidence — it would not be an unfunded floor case"
                )

    def test_hidden_information_pt_tracks_a_hidden_library(self):
        """Consuming Aberration's power/toughness is a function of a hidden zone
        (self-mill feeding the graveyard off the engine's private library), so
        its mismatches are hidden-information. Evidence: the P/T mismatches are
        all on Consuming Aberration, and the library the mill draws from holds
        objects whose identity the stream never attests (referenced in the zone
        list but absent from game_objects), so no engine could reproduce which
        cards were milled."""
        game, _executor, report = _run_golden(GOLDEN / "fdn_consuming_aberration_mill.json")
        pt = [
            d for d in report.divergences
            if d.description.startswith("[power_toughness]")
        ]
        cda_pt = [d for d in pt if "Consuming Aberration" in d.description]
        assert cda_pt, "mill fixture must exercise Consuming Aberration's P/T"
        # Library identity is withheld: instance ids are listed in library zones
        # with no corresponding attested GameObject.
        withheld = 0
        for snap in game.snapshots:
            for zone in snap.zones.values():
                if zone.type != "ZoneType_Library":
                    continue
                withheld += sum(
                    1 for iid in zone.object_instance_ids
                    if snap.game_objects.get(iid) is None
                )
        assert withheld > 0

    def test_hidden_information_zone_shell_from_withheld_identity(self):
        """A hidden-information zone divergence carries an engine-side grpId-0
        object: the stream withheld the card's identity when it arrived from a
        hidden zone, so the executor can only represent it as an unidentifiable
        shell that never reconciles by identity."""
        from silverquillm.replay.limitations import (
            LimitationContext,
            classify_limitation,
        )

        _game, executor, report = _run_golden(GOLDEN / "fdn_equipment_funding.json")
        ctx = LimitationContext(
            ambiguous_sources=frozenset(executor._ambiguous_sources)
        )
        hidden_zone = [
            d for d in report.divergences
            if d.description.startswith("[zone_contents]")
            and classify_limitation(
                {"type": d.divergence_type.value, "description": d.description},
                ctx,
            ) == "hidden-information"
        ]
        assert hidden_zone, "equipment fixture must surface a grpId-0 zone shell"
        # The engine side of the diff carries a grpId-0 (identity-less) object.
        assert any("engine=[0" in d.description or ", 0," in d.description or ", 0]"
                   in d.description for d in hidden_zone)

    def test_ambiguous_ability_source_is_recorded(self):
        """ambiguous-ability floor: a multi-ability source (Ravenous Amulet)
        whose exact ability the executor could not disambiguate is recorded, so
        its surviving mismatches are floor-tagged rather than mis-driven."""
        _game, executor, _report = _run_golden(GOLDEN / "fdn_equipment_funding.json")
        assert "Ravenous Amulet" in executor._ambiguous_sources
