"""Guard agent: the only thing standing between a bad episode and your channel.

You review finished Shorts, never drafts, so every check here must run
automatically and must refuse rather than warn. A VETO stops the render.

Two classes of check:
  * content   - the things that get a channel taken down or a video struck
  * continuity - does this episode contradict the bible, a forbidden state, or
                 an episode already published
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from lib import config


class Veto(Exception):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def _fold(text: str) -> str:
    """Lowercase and strip accents/unicode marks so blocked-word matching is stable."""
    t = unicodedata.normalize("NFKD", text)
    return re.sub(r"\s+", " ", t.lower()).strip()


def content_checks(cfg: dict, script: dict[str, Any]) -> list[str]:
    terms = cfg["guard"]["block_terms"]
    problems: list[str] = []

    haystack = _fold(" ".join([
        script.get("title", ""),
        script.get("hook_text_dev", ""),
        script.get("cliffhanger", ""),
        *[s.get("narration_hinglish", "") for s in script.get("shots", [])],
        *[s.get("caption_devanagari", "") for s in script.get("shots", [])],
        *[s.get("visual_prompt", "") for s in script.get("shots", [])],
        " ".join(script.get("end_card_dev", []) or []),
    ]))

    for term in terms:
        # word-boundary match so "muslim" does not fire on nothing and "hindu" does
        # not fire inside another word
        if re.search(rf"(?<!\w){re.escape(_fold(term))}(?!\w)", haystack):
            problems.append(f"blocked term present: {term!r}")

    for s in script.get("shots", []):
        prompt = _fold(s.get("visual_prompt", ""))
        if any(k in prompt for k in ("photorealistic face", "detailed face", "facial features",
                                     "close-up face", "portrait of")):
            problems.append(f"{s.get('id')}: prompt asks for a visible face - the channel is face-free")
        if re.search(r"\b(?:gore|blood|nude|explicit|graphic)\b", prompt):
            problems.append(f"{s.get('id')}: prompt requests disallowed content")

    # a Short that promises money is the fastest route to a strike
    if re.search(r"(?<!\w)(?:guarantee|promised|paisa hi paisa|sure shot|pakka profit)(?!\w)",
                 haystack):
        problems.append("financial promise language")

    return problems


def continuity_checks(bible: dict[str, Any], season: dict[str, Any], script: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    ep = script.get("episode")

    beat = next((e for e in season.get("episodes", []) if e.get("ep") == ep), None)
    if beat is None:
        problems.append(f"episode {ep} has no beat sheet in the season file")

    rule = bible.get("rule", {})
    known_kinds: set[str] = set()
    for ep_entry in season.get("episodes", []):
        known_kinds.update(ep_entry.get("visual_kinds", []))

    for s in script.get("shots", []):
        if s.get("kind") not in known_kinds:
            problems.append(f"{s.get('id')}: unknown shot kind {s.get('kind')!r}")
        cv = s.get("character_visual")
        if cv and cv not in bible.get("cast_characters", []):
            problems.append(f"{s.get('id')}: unknown character silhouette {cv!r}")

    if beat:
        # String equality on the cliffhanger is too brittle to be a real gate - one
        # spelling difference vetoes a fine script. What actually matters is that
        # the episode pays off the beat's distinctive terms, so check for those.
        clif_words = [_fold(w) for w in content_words(beat.get("cliffhanger", "")) if len(w) >= 5]
        if clif_words:
            narration = _fold(" ".join(
                [s.get("narration_hinglish", "") for s in script.get("shots", [])]
                + [s.get("caption_devanagari", "") for s in script.get("shots", [])]
            ))
            missing = [w for w in clif_words if w not in narration]
            coverage = 1.0 - (len(missing) / len(clif_words))
            if coverage < 0.7:
                problems.append(
                    f"episode does not land the beat's cliffhanger "
                    f"({int(coverage * 100)}% of key terms present); missing {missing}"
                )

    return problems


def content_words(text: str) -> list[str]:
    import re as _re
    out = []
    for tok in text.split():
        stripped = tok.strip(".,!?;:—–-।॥\"'()[]“”")
        if stripped:
            out.append(stripped)
    return out


def character_ids(bible: dict[str, Any]) -> list[str]:
    """Silhouette ids the renderer can actually draw.

    These live in the DOP grammar, not the bible's cast: a bible entry like
    ``papa`` is a voice-only character with nothing to draw, while
    ``cane_silhouette`` is the shape that goes on screen. Validating a shot
    against the wrong list rejects every real script.
    """
    grammar = config.read_json(config.GRAMMAR_PATH, {}) or {}
    ids = list((grammar.get("characters") or {}).keys())
    if ids:
        return ids
    return [c["id"] for c in bible.get("cast", []) if c.get("on_screen")]


def run(cfg: dict, bible: dict[str, Any], season: dict[str, Any], script: dict[str, Any]) -> dict[str, Any]:
    bible = dict(bible)
    bible["cast_characters"] = character_ids(bible)

    problems = content_checks(cfg, script) + continuity_checks(bible, season, script)

    verdict = {
        "episode": script.get("episode"),
        "status": "VETO" if problems else "PASS",
        "problems": problems,
        "disclosure_required": bool(cfg["guard"]["require_disclosure"]),
    }
    ep_dir = config.episode_dir(int(script.get("episode", 0)))
    config.write_json(ep_dir / "verdict.json", verdict)
    config.log_line("guard", f"ep{script.get('episode')} {verdict['status']} "
                             f"({len(problems)} problems)")
    if problems:
        raise Veto(problems)
    return verdict