"""Download all replay data from a 17lands replay page HTML file.

Usage:
    python scripts/download_replays.py <replay_page.html> <output_dir> [--session <cookie>]

Steps per the extraction guide (data/replays/extration_steps.md):
  1. Extract draft IDs from /details/<id> links in the HTML.
  2. Fetch event_details for each draft to get match/game counts.
  3. Fetch history_info for each (draft, match, game) to get the history path.
  4. Fetch the full replay JSON from /data/history.
"""

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

from curl_cffi import requests

BASE_URL = "https://www.17lands.com"

# Mimics a real browser so the API accepts the request.
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
}

DELAY_BASE = 10.0   # seconds
DELAY_JITTER = 5.0  # ± uniform jitter added to base delay


def _sleep() -> None:
    time.sleep(DELAY_BASE + random.uniform(-DELAY_JITTER, DELAY_JITTER))


def extract_draft_ids(html: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"/details/([a-f0-9]+)", html)))


def fetch_event_details(session: requests.Session, draft_id: str) -> dict:
    url = f"{BASE_URL}/data/event_details?draft_id={draft_id}"
    resp = session.get(url, headers={**HEADERS, "referer": f"{BASE_URL}/details/{draft_id}"})
    resp.raise_for_status()
    return resp.json()


def fetch_history_info(
    session: requests.Session, draft_id: str, match_index: int, game_index: int
) -> dict:
    url = (
        f"{BASE_URL}/data/history_info/"
        f"?draft_id={draft_id}&match_index={match_index}&game_index={game_index}"
    )
    resp = session.get(
        url,
        headers={
            **HEADERS,
            "referer": f"{BASE_URL}/history/{draft_id}/{match_index}/{game_index}",
        },
    )
    resp.raise_for_status()
    return resp.json()


def fetch_replay(session: requests.Session, history_path: str, draft_id: str) -> dict:
    from urllib.parse import quote

    encoded = quote(history_path, safe="")
    url = f"{BASE_URL}/data/history?history_path={encoded}"
    resp = session.get(
        url,
        headers={**HEADERS, "referer": f"{BASE_URL}/history/{draft_id}/0/0"},
    )
    resp.raise_for_status()
    return resp.json()


def download_all(
    html_path: Path,
    output_dir: Path,
    session_cookie: str | None,
    resume: bool = True,
) -> None:
    html = html_path.read_text(encoding="utf-8")
    draft_ids = extract_draft_ids(html)
    print(f"Found {len(draft_ids)} draft IDs in {html_path.name}")

    output_dir.mkdir(parents=True, exist_ok=True)

    http = requests.Session(impersonate="chrome")
    if session_cookie:
        http.cookies.set("session", session_cookie)
        http.cookies.set("logged_in", "true")

    total_games = 0
    for draft_num, draft_id in enumerate(draft_ids, 1):
        draft_dir = output_dir / draft_id
        details_path = draft_dir / "event_details.json"

        print(f"\n[{draft_num}/{len(draft_ids)}] Draft {draft_id}")

        if resume and details_path.exists():
            details = json.loads(details_path.read_text())
            print("  event_details cached — skipping fetch")
        else:
            try:
                details = fetch_event_details(http, draft_id)
            except requests.HTTPError as exc:
                print(f"  ERROR fetching event_details: {exc}")
                continue
            draft_dir.mkdir(parents=True, exist_ok=True)
            details_path.write_text(json.dumps(details, indent=2))
            _sleep()

        match_results = details.get("details", {}).get("match_results", [])
        print(f"  {len(match_results)} match(es)")

        for match_index, match in enumerate(match_results):
            game_results = match.get("game_results", [])
            for game_index, _ in enumerate(game_results):
                replay_path = draft_dir / f"match{match_index}_game{game_index}.json"
                info_path = draft_dir / f"match{match_index}_game{game_index}_info.json"

                if resume and replay_path.exists():
                    print(f"  match {match_index} game {game_index}: cached")
                    total_games += 1
                    continue

                if resume and info_path.exists():
                    info = json.loads(info_path.read_text())
                    print(f"  match {match_index} game {game_index}: history_info cached")
                else:
                    try:
                        info = fetch_history_info(http, draft_id, match_index, game_index)
                        info_path.write_text(json.dumps(info, indent=2))
                        _sleep()
                    except requests.HTTPError as exc:
                        print(f"  ERROR fetching history_info m{match_index}g{game_index}: {exc}")
                        continue

                history_path = info.get("history_path")
                if not history_path:
                    print(f"  WARN no history_path for m{match_index}g{game_index}")
                    continue

                try:
                    replay = fetch_replay(http, history_path, draft_id)
                    _sleep()
                except requests.HTTPError as exc:
                    print(f"  ERROR fetching replay m{match_index}g{game_index}: {exc}")
                    continue

                replay_path.write_text(json.dumps(replay, indent=2))
                print(f"  match {match_index} game {game_index}: saved ({history_path})")
                total_games += 1

    print(f"\nDone. {total_games} game replay(s) saved to {output_dir}/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download 17lands replay data from a replay page.")
    parser.add_argument("replay_page", type=Path, help="Path to replay page HTML file")
    parser.add_argument("output_dir", type=Path, help="Directory to write replay JSON files")
    parser.add_argument(
        "--session",
        metavar="COOKIE",
        help="Value of the 17lands 'session' cookie (required for auth-gated replays)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Re-download files even if they already exist",
    )
    args = parser.parse_args()

    if not args.replay_page.exists():
        print(f"ERROR: {args.replay_page} not found", file=sys.stderr)
        sys.exit(1)

    download_all(
        html_path=args.replay_page,
        output_dir=args.output_dir,
        session_cookie=args.session,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
