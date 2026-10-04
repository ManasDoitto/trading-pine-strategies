"""Paths, config loading and small shared helpers."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

CONFIG_PATH = ROOT / "config" / "pipeline.json"
STORY_DIR = ROOT / "story"
PROMPTS_DIR = ROOT / "prompts"
RENDER_DIR = ROOT / "render"
CLIPS_DIR = RENDER_DIR / "clips"
FRAMES_DIR = RENDER_DIR / "frames"
AUDIO_DIR = RENDER_DIR / "audio"
OUT_DIR = RENDER_DIR / "out"
QC_DIR = ROOT / "qc"
STATE_DIR = ROOT / "state"
LOGS_DIR = ROOT / "logs"
EPISODES_DIR = ROOT / "episodes"

BRIEF_PATH = STORY_DIR / "brief.md"
BIBLE_PATH = STORY_DIR / "story_bible.json"
SEASON_PATH = STORY_DIR / "season_30.json"
LEDGER_PATH = STORY_DIR / "continuity_ledger.md"
GRAMMAR_PATH = STORY_DIR / "dop_grammar.json"
STYLE_PATH = PROMPTS_DIR / "style_base.txt"
STYLE_VIDEO_PATH = PROMPTS_DIR / "style_base_video.txt"
LICENSES_PATH = ROOT / "licenses.csv"

ALL_DIRS = (
    CONFIG_PATH.parent, STORY_DIR, PROMPTS_DIR, RENDER_DIR, CLIPS_DIR,
    FRAMES_DIR, AUDIO_DIR, OUT_DIR, QC_DIR, STATE_DIR, LOGS_DIR, EPISODES_DIR,
)


def ensure_dirs() -> None:
    for d in ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)


def load_config(path: Path | None = None) -> dict[str, Any]:
    target = path or CONFIG_PATH
    with open(target, "r", encoding="utf-8") as fh:
        return json.load(fh)


def episode_id(n: int) -> str:
    return f"ep{n:02d}"


def episode_dir(n: int) -> Path:
    d = EPISODES_DIR / episode_id(n)
    d.mkdir(parents=True, exist_ok=True)
    return d


def script_path(n: int) -> Path:
    return episode_dir(n) / "script.json"


def state_path(name: str) -> Path:
    return STATE_DIR / name


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def log_line(stage: str, message: str) -> None:
    """Append a timestamped line to the run log. Keeps stdout clean for the report."""
    from datetime import datetime, timezone
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOGS_DIR / "pipeline.log", "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{stamp}\t{stage}\t{message}\n")


def slug(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
    return out.strip("-") or "shot"