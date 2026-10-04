"""Prompt engineer agent: turns the shot list into model-ready prompts.

Even though the diffusion provider is gated off on this machine, this stays live
because it is what makes the prompts consistent across 30 episodes and across a
future GPU. The diffusion renderer consumes ``visual_prompt`` from these records;
the motion renderer ignores it, so nothing here can break today's render.

The rules it enforces:
  * a locked style base, applied to every shot
  * a fixed negative prompt, plus per-shot exclusions
  * a negative filter that blocks anything face-forward, because the channel is
    face-free by design, not by accident
  * a seed derived from episode and shot id, so a rerun reproduces exactly
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from lib import config

# Anything here blocks a prompt: the channel never shows a readable face.
FACE_BLOCKLIST = (
    "face", "facial features", "eyes", "portrait of", "close-up face",
    "detailed face", "photorealistic face", "selfie",
)

NEGATIVE_BASE = (
    "blurry, lowres, jpeg artifacts, watermark, text overlay, logo, "
    "cartoon, anime, 3d render, deformed hands, extra limbs, duplicate person, "
    "oversaturated, daylight, cheerful"
)


def style_base() -> str:
    """The locked style prefix, with the file's own comment header stripped.

    ``prompts/style_base.txt`` carries `#` notes explaining what the block is and
    why it is version-locked. Those notes are for the human editing the file; they
    must never reach the diffusion prompt, where they would be rendered as scene
    text. Reading the file verbatim was a real bug: every prompt shipped with the
    comment header inside it.
    """
    raw = config.read_text(config.STYLE_PATH, "")
    lines = [ln.strip() for ln in raw.splitlines()]
    body = [ln for ln in lines if ln and not ln.startswith("#")]
    return ", ".join(body)


def write_style_base(text: str) -> None:
    config.write_text(config.STYLE_PATH, text.strip() + "\n")
    config.log_line("prompter", "style base written")


def _merge_terms(*sources: str) -> str:
    """Join prompt term lists, dropping duplicates and empty entries.

    De-duplicating whole comma-joined strings is a no-op, because every source is a
    different string; the repeated terms only collapse when the list is split first.
    Order is preserved so the locked base always leads.
    """
    seen: dict[str, str] = {}
    for source in sources:
        for term in (source or "").split(","):
            key = term.strip().lower()
            if key and key not in seen:
                seen[key] = term.strip()
    return ", ".join(seen.values())


def seed_for(ep: int, shot_id: str, base: int) -> int:
    h = hashlib.sha256(f"{ep}:{shot_id}".encode("utf-8")).hexdigest()
    return base + (int(h[:8], 16) % 1_000_000)


def compile_prompt(shot: dict[str, Any], ep: int, cfg: dict,
                   base_style: str | None = None) -> dict[str, Any]:
    base_style = base_style if base_style is not None else style_base()
    positive = _merge_terms(base_style, shot.get("visual_prompt", ""))

    negatives = [NEGATIVE_BASE, cfg["visual"]["diffusion"]["negative"]]
    if shot.get("negative_extra"):
        negatives.append(shot["negative_extra"])
    if shot.get("character_visual"):
        # a silhouette is wanted; a face is not
        negatives.append("detailed face, facial features, eyes, portrait")

    negative = _merge_terms(*negatives)

    matched = [t for t in FACE_BLOCKLIST if re.search(rf"(?<!\w){re.escape(t)}(?!\w)",
                                                     shot.get("visual_prompt", "").lower())]

    return {
        "id": shot["id"],
        "kind": shot["kind"],
        "positive": positive,
        "negative": negative,
        "seed": seed_for(ep, shot["id"], int(cfg["visual"]["seed_base"])),
        "warnings": [f"prompt mentions {t!r}; check it is negating, not requesting" for t in matched],
    }


def build_promptset(script: dict[str, Any], ep: int, cfg: dict) -> list[dict[str, Any]]:
    base_style = style_base()
    return [compile_prompt(s, ep, cfg, base_style) for s in script["shots"]]