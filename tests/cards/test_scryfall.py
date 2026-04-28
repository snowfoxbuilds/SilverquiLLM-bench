"""Tests for cards/scryfall.py — Scryfall API fetcher and parser.

Verifies:
- _parse_card converts Scryfall JSON to CardMetadata correctly.
- Creature cards with power/toughness are parsed.
- Non-creature cards have power/toughness as None.
- Pagination: multi-page responses return all cards.
- Cache: fresh cache file is used instead of network.
- Cache: stale/missing cache triggers network fetch.
- Empty set response returns empty list.
- Missing fields in Scryfall data use safe defaults.
- Rate limiting: sleep is called between paginated requests.

Uses unittest.mock throughout — no real HTTP requests.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, mock_open, patch

import pytest

from cards.registry import CardMetadata
from cards.scryfall import (
    SCRYFALL_SEARCH_URL,
    _parse_card,
    fetch_set,
)


# ---------------------------------------------------------------------------
# Helpers — sample Scryfall card JSON
# ---------------------------------------------------------------------------

def _creature_json(
    name: str = "Grizzly Bears",
    mana_cost: str = "{1}{G}",
    type_line: str = "Creature — Bear",
    oracle_text: str = "",
    power: str = "2",
    toughness: str = "2",
    colors: list[str] | None = None,
    keywords: list[str] | None = None,
    rarity: str = "common",
    set_code: str = "fdn",
    collector_number: str = "1",
) -> dict[str, Any]:
    d: dict[str, Any] = {
        "name": name,
        "mana_cost": mana_cost,
        "type_line": type_line,
        "oracle_text": oracle_text,
        "power": power,
        "toughness": toughness,
        "colors": colors or ["G"],
        "keywords": keywords or [],
        "rarity": rarity,
        "set": set_code,
        "collector_number": collector_number,
    }
    return d


def _noncreature_json(
    name: str = "Lightning Bolt",
    mana_cost: str = "{R}",
    type_line: str = "Instant",
    oracle_text: str = "Lightning Bolt deals 3 damage to any target.",
    colors: list[str] | None = None,
    keywords: list[str] | None = None,
    rarity: str = "common",
    set_code: str = "fdn",
    collector_number: str = "132",
) -> dict[str, Any]:
    return {
        "name": name,
        "mana_cost": mana_cost,
        "type_line": type_line,
        "oracle_text": oracle_text,
        "colors": colors or ["R"],
        "keywords": keywords or [],
        "rarity": rarity,
        "set": set_code,
        "collector_number": collector_number,
    }


def _scryfall_page(
    cards: list[dict[str, Any]],
    has_more: bool = False,
    next_page: str | None = None,
) -> dict[str, Any]:
    """Build a Scryfall-style response page."""
    result: dict[str, Any] = {
        "object": "list",
        "total_cards": len(cards),
        "has_more": has_more,
        "data": cards,
    }
    if next_page:
        result["next_page"] = next_page
    return result


# ---------------------------------------------------------------------------
# _parse_card tests
# ---------------------------------------------------------------------------

class TestParseCard:
    """Verify the _parse_card helper converts Scryfall JSON to CardMetadata."""

    def test_creature_card(self) -> None:
        """Creature JSON is parsed with power and toughness strings."""
        card_json = _creature_json(
            name="Grizzly Bears",
            power="2",
            toughness="2",
        )
        meta = _parse_card(card_json, set_code="fdn")
        assert isinstance(meta, CardMetadata)
        assert meta.name == "Grizzly Bears"
        assert meta.mana_cost_str == "{1}{G}"
        assert meta.type_line == "Creature — Bear"
        assert meta.power == "2"
        assert meta.toughness == "2"
        assert meta.colors == ["G"]
        assert meta.set_code == "fdn"

    def test_noncreature_card(self) -> None:
        """Non-creature JSON is parsed with power/toughness as None."""
        card_json = _noncreature_json()
        meta = _parse_card(card_json, set_code="fdn")
        assert meta.name == "Lightning Bolt"
        assert meta.power is None
        assert meta.toughness is None

    def test_keywords_parsed(self) -> None:
        """Keywords list is preserved in metadata."""
        card_json = _creature_json(
            name="Serra Angel",
            keywords=["Flying", "Vigilance"],
        )
        meta = _parse_card(card_json)
        assert meta.keywords == ["Flying", "Vigilance"]

    def test_set_code_from_json(self) -> None:
        """set_code comes from the JSON 'set' field when present."""
        card_json = _creature_json(set_code="m21")
        meta = _parse_card(card_json, set_code="fallback")
        # The impl uses card_json.get("set", set_code), so "m21" from JSON wins
        assert meta.set_code == "m21"

    def test_set_code_fallback(self) -> None:
        """set_code falls back to the function argument when 'set' missing from JSON."""
        card_json = _creature_json()
        del card_json["set"]
        meta = _parse_card(card_json, set_code="fallback_set")
        assert meta.set_code == "fallback_set"

    def test_missing_fields_use_defaults(self) -> None:
        """A minimal JSON object (missing most fields) still parses with defaults."""
        card_json: dict[str, Any] = {"name": "Mystery Card"}
        meta = _parse_card(card_json)
        assert meta.name == "Mystery Card"
        assert meta.mana_cost_str == ""
        assert meta.type_line == ""
        assert meta.oracle_text == ""
        assert meta.power is None
        assert meta.toughness is None
        assert meta.colors == []
        assert meta.keywords == []
        assert meta.rarity == ""
        assert meta.collector_number == ""

    def test_completely_empty_json(self) -> None:
        """An empty JSON dict produces a fully-defaulted CardMetadata."""
        meta = _parse_card({})
        assert meta.name == ""
        assert meta.power is None


# ---------------------------------------------------------------------------
# _parse_card — multi-face card tests (transform, adventure, split)
# ---------------------------------------------------------------------------

def _transform_card_json() -> dict[str, Any]:
    """Build a Scryfall-style transform card (e.g. Delver of Secrets).

    Transform cards have mana_cost, oracle_text, colors, power, and toughness
    under card_faces[0] (front face) rather than at the top level.
    """
    return {
        "name": "Delver of Secrets // Insectile Aberration",
        "type_line": "Creature — Human Wizard // Creature — Human Insect",
        "keywords": ["Transform"],
        "rarity": "common",
        "set": "mid",
        "collector_number": "47",
        # Top-level fields are MISSING or EMPTY for transform cards
        "mana_cost": "",
        "oracle_text": "",
        "colors": [],
        "card_faces": [
            {
                "name": "Delver of Secrets",
                "mana_cost": "{U}",
                "oracle_text": "At the beginning of your upkeep, look at the top card of your library. You may reveal that card. If an instant or sorcery card is revealed this way, transform Delver of Secrets.",
                "colors": ["U"],
                "power": "1",
                "toughness": "1",
                "type_line": "Creature — Human Wizard",
            },
            {
                "name": "Insectile Aberration",
                "mana_cost": "",
                "oracle_text": "Flying",
                "colors": ["U"],
                "power": "3",
                "toughness": "2",
                "type_line": "Creature — Human Insect",
            },
        ],
    }


def _adventure_card_json() -> dict[str, Any]:
    """Build a Scryfall-style adventure card (e.g. Bonecrusher Giant).

    Adventure cards have mana_cost and oracle_text under card_faces rather
    than at top level. Colors may or may not appear at the top level.
    """
    return {
        "name": "Bonecrusher Giant // Stomp",
        "type_line": "Creature — Giant // Instant — Adventure",
        "keywords": [],
        "rarity": "rare",
        "set": "eld",
        "collector_number": "115",
        # Top-level fields are MISSING/EMPTY for adventure cards
        "mana_cost": "",
        "oracle_text": "",
        "colors": [],
        "card_faces": [
            {
                "name": "Bonecrusher Giant",
                "mana_cost": "{2}{R}",
                "oracle_text": "Whenever Bonecrusher Giant becomes the target of a spell, Bonecrusher Giant deals 2 damage to that spell's controller.",
                "colors": ["R"],
                "power": "4",
                "toughness": "3",
                "type_line": "Creature — Giant",
            },
            {
                "name": "Stomp",
                "mana_cost": "{1}{R}",
                "oracle_text": "Damage can't be prevented this turn. Stomp deals 2 damage to any target.",
                "colors": ["R"],
                "type_line": "Instant — Adventure",
            },
        ],
    }


def _transform_card_no_toplevel_fields_json() -> dict[str, Any]:
    """Build a transform card where top-level mana_cost/oracle_text/colors are completely absent.

    Some Scryfall payloads omit these fields entirely at the top level rather
    than providing empty strings/lists.
    """
    return {
        "name": "Huntmaster of the Fells // Ravager of the Fells",
        "type_line": "Creature — Human Werewolf // Creature — Werewolf",
        "keywords": ["Transform"],
        "rarity": "mythic",
        "set": "dka",
        "collector_number": "140",
        # These fields are COMPLETELY ABSENT at the top level
        # (no "mana_cost", "oracle_text", "colors", "power", "toughness" keys)
        "card_faces": [
            {
                "name": "Huntmaster of the Fells",
                "mana_cost": "{2}{R}{G}",
                "oracle_text": "Whenever this creature enters or transforms into Huntmaster of the Fells, create a 2/2 green Wolf creature token and you gain 2 life.",
                "colors": ["R", "G"],
                "power": "2",
                "toughness": "2",
                "type_line": "Creature — Human Werewolf",
            },
            {
                "name": "Ravager of the Fells",
                "mana_cost": "",
                "oracle_text": "Trample\nWhenever this creature transforms into Ravager of the Fells, it deals 2 damage to target opponent or planeswalker and 2 damage to up to one target creature that player or that planeswalker's controller controls.",
                "colors": ["R", "G"],
                "power": "4",
                "toughness": "4",
                "type_line": "Creature — Werewolf",
            },
        ],
    }


class TestParseCardMultiFace:
    """Verify _parse_card correctly handles multi-face cards (card_faces fallback)."""

    def test_transform_card_mana_cost_from_front_face(self) -> None:
        """Transform card: mana_cost is read from card_faces[0] when top-level is empty."""
        card_json = _transform_card_json()
        meta = _parse_card(card_json, set_code="mid")
        assert meta.mana_cost_str == "{U}"

    def test_transform_card_oracle_text_from_front_face(self) -> None:
        """Transform card: oracle_text is read from card_faces[0] when top-level is empty."""
        card_json = _transform_card_json()
        meta = _parse_card(card_json, set_code="mid")
        assert "look at the top card" in meta.oracle_text

    def test_transform_card_colors_from_front_face(self) -> None:
        """Transform card: colors are read from card_faces[0] when top-level is empty list."""
        card_json = _transform_card_json()
        meta = _parse_card(card_json, set_code="mid")
        assert meta.colors == ["U"]

    def test_transform_card_power_toughness_from_front_face(self) -> None:
        """Transform card: power/toughness from card_faces[0] when not at top level."""
        card_json = _transform_card_json()
        meta = _parse_card(card_json, set_code="mid")
        assert meta.power == "1"
        assert meta.toughness == "1"

    def test_transform_card_preserves_toplevel_name(self) -> None:
        """Transform card: name is always from the top level (both faces combined)."""
        card_json = _transform_card_json()
        meta = _parse_card(card_json, set_code="mid")
        assert meta.name == "Delver of Secrets // Insectile Aberration"

    def test_transform_card_preserves_toplevel_type_line(self) -> None:
        """Transform card: type_line is from top level (combined type)."""
        card_json = _transform_card_json()
        meta = _parse_card(card_json, set_code="mid")
        assert meta.type_line == "Creature — Human Wizard // Creature — Human Insect"

    def test_transform_card_keywords_from_toplevel(self) -> None:
        """Transform card: keywords are taken from top level."""
        card_json = _transform_card_json()
        meta = _parse_card(card_json, set_code="mid")
        assert meta.keywords == ["Transform"]

    def test_adventure_card_mana_cost_from_front_face(self) -> None:
        """Adventure card: mana_cost is read from card_faces[0] (creature face)."""
        card_json = _adventure_card_json()
        meta = _parse_card(card_json, set_code="eld")
        assert meta.mana_cost_str == "{2}{R}"

    def test_adventure_card_oracle_text_from_front_face(self) -> None:
        """Adventure card: oracle_text is read from card_faces[0]."""
        card_json = _adventure_card_json()
        meta = _parse_card(card_json, set_code="eld")
        assert "becomes the target of a spell" in meta.oracle_text

    def test_adventure_card_colors_from_front_face(self) -> None:
        """Adventure card: colors from card_faces[0] when top-level is empty."""
        card_json = _adventure_card_json()
        meta = _parse_card(card_json, set_code="eld")
        assert meta.colors == ["R"]

    def test_adventure_card_power_toughness(self) -> None:
        """Adventure card: power/toughness from card_faces[0] (creature face)."""
        card_json = _adventure_card_json()
        meta = _parse_card(card_json, set_code="eld")
        assert meta.power == "4"
        assert meta.toughness == "3"

    def test_transform_card_toplevel_fields_absent(self) -> None:
        """When top-level mana_cost/oracle_text/colors keys are completely missing,
        fallback to card_faces[0] still works."""
        card_json = _transform_card_no_toplevel_fields_json()
        meta = _parse_card(card_json, set_code="dka")
        assert meta.mana_cost_str == "{2}{R}{G}"
        assert "create a 2/2 green Wolf" in meta.oracle_text
        assert meta.colors == ["R", "G"]
        assert meta.power == "2"
        assert meta.toughness == "2"

    def test_single_face_card_still_works(self) -> None:
        """Single-face card (no card_faces key) still parses correctly — no regression."""
        card_json = _creature_json(
            name="Llanowar Elves",
            mana_cost="{G}",
            power="1",
            toughness="1",
            colors=["G"],
        )
        meta = _parse_card(card_json, set_code="fdn")
        assert meta.name == "Llanowar Elves"
        assert meta.mana_cost_str == "{G}"
        assert meta.power == "1"
        assert meta.toughness == "1"
        assert meta.colors == ["G"]

    def test_toplevel_values_take_precedence_over_faces(self) -> None:
        """If top-level fields are present AND non-empty, they take precedence over card_faces."""
        card_json: dict[str, Any] = {
            "name": "Hybrid Card",
            "mana_cost": "{W}{U}",
            "oracle_text": "Top level text.",
            "colors": ["W", "U"],
            "power": "3",
            "toughness": "3",
            "type_line": "Creature — Something",
            "keywords": [],
            "rarity": "rare",
            "set": "test",
            "collector_number": "1",
            "card_faces": [
                {
                    "mana_cost": "{W}",
                    "oracle_text": "Face text.",
                    "colors": ["W"],
                    "power": "1",
                    "toughness": "1",
                },
                {
                    "mana_cost": "{U}",
                    "oracle_text": "Back face text.",
                    "colors": ["U"],
                    "power": "2",
                    "toughness": "2",
                },
            ],
        }
        meta = _parse_card(card_json, set_code="test")
        # Top-level values should win
        assert meta.mana_cost_str == "{W}{U}"
        assert meta.oracle_text == "Top level text."
        assert meta.colors == ["W", "U"]
        assert meta.power == "3"
        assert meta.toughness == "3"


# ---------------------------------------------------------------------------
# fetch_set — single page (mocked network)
# ---------------------------------------------------------------------------

class TestFetchSetSinglePage:
    """Verify fetch_set with a single-page Scryfall response."""

    @patch("cards.scryfall._fetch_json")
    def test_single_page_returns_cards(self, mock_fetch: MagicMock) -> None:
        """Single-page response returns all cards."""
        cards = [_creature_json(name="Bear"), _noncreature_json(name="Bolt")]
        mock_fetch.return_value = _scryfall_page(cards)

        result = fetch_set("fdn", use_cache=False)

        assert len(result) == 2
        assert all(isinstance(m, CardMetadata) for m in result)
        assert result[0].name == "Bear"
        assert result[1].name == "Bolt"

    @patch("cards.scryfall._fetch_json")
    def test_empty_set_returns_empty_list(self, mock_fetch: MagicMock) -> None:
        """An empty set response returns an empty list."""
        mock_fetch.return_value = _scryfall_page([])
        result = fetch_set("empty", use_cache=False)
        assert result == []

    @patch("cards.scryfall._fetch_json")
    def test_url_contains_set_code(self, mock_fetch: MagicMock) -> None:
        """The initial request URL contains the set code."""
        mock_fetch.return_value = _scryfall_page([])
        fetch_set("m21", use_cache=False)
        called_url = mock_fetch.call_args[0][0]
        assert "m21" in called_url


# ---------------------------------------------------------------------------
# fetch_set — pagination
# ---------------------------------------------------------------------------

class TestFetchSetPagination:
    """Verify fetch_set paginates through multiple pages."""

    @patch("cards.scryfall.time.sleep")
    @patch("cards.scryfall._fetch_json")
    def test_two_pages_returns_all_cards(
        self, mock_fetch: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        """Two-page response aggregates all cards from both pages."""
        page1 = _scryfall_page(
            [_creature_json(name="Bear")],
            has_more=True,
            next_page="https://api.scryfall.com/cards/search?page=2",
        )
        page2 = _scryfall_page([_noncreature_json(name="Bolt")])
        mock_fetch.side_effect = [page1, page2]

        result = fetch_set("fdn", use_cache=False)

        assert len(result) == 2
        assert result[0].name == "Bear"
        assert result[1].name == "Bolt"

    @patch("cards.scryfall.time.sleep")
    @patch("cards.scryfall._fetch_json")
    def test_pagination_respects_rate_limit(
        self, mock_fetch: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        """time.sleep is called between paginated requests."""
        page1 = _scryfall_page(
            [_creature_json(name="Bear")],
            has_more=True,
            next_page="https://api.scryfall.com/cards/search?page=2",
        )
        page2 = _scryfall_page([_noncreature_json(name="Bolt")])
        mock_fetch.side_effect = [page1, page2]

        fetch_set("fdn", use_cache=False)

        # sleep should be called at least once (between page 1 and page 2)
        mock_sleep.assert_called()
        # Verify it's called with the expected delay (0.1 seconds)
        args = mock_sleep.call_args[0]
        assert args[0] == pytest.approx(0.1, abs=0.05)

    @patch("cards.scryfall.time.sleep")
    @patch("cards.scryfall._fetch_json")
    def test_three_pages(
        self, mock_fetch: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        """Three-page response returns all 3 cards."""
        pages = [
            _scryfall_page(
                [_creature_json(name="Card1")], has_more=True,
                next_page="https://api.scryfall.com/page2",
            ),
            _scryfall_page(
                [_creature_json(name="Card2")], has_more=True,
                next_page="https://api.scryfall.com/page3",
            ),
            _scryfall_page([_creature_json(name="Card3")]),
        ]
        mock_fetch.side_effect = pages

        result = fetch_set("fdn", use_cache=False)
        assert len(result) == 3
        names = [m.name for m in result]
        assert names == ["Card1", "Card2", "Card3"]


# ---------------------------------------------------------------------------
# fetch_set — caching
# ---------------------------------------------------------------------------

class TestFetchSetCache:
    """Verify cache read/write behavior."""

    @patch("cards.scryfall._fetch_json")
    @patch("cards.scryfall._is_cache_fresh", return_value=True)
    def test_fresh_cache_skips_network(
        self, mock_fresh: MagicMock, mock_fetch: MagicMock, tmp_path: Path,
    ) -> None:
        """When a fresh cache exists, no network request is made."""
        cached_cards = [_creature_json(name="CachedBear")]
        cache_file = tmp_path / "fdn.json"
        cache_file.write_text(json.dumps(cached_cards))

        with patch("cards.scryfall._cache_path", return_value=cache_file):
            result = fetch_set("fdn", use_cache=True)

        mock_fetch.assert_not_called()
        assert len(result) == 1
        assert result[0].name == "CachedBear"

    @patch("cards.scryfall._is_cache_fresh", return_value=False)
    @patch("cards.scryfall._fetch_json")
    def test_stale_cache_triggers_fetch(
        self, mock_fetch: MagicMock, mock_fresh: MagicMock, tmp_path: Path,
    ) -> None:
        """When cache is stale, a network fetch happens."""
        mock_fetch.return_value = _scryfall_page([_creature_json(name="FreshBear")])

        with patch("cards.scryfall._cache_path", return_value=tmp_path / "fdn.json"), \
             patch("cards.scryfall._CACHE_DIR", tmp_path):
            result = fetch_set("fdn", use_cache=True)

        mock_fetch.assert_called_once()
        assert result[0].name == "FreshBear"

    @patch("cards.scryfall._fetch_json")
    def test_cache_disabled_skips_cache_read(
        self, mock_fetch: MagicMock, tmp_path: Path,
    ) -> None:
        """use_cache=False bypasses cache and always fetches."""
        mock_fetch.return_value = _scryfall_page([_creature_json(name="Fresh")])

        result = fetch_set("fdn", use_cache=False)

        mock_fetch.assert_called_once()
        assert result[0].name == "Fresh"

    @patch("cards.scryfall._is_cache_fresh", return_value=False)
    @patch("cards.scryfall._fetch_json")
    def test_cache_written_after_fetch(
        self, mock_fetch: MagicMock, mock_fresh: MagicMock, tmp_path: Path,
    ) -> None:
        """After fetching, the cache file is written."""
        cards_data = [_creature_json(name="Bear")]
        mock_fetch.return_value = _scryfall_page(cards_data)
        cache_file = tmp_path / "fdn.json"

        with patch("cards.scryfall._cache_path", return_value=cache_file), \
             patch("cards.scryfall._CACHE_DIR", tmp_path):
            fetch_set("fdn", use_cache=True)

        assert cache_file.exists()
        written = json.loads(cache_file.read_text())
        assert len(written) == 1
        assert written[0]["name"] == "Bear"


# ---------------------------------------------------------------------------
# fetch_set — set_code normalization
# ---------------------------------------------------------------------------

class TestFetchSetCodeNormalization:
    """Verify that set codes are lowercased."""

    @patch("cards.scryfall._fetch_json")
    def test_uppercase_set_code_lowercased(self, mock_fetch: MagicMock) -> None:
        """fetch_set('FDN') normalizes the code to lowercase in the URL."""
        mock_fetch.return_value = _scryfall_page([])
        fetch_set("FDN", use_cache=False)
        called_url = mock_fetch.call_args[0][0]
        assert "fdn" in called_url
        # Should NOT contain uppercase FDN in the URL
        assert "FDN" not in called_url


# ---------------------------------------------------------------------------
# _is_cache_fresh helper
# ---------------------------------------------------------------------------

class TestIsCacheFresh:
    """Verify the _is_cache_fresh helper function."""

    def test_nonexistent_file_is_not_fresh(self, tmp_path: Path) -> None:
        """A path that does not exist is not fresh."""
        from cards.scryfall import _is_cache_fresh
        assert _is_cache_fresh(tmp_path / "nope.json") is False

    def test_recent_file_is_fresh(self, tmp_path: Path) -> None:
        """A file just created (age ~0) is fresh with default max_age."""
        from cards.scryfall import _is_cache_fresh
        p = tmp_path / "test.json"
        p.write_text("[]")
        assert _is_cache_fresh(p) is True

    def test_custom_max_age_zero_makes_everything_stale(self, tmp_path: Path) -> None:
        """A max_age of 0 makes even a brand-new file stale (mtime is in the past)."""
        from cards.scryfall import _is_cache_fresh
        p = tmp_path / "test.json"
        p.write_text("[]")
        # Age will be >= 0; with max_age=0, _is_cache_fresh returns age < 0 → False
        assert _is_cache_fresh(p, max_age=0) is False
