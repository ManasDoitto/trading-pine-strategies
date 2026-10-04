"""Scriptwriter agent: beat sheet -> voiceover script + shot list.

Two jobs, and the second one matters more than it looks:

1. Produce or load a ``script.json`` for an episode.
2. Guarantee the invariant that makes Devanagari captions possible without a
   translation step: every shot's Hinglish narration has a word-for-word parallel
   Devanagari line. The editor maps each synthesised word onto its Devanagari twin
   by index, so captions can never drift out of sync with the voice. If the counts
   disagree the script is rejected rather than captioned wrong.
"""

from __future__ import annotations

import re
from typing import Any

from lib import config, llm

SCHEMA = "sheesha.script/1"

SYSTEM = (
    "You are the scriptwriter for a Hindi horror Shorts channel. You write in Hinglish "
    "(Roman-script Hindi mixed with English) for the voiceover, and a word-for-word "
    "Devanagari line for on-screen captions. Hard rules: the hook lands in the first "
    "sentence; the last line is always a cliffhanger; no gore, no real persons, no "
    "brands, no guaranteed-profit language, no engagement bait. Total narration across "
    "all shots must be 60-80 words so it reads in about 26 seconds."
)


def content_words(text: str) -> list[str]:
    """Speech tokens only: drops punctuation and standalone symbols.

    edge-tts does not emit a WordBoundary for a bare dash or ellipsis, so caption
    alignment must ignore them too or every index after the dash shifts by one.
    """
    out = []
    for tok in text.split():
        stripped = tok.strip(".,!?;:—–-।॥\"'()[]\"“”")
        if stripped:
            out.append(stripped)
    return out


def validate(script: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if script.get("schema") != SCHEMA:
        problems.append(f"schema must be {SCHEMA!r}")
    shots = script.get("shots") or []
    if len(shots) < 3:
        problems.append("need at least 3 shots for a 30s episode")

    total_words = 0
    for s in shots:
        sid = s.get("id", "?")
        narration = s.get("narration_hinglish", "")
        if s.get("silent"):
            if not s.get("duration_hint_s"):
                problems.append(f"{sid}: silent shot needs duration_hint_s")
            continue
        if not narration.strip():
            problems.append(f"{sid}: empty narration")
            continue
        hing = content_words(narration)
        dev = content_words(s.get("caption_devanagari", ""))
        if len(hing) != len(dev):
            problems.append(
                f"{sid}: caption alignment broken - {len(hing)} narration words "
                f"vs {len(dev)} caption words"
            )
        if not re.search(r"[\u0900-\u097F]", s.get("caption_devanagari", "")):
            problems.append(f"{sid}: caption_devanagari has no Devanagari")
        for key in ("kind", "visual_prompt"):
            if not s.get(key):
                problems.append(f"{sid}: missing {key}")
        total_words += len(hing)

    # 30-90 words fits a 30s Short at the configured edge-tts rate: the floor catches
    # a stub that would leave half the runtime silent, the ceiling catches narration
    # that overruns. The editor fails hard if synthesised audio actually overruns.
    if total_words and not (30 <= total_words <= 90):
        problems.append(f"narration is {total_words} words, target 30-90 for a 30s Short")

    ids = [s.get("id") for s in shots]
    if len(set(ids)) != len(ids):
        problems.append("duplicate shot ids")
    return problems


def load_or_write(cfg: dict, ep: int, season: dict | None = None) -> dict[str, Any]:
    path = config.script_path(ep)
    existing = config.read_json(path)
    if existing:
        problems = validate(existing)
        if problems:
            raise ValueError(f"{path} failed validation:\n  - " + "\n  - ".join(problems))
        return existing

    if season is None:
        raise FileNotFoundError(
            f"{path} does not exist and no LLM is configured to write it. "
            f"Set llm.provider=openai with a model id, or author the file by hand."
        )

    beat = next((e for e in season["episodes"] if e["ep"] == ep), None)
    if beat is None:
        raise KeyError(f"episode {ep} is not in the season file")

    client = llm.client(cfg)
    if client is None:
        raise FileNotFoundError(f"{path} missing and llm.provider=static")

    user = (
        "Write one 30-second Short for this episode.\n"
        f"Episode {beat['ep']}, title {beat['title']}, place: {beat['place']}, "
        f"character present: {beat['character']}.\n"
        f"Beat: {beat['beat']}\n"
        f"Cliffhanger to land on: {beat['cliffhanger']}\n"
        f"Clue to plant: {beat['clue_planted']}\n"
        f"Available shot kinds: {', '.join(beat['visual_kinds'])}\n"
        "Available character silhouettes: sari_silhouette, cane_silhouette, doorway_presence, or null\n\n"
        "Return JSON with keys: title, hook_text_dev, cliffhanger, shots.\n"
        "Each shot: id (s1, s2, ...), kind, character_visual, narration_hinglish, "
        "caption_devanagari, on_screen_text_dev, visual_prompt, negative_extra.\n"
        "6 narrated shots plus one silent hold shot at the end with duration_hint_s.\n"
        "caption_devanagari must contain exactly the same number of Devanagari words as "
        "narration_hinglish contains Latin words, in the same order."
    )
    script = client.complete_json(SYSTEM, user)
    script.setdefault("schema", SCHEMA)
    script.setdefault("episode", ep)
    problems = validate(script)
    if problems:
        raise ValueError("generated script failed validation:\n  - " + "\n  - ".join(problems))
    config.write_json(path, script)
    config.log_line("scriptwriter", f"ep{ep} written by LLM")
    return script


def word_alignment(shot: dict[str, Any], words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map synthesised Latin words onto their authored Devanagari twins, in order.

    Falls back to proportional placement if the provider merged or split tokens,
    so a caption is always produced and never silently dropped.
    """
    dev_tokens = content_words(shot.get("caption_devanagari", ""))
    if not words:
        return []
    n_syn, n_dev = len(words), len(dev_tokens)
    if n_syn == n_dev:
        pairs = [(i, i) for i in range(n_syn)]
    elif n_dev >= 1:
        pairs = [(i, min(n_dev - 1, int(i * n_dev / n_syn))) for i in range(n_syn)]
    else:
        return []
    out = []
    for syn_i, dev_i in pairs:
        w = dict(words[syn_i])
        w["text"] = dev_tokens[dev_i]
        out.append(w)
    return out