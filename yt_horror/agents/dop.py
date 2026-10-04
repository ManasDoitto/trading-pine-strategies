"""DOP agent: owns the camera grammar and resolves each shot's optics.

The grammar in story/dop_grammar.json is version-locked. This agent reads it, merges
it with the shot list the scriptwriter produced, and writes the shotlist the visual
provider consumes. It never invents style - if a shot asks for something outside the
locked grammar it is rejected rather than quietly restyled, because 30 episodes only
look like one film if the style cannot drift.
"""

from __future__ import annotations

from typing import Any

from lib import config


def load_grammar() -> dict[str, Any]:
    grammar = config.read_json(config.GRAMMAR_PATH)
    if grammar is None:
        raise FileNotFoundError(
            f"{config.GRAMMAR_PATH} is missing. The camera grammar is authored once and "
            f"then locked; the renderer has no defaults for it."
        )
    return grammar


def resolve(shot: dict[str, Any], grammar: dict[str, Any]) -> dict[str, Any]:
    kind = shot["kind"]
    spec = grammar["shot_kinds"].get(kind)
    if spec is None:
        raise KeyError(f"shot kind {kind!r} is not in the locked grammar")

    char = shot.get("character_visual")
    if char and char not in grammar["characters"]:
        raise KeyError(f"character silhouette {char!r} is not in the locked grammar")

    return {
        **shot,
        "palette": spec["palette"],
        "camera": spec["camera"],
        "fog": spec.get("fog", 0.3),
        "lens_mm": grammar["camera"]["lens_equivalent_mm"],
        "rim_light": bool(grammar["characters"].get(char, {}).get("rim_light", 0)) if char else False,
        "caption_band": grammar["camera"]["safe_caption_band_y"],
    }


def build_shotlist(script: dict[str, Any], durations: list[float],
                   grammar: dict[str, Any]) -> list[dict[str, Any]]:
    if len(durations) != len(script["shots"]):
        raise ValueError(f"{len(durations)} durations for {len(script['shots'])} shots")
    out = []
    for shot, dur in zip(script["shots"], durations):
        resolved = resolve(shot, grammar)
        resolved["duration"] = round(dur, 3)
        out.append(resolved)
    return out


def describe(grammar: dict[str, Any]) -> str:
    return (f"grammar v{grammar['version']} locked={grammar.get('locked')} "
            f"| {len(grammar['shot_kinds'])} shot kinds "
            f"| {len(grammar['characters'])} characters")