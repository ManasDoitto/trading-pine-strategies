"""Director agent: owns the season's continuity.

The season file is the contract. This agent's real job is refusing to let the
pipeline ship an episode that contradicts it, and keeping the ledger of what the
audience has actually seen so arc 3 can pay off clues planted in arc 1.
"""

from __future__ import annotations

from typing import Any

from lib import config


def load() -> tuple[dict[str, Any], dict[str, Any]]:
    bible = config.read_json(config.BIBLE_PATH)
    season = config.read_json(config.SEASON_PATH)
    if bible is None:
        raise FileNotFoundError(f"{config.BIBLE_PATH} is missing - author story/bible first")
    if season is None:
        raise FileNotFoundError(f"{config.SEASON_PATH} is missing - author story/season first")
    return bible, season


def next_episode(season: dict[str, Any], published: set[int]) -> int | None:
    for e in sorted(season["episodes"], key=lambda x: x["ep"]):
        if e["ep"] not in published:
            return e["ep"]
    return None


def published_episodes() -> set[int]:
    """Episodes with a rendered final file, or an entry in the ledger."""
    done: set[int] = set()
    for f in config.OUT_DIR.glob("ep*.mp4"):
        try:
            done.add(int(f.stem[2:]))
        except ValueError:
            continue
    ledger = config.read_text(config.LEDGER_PATH, "")
    for line in ledger.splitlines():
        if line.startswith("- ep"):
            try:
                done.add(int(line.split()[1].rstrip(":")))
            except (IndexError, ValueError):
                continue
    return done


def seed_ledger(bible: dict[str, Any], season: dict[str, Any]) -> None:
    """Write the empty ledger once, with every clue tracked as an open promise."""
    if config.LEDGER_PATH.exists():
        return
    lines = [
        f"# Continuity ledger - {bible['title']}",
        "",
        "One line per published episode. The `open` column is the promise the season",
        "owes the audience; an entry stays open until the episode named in",
        "`paid_off_by` ships.",
        "",
        "| ep | title | clue planted | paid off by | status |",
        "|---|---|---|---|---|",
    ]
    for e in season["episodes"]:
        lines.append(
            f"| {e['ep']} | {e['title']} | {e.get('clue_planted') or '-'} | "
            f"{e.get('clue_paid_off') or '-'} | planned |"
        )
    lines += ["", "## Notes", ""]
    config.write_text(config.LEDGER_PATH, "\n".join(lines))
    config.log_line("director", "ledger seeded")


def record_published(bible: dict[str, Any], season: dict[str, Any], ep: int) -> None:
    """Mark an episode published and flag any clue that is now overdue."""
    beat = next((e for e in season["episodes"] if e["ep"] == ep), None)
    if beat is None:
        return
    text = config.read_text(config.LEDGER_PATH, "")
    stamp = f"- ep{ep}: {beat['title']} published"

    planted = beat.get("clue_planted")
    overdue: list[str] = []
    if planted:
        for e in season["episodes"]:
            if e.get("clue_planted") == planted and e["ep"] > ep:
                overdue.append(f"'{planted}' still open, due at ep{e['ep']}")
    if overdue:
        stamp += "\n  - OPEN PROMISES: " + "; ".join(overdue)

    config.write_text(config.LEDGER_PATH, text.rstrip() + "\n" + stamp + "\n")
    config.log_line("director", f"ep{ep} recorded")


def coverage(season: dict[str, Any]) -> dict[str, Any]:
    planned = {e["ep"] for e in season["episodes"]}
    published = published_episodes()
    return {
        "planned": len(planned),
        "published": len(published & planned),
        "remaining": sorted(planned - published),
    }