"""MTG comprehensive rules indexer and lookup.

Provides utilities to download, parse, index, and query the Magic: The Gathering
comprehensive rules.  The index maps rule numbers and keywords to rule text,
enabling quick lookup by number (e.g. ``"702.9"``) or keyword (e.g. ``"flying"``).
"""

from __future__ import annotations

import logging
import re
import urllib.request
from pathlib import Path

__all__ = [
    "download_comprehensive_rules",
    "build_rules_index",
    "generate_rules_overview",
    "lookup_rule",
]

logger = logging.getLogger(__name__)

_RULES_URL = (
    "https://media.wizards.com/images/magic/comprules/MagicCompRules.txt"
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "sos" / "data"
_CACHE_PATH = _DATA_DIR / "comprehensive_rules.txt"
_OVERVIEW_PATH = _DATA_DIR / "rules_overview.md"

# ---------------------------------------------------------------------------
# Stub rules (used when the download fails)
# ---------------------------------------------------------------------------

_STUB_RULES = """\
Magic: The Gathering Comprehensive Rules (Stub)

These rules are effective as of the latest release.

1. Game Concepts

100. General
100.1. These Magic rules apply to any Magic game with two or more players.

101. The Magic Golden Rules
101.1. Whenever a card's text directly contradicts these rules, the card takes precedence.
101.2. When a rule or effect allows or directs something to happen, and another effect states \
that it can't happen, the "can't" effect takes precedence.

102. Players
102.1. A player is one of the people in the game.

103. Starting the Game
103.1. At the start of a game, each player shuffles their deck.

104. Ending the Game
104.1. A game ends immediately when a player wins, when the game is a draw, or when the game \
is restarted.

2. Parts of a Card

200. General
200.1. The parts of a card are name, mana cost, illustration, color indicator, type line, \
expansion symbol, text box, power and toughness, loyalty, hand modifier, life modifier, \
defense, collector information.

3. Card Types

300. General
300.1. The card types are artifact, battle, conspiracy, creature, dungeon, enchantment, \
instant, kindred, land, phenomenon, plane, planeswalker, scheme, sorcery, and vanguard.

301. Artifacts
301.1. A player who has priority may cast an artifact card from their hand during a main phase \
of their turn when the stack is empty.

302. Creatures
302.1. A player who has priority may cast a creature card from their hand during a main phase \
of their turn when the stack is empty.
302.2. When a creature spell resolves, its controller puts it onto the battlefield under their \
control.
302.3. Creature's subtypes are always a single word and are listed after a long dash.
302.4. Power and toughness are characteristics only creatures have.
302.6. A creature's activated ability with the tap symbol or the untap symbol in its activation \
cost can't be activated unless the creature has been under its controller's control continuously \
since the start of their most recent turn. This rule is informally called the "summoning \
sickness" rule.

303. Enchantments
303.1. A player who has priority may cast an enchantment card from their hand during a main \
phase of their turn when the stack is empty.

304. Instants
304.1. A player who has priority may cast an instant card from their hand.

305. Lands
305.1. A player who has priority may play a land card from their hand during a main phase of \
their turn when the stack is empty.
305.2. A player can normally play one land during their turn.

306. Planeswalkers
306.1. A player who has priority may cast a planeswalker card from their hand during a main \
phase of their turn when the stack is empty.

4. Zones

400. General
400.1. A zone is a place where objects can be during a game. There are normally seven zones: \
library, hand, battlefield, graveyard, stack, exile, and command.

401. Library
401.1. When a game begins, each player's deck becomes their library.

402. Hand
402.1. The hand is where a player holds cards that have been drawn.

403. Battlefield
403.1. The battlefield is the zone in which permanents exist.

404. Graveyard
404.1. A player's graveyard is their discard pile.

405. Stack
405.1. When a spell is cast, the physical card is put on the stack. When an ability is \
activated or triggers, it goes on top of the stack without any card associated with it.

406. Exile
406.1. The exile zone is essentially a holding area for objects.

5. Turn Structure

500. General
500.1. A turn consists of five phases, in this order: beginning phase, first main phase, \
combat phase, second main phase, and ending phase.

501. Beginning Phase
501.1. The beginning phase consists of three steps, in this order: untap, upkeep, and draw.

502. Untap Step
502.1. First, all phased-in permanents with phasing that the active player controls phase out, \
and all phased-out permanents that the active player controlled when they phased out phase in.
502.2. Second, the active player determines which permanents they control will untap. Then they \
untap them all simultaneously.
502.3. No player receives priority during the untap step.

503. Upkeep Step
503.1. The upkeep step has no turn-based action. Once it begins, the active player gets priority.

504. Draw Step
504.1. First, the active player draws a card. This turn-based action doesn't use the stack.

505. Main Phase
505.1. There are two main phases in a turn. The first main phase and second main phase are \
sometimes referred to as the precombat and postcombat main phase respectively.

506. Combat Phase
506.1. The combat phase has five steps, which proceed in order: beginning of combat, declare \
attackers, declare blockers, combat damage, and end of combat.

507. Beginning of Combat Step
507.1. The active player gets priority.

508. Declare Attackers Step
508.1. First, the active player declares attackers.

509. Declare Blockers Step
509.1. First, the defending player declares blockers.

510. Combat Damage Step
510.1. First, the active player announces how each attacking creature assigns its combat damage.
510.2. Second, all combat damage that's been assigned is dealt simultaneously.

511. End of Combat Step
511.1. The end of combat step has no turn-based action.

512. Ending Phase
512.1. The ending phase consists of two steps: end and cleanup.

513. End Step
513.1. The end step has no turn-based action.

514. Cleanup Step
514.1. First, if the active player's hand contains more cards than their maximum hand size \
(normally seven), they discard enough cards to reduce their hand size to that number.
514.2. Second, the following actions happen simultaneously: all damage marked on permanents is \
removed and all "until end of turn" and "this turn" effects end.

6. Spells, Abilities, and Effects

600. General
600.1. Anything that happens in a game is an event.

601. Casting Spells
601.1. Previously, the action of casting a spell, or casting a card as a spell, was referred \
to on cards as "playing" that spell or "playing" that card.
601.2. To cast a spell is to take it from where it is, put it on the stack, and pay its costs.
601.2a. To propose the casting of a spell, a player first moves that card (or that copy of a \
card) from where it is to the stack.
601.2b. If the spell is modal, the player announces the mode choice.
601.2c. The player announces their choice of an appropriate object or player for each target \
the spell requires.
601.2f. The player determines the total cost of the spell.
601.2h. The player pays the total cost.

602. Activating Activated Abilities
602.1. Activated abilities have a cost and an effect. They are written as "[Cost]: [Effect.]"

603. Handling Triggered Abilities
603.1. Triggered abilities have a trigger condition and an effect.

604. Handling Static Abilities
604.1. Static abilities do something all the time rather than being activated or triggered.

605. Mana Abilities
605.1. An activated ability is a mana ability if it meets all of the following criteria: it \
doesn't require a target, it could add mana to a player's mana pool when it resolves, and it's \
not a loyalty ability.

608. Resolving Spells and Abilities
608.1. Each time all players pass in succession, the spell or ability on top of the stack resolves.

7. Additional Rules

700. General
700.1. Anything that happens in a game is an event.

701. Keyword Actions
701.2. Regenerate
701.3. Destroy
701.4. Sacrifice
701.5. Discard
701.7. Draw
701.8. Exile
701.10. Shuffle

702. Keyword Abilities
702.1. Most abilities describe exactly what they do in the card's rules text. Some, though, \
are very common or would require too much space to define on a card. In these cases, the object \
lists only the name of the ability as a "keyword"; sometimes reminder text summarizes the game \
rule.

702.2. First Strike
702.2a. First strike is a static ability that modifies the rules for the combat damage step.
702.2b. If at least one attacking or blocking creature has first strike or double strike as the \
combat damage step begins, creatures without first strike or double strike don't assign combat \
damage during that step. Instead of following the procedure in rule 510.2, the combat damage \
step has a second combat damage substep.

702.3. Haste
702.3a. Haste is a static ability.
702.3b. If a creature has haste, it can attack even if it hasn't been controlled by its \
controller continuously since their most recent turn began.

702.4. Protection
702.4a. Protection is a static ability, written "Protection from [quality]."

702.5. Reach
702.5a. Reach is a static ability.
702.5b. A creature with reach can block creatures with flying.

702.6. Trample
702.6a. Trample is a static ability that modifies the rules for assigning an attacking \
creature's combat damage.
702.6b. The attacking creature with trample assigns lethal damage to each blocker, then assigns \
remaining damage to the defending player or planeswalker.

702.7. Vigilance
702.7a. Vigilance is a static ability.
702.7b. Attacking doesn't cause creatures with vigilance to tap.

702.8. Hexproof
702.8a. Hexproof is a static ability.
702.8b. A permanent with hexproof can't be the target of spells or abilities its controller's \
opponents control.

702.9. Flying
702.9a. Flying is a static ability.
702.9b. A creature with flying can't be blocked except by creatures with flying and/or reach.

702.10. Deathtouch
702.10a. Deathtouch is a static ability.
702.10b. A creature with deathtouch that deals damage to a creature is considered to have dealt \
lethal damage to that creature regardless of the amount of damage dealt.

702.11. Defender
702.11a. Defender is a static ability.
702.11b. A creature with defender can't attack.

702.12. Flash
702.12a. Flash is a static ability.
702.12b. A player may cast a spell with flash any time they could cast an instant.

702.13. Lifelink
702.13a. Lifelink is a static ability.
702.13b. Damage dealt by a source with lifelink causes that source's controller to gain that \
much life.

702.15. Double Strike
702.15a. Double strike is a static ability that modifies the rules for the combat damage step.
702.15b. A creature with double strike deals both first-strike and normal combat damage.

702.19. Menace
702.19a. Menace is a static ability.
702.19b. A creature with menace can't be blocked except by two or more creatures.

702.44. Ward
702.44a. Ward is a triggered ability. "Ward [cost]" means "Whenever this permanent becomes \
the target of a spell or ability an opponent controls, counter that spell or ability unless \
that player pays [cost]."

702.134. Prepared
702.134a. Prepared is a keyword ability that provides a conditional bonus.

703. Turn-Based Actions
703.1. Turn-based actions are game actions that happen automatically when certain steps or \
phases begin, or when each step or phase ends.

704. State-Based Actions
704.1. State-based actions are game actions that happen automatically whenever certain \
conditions are met.
704.3. Whenever a player would get priority, the game checks for any of the listed conditions \
for state-based actions, then performs all applicable state-based actions simultaneously as a \
single event.
704.5. The state-based actions are as follows:
704.5a. If a player has 0 or less life, that player loses the game.
704.5b. If a player attempted to draw a card from an empty library since the last time \
state-based actions were checked, that player loses the game.
704.5c. If a creature has toughness 0 or less, it's put into its owner's graveyard.
704.5d. If a creature has been dealt damage by a source with deathtouch, or if a creature's \
toughness is reduced to 0 or less by damage marked on it, it's destroyed. Regeneration can \
replace this event.
704.5e. If a planeswalker has loyalty 0, it's put into its owner's graveyard.
704.5f. If a player controls two or more legendary permanents with the same name, that player \
chooses one of them, and the rest are put into their owners' graveyards. This is called the \
"legend rule."
704.5g. If two or more permanents have the supertype "world," all except the one that has had \
the world supertype for the shortest amount of time are put into their owners' graveyards.
704.5j. If a creature is attached to an object or player, it becomes unattached and remains \
on the battlefield. Similarly, if a permanent that's neither an Aura, an Equipment, nor a \
Fortification is attached to an object or player, it becomes unattached and remains on the \
battlefield.
704.5m. If an Aura is attached to an illegal object or player, or is not attached to an object \
or player, that Aura is put into its owner's graveyard.
704.5n. If a creature is blocking but no creatures are attacking, the creature is removed from \
combat.

713. Controlling Another Player
713.1. Some cards allow a player to control another player during that player's next turn.

8. Multiplayer Rules

800. General
800.1. A multiplayer game is a game that begins with more than two players.

Glossary:
Flying: A keyword ability that restricts how a creature may be blocked. See rule 702.9.
First Strike: A keyword ability that lets a creature deal its combat damage before other \
creatures. See rule 702.2.
Haste: A keyword ability that lets a creature ignore the "summoning sickness" rule. See \
rule 702.3.
Trample: A keyword ability that modifies how a creature assigns combat damage. See rule 702.6.
Vigilance: A keyword ability that lets a creature attack without tapping. See rule 702.7.
Deathtouch: A keyword ability that makes any damage dealt by a source lethal. See rule 702.10.
Lifelink: A keyword ability that causes a player to gain life. See rule 702.13.
Reach: A keyword ability that allows a creature to block flyers. See rule 702.5.
Flash: A keyword ability that allows casting at instant speed. See rule 702.12.
Hexproof: A keyword ability that prevents targeting by opponents. See rule 702.8.
Defender: A keyword ability that prevents a creature from attacking. See rule 702.11.
Double Strike: A keyword ability that causes a creature to deal damage twice. See rule 702.15.
Menace: A keyword ability that makes a creature harder to block. See rule 702.19.
Ward: A triggered ability that taxes targeting. See rule 702.44.
Prepared: A keyword ability that provides a conditional bonus. See rule 702.134.
State-Based Actions: Game actions that happen automatically. See rule 704.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def download_comprehensive_rules(*, force: bool = False) -> str:
    """Download MTG comprehensive rules and cache locally.

    Fetches from the official Wizards URL.  On failure, falls back to a
    representative stub covering the most important rule sections.

    Args:
        force: If *True*, bypass the local cache and re-download from the
            Wizards URL even when the cache file already exists.

    Returns:
        The full rules text as a string.
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not force and _CACHE_PATH.exists():
        logger.info("Using cached rules at %s", _CACHE_PATH)
        return _CACHE_PATH.read_text(encoding="utf-8")

    try:
        logger.info("Downloading comprehensive rules from %s", _RULES_URL)
        req = urllib.request.Request(_RULES_URL, headers={"User-Agent": "SilverquiLLM-bench/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        # Try utf-8 first, fall back to latin-1
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        _CACHE_PATH.write_text(text, encoding="utf-8")
        logger.info("Cached rules to %s (%d bytes)", _CACHE_PATH, len(text))
        return text
    except Exception:
        logger.warning(
            "Failed to download rules; using stub rules.",
            exc_info=True,
        )
        text = _STUB_RULES
        _CACHE_PATH.write_text(text, encoding="utf-8")
        return text


# Rule-number pattern: e.g. "100.", "100.1", "100.1a", "702.9b"
_RULE_RE = re.compile(r"^(\d{3}(?:\.\d+[a-z]?)?)\.?\s+(.+)", re.MULTILINE)


# ---------------------------------------------------------------------------
# Hand-crafted overview content (kept in sync with the stub / downloaded rules)
# ---------------------------------------------------------------------------

_RULES_OVERVIEW_CONTENT = """\
# MTG Rules Overview

## Turn Structure
Each turn has five phases: **Beginning** (untap, upkeep, draw), **Pre-combat Main**, **Combat**, **Post-combat Main**, and **Ending** (end step, cleanup). Players receive priority in each step except untap and cleanup (unless triggers fire).

## Casting Spells
To cast a spell: move it to the stack, choose modes/targets, determine and pay costs. Sorceries and permanents can only be cast during your main phase with an empty stack. Instants (and flash) can be cast any time you have priority.

## The Stack
Spells and abilities resolve last-in, first-out. Each time all players pass priority in succession, the top item resolves. Players may respond by casting instants or activating abilities.

## Combat
1. **Beginning of combat** — priority pass.
2. **Declare attackers** — active player taps attacking creatures (unless vigilance).
3. **Declare blockers** — defending player assigns blockers. A blocked creature stays blocked even if blockers are removed.
4. **Combat damage** — first strike/double strike creatures deal damage first, then normal damage. Trample assigns lethal to blockers, remainder to defender.
5. **End of combat** — cleanup.

## Zones
Seven zones: **Library** (deck), **Hand**, **Battlefield** (permanents), **Graveyard** (discard pile), **Stack** (spells/abilities resolving), **Exile**, and **Command**. Cards move between zones per game rules and effects.

## Targeting
Spells/abilities with "target" require legal targets on casting. Targets are checked again on resolution — if all targets are illegal, the spell/ability is countered. Hexproof and protection can make targets illegal.

## Keyword Abilities
- **Flying** (702.9) — can only be blocked by flying/reach creatures.
- **First Strike** (702.2) — deals combat damage before normal creatures.
- **Double Strike** (702.15) — deals both first-strike and normal combat damage.
- **Deathtouch** (702.10) — any damage dealt is lethal.
- **Trample** (702.6) — excess combat damage carries over to defender.
- **Lifelink** (702.13) — damage dealt also gains you that much life.
- **Haste** (702.3) — can attack/tap the turn it enters.
- **Vigilance** (702.7) — attacking doesn't cause it to tap.
- **Reach** (702.5) — can block flying creatures.
- **Hexproof** (702.8) — can't be targeted by opponents.
- **Menace** (702.19) — must be blocked by 2+ creatures.
- **Flash** (702.12) — can be cast at instant speed.
- **Defender** (702.11) — can't attack.
- **Ward** (702.44) — taxes opponents for targeting.

## State-Based Actions (SBAs)
Checked whenever a player would get priority:
- Player at 0 or less life loses.
- Creature with 0 or less toughness → graveyard.
- Creature with lethal damage or deathtouch damage → destroyed.
- Planeswalker with 0 loyalty → graveyard.
- Legend rule: 2+ legendary permanents with same name → keep one.
- Unattached/illegal auras → graveyard.
"""


def generate_rules_overview(output_path: str | None = None) -> str:
    """Write the rules overview markdown to *output_path* and return its content.

    Args:
        output_path: Destination file path.  Defaults to
            ``benchmarks/sos/data/rules_overview.md`` relative to the repo root.

    Returns:
        The overview markdown as a string.
    """
    dest = Path(output_path) if output_path else _OVERVIEW_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_RULES_OVERVIEW_CONTENT, encoding="utf-8")
    logger.info("Wrote rules overview to %s", dest)
    return _RULES_OVERVIEW_CONTENT


def build_rules_index(rules_text: str) -> dict[str, list[str]]:
    """Parse rules text into a searchable index.

    Returns a dict with two kinds of keys:

    * **Rule numbers** (e.g. ``"702.9"``) → list of rule text lines for that
      number and its sub-rules.
    * **Keywords** (lowercase, e.g. ``"flying"``) → list of rule numbers that
      mention that keyword.
    """
    index: dict[str, list[str]] = {}
    rules_by_number: dict[str, list[str]] = {}

    # Parse numbered rules
    for match in _RULE_RE.finditer(rules_text):
        num = match.group(1)
        text = match.group(2).strip()
        # Store under the exact number
        rules_by_number.setdefault(num, []).append(text)
        # Also store sub-rules under parent number (e.g. 702.9a under 702.9)
        parent = _parent_rule(num)
        if parent and parent != num:
            rules_by_number.setdefault(parent, []).append(f"{num} {text}")

    # Copy rules_by_number into index
    for num, texts in rules_by_number.items():
        index[num] = texts

    # Build keyword → rule numbers mapping
    # Extract keywords from glossary and rule headings
    keyword_map: dict[str, set[str]] = {}

    # Scan all rule text for keyword extraction
    for num, texts in rules_by_number.items():
        full_text = " ".join(texts).lower()
        words = set(re.findall(r"[a-z]+", full_text))
        for word in words:
            if len(word) >= 3:  # skip very short words
                keyword_map.setdefault(word, set()).add(num)

    # Also parse glossary entries
    glossary_re = re.compile(r"^([A-Z][A-Za-z ]+?):\s+(.+)", re.MULTILINE)
    in_glossary = False
    for line in rules_text.split("\n"):
        if line.strip().lower() == "glossary:":
            in_glossary = True
            continue
        if in_glossary:
            gm = glossary_re.match(line)
            if gm:
                term = gm.group(1).strip().lower()
                body = gm.group(2)
                # Extract rule references
                refs = re.findall(r"\d{3}(?:\.\d+[a-z]?)?", body)
                for ref in refs:
                    keyword_map.setdefault(term, set()).add(ref)
                # Single-word terms also as individual keywords
                for word in term.split():
                    w = word.lower()
                    if len(w) >= 3:
                        for ref in refs:
                            keyword_map.setdefault(w, set()).add(ref)

    # Store keyword mappings in index (prefix with "kw:")
    for kw, nums in keyword_map.items():
        index.setdefault(f"kw:{kw}", []).extend(sorted(nums))

    return index


def lookup_rule(index: dict[str, list[str]], query: str) -> str:
    """Look up rules by number or keyword.

    Args:
        index: The rules index built by :func:`build_rules_index`.
        query: A rule number (e.g. ``"702.9"``) or keyword (e.g. ``"flying"``).

    Returns:
        A string containing the matching rule text, or a "not found" message.
    """
    query = query.strip()

    # Try exact rule number match first
    if query in index:
        return _format_rules(query, index[query])

    # Try as a keyword (lowercase)
    kw_key = f"kw:{query.lower()}"
    if kw_key in index:
        rule_nums = index[kw_key]
        sections: list[str] = []
        seen: set[str] = set()
        for num in rule_nums:
            if num in seen:
                continue
            seen.add(num)
            if num in index:
                sections.append(_format_rules(num, index[num]))
        if sections:
            return "\n\n".join(sections)

    # Partial match: try to find rule numbers that start with the query
    if re.match(r"^\d+", query):
        matches = []
        for key in sorted(index.keys()):
            if key.startswith(query) and not key.startswith("kw:"):
                matches.append(_format_rules(key, index[key]))
        if matches:
            return "\n\n".join(matches[:10])  # Limit output

    # Fallback: search all rule text
    q_lower = query.lower()
    results: list[str] = []
    for key, texts in sorted(index.items()):
        if key.startswith("kw:"):
            continue
        for text in texts:
            if q_lower in text.lower():
                results.append(f"[{key}] {text}")
                if len(results) >= 10:
                    break
        if len(results) >= 10:
            break
    if results:
        return "\n".join(results)

    return f"No rules found for query: {query!r}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parent_rule(num: str) -> str | None:
    """Return parent rule number, or None for top-level."""
    # "702.9a" -> "702.9", "702.9" -> "702", "702" -> None
    if re.match(r"^\d+\.\d+[a-z]$", num):
        return num[:-1]
    if re.match(r"^\d+\.\d+$", num):
        return num.split(".")[0]
    return None


def _format_rules(num: str, texts: list[str]) -> str:
    """Format rule texts for display."""
    header = f"Rule {num}:"
    body = "\n  ".join(texts)
    return f"{header}\n  {body}"
