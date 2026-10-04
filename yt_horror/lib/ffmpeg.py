"""ffmpeg/ffprobe discovery and invocation.

ffmpeg ships with Windows but is usually absent from PATH in the shell that runs
the pipeline (winget edits PATH for new sessions only), so discovery scans the
known winget install layout as well as PATH.
"""

from __future__ import annotations

import glob
import json
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from lib import config

FFMPEG_NAMES = ("ffmpeg.exe", "ffmpeg")
FFPROBE_NAMES = ("ffprobe.exe", "ffprobe")

_WINGET_GLOBS = (
    r"C:\Users\*\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*\bin",
    r"C:\Users\*\AppData\Local\Microsoft\WinGet\Packages\BtbN.FFmpeg_*\ffmpeg-*\bin",
)


class FFmpegMissing(RuntimeError):
    pass


def _scan_known_locations(names: Sequence[str]) -> Path | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)
    for pattern in _WINGET_GLOBS:
        for match in sorted(glob.glob(pattern), reverse=True):
            folder = Path(match)
            for name in names:
                candidate = folder / name
                if candidate.exists():
                    return candidate
    return None


@lru_cache(maxsize=1)
def ffmpeg_bin() -> Path:
    found = _scan_known_locations(FFMPEG_NAMES)
    if not found:
        raise FFmpegMissing(
            "ffmpeg not found. Install it with:  winget install --id Gyan.FFmpeg -e"
        )
    return found


@lru_cache(maxsize=1)
def ffprobe_bin() -> Path:
    found = _scan_known_locations(FFPROBE_NAMES)
    if not found:
        raise FFmpegMissing(
            "ffprobe not found. Install it with:  winget install --id Gyan.FFmpeg -e"
        )
    return found


def run(args: Sequence[str], *, desc: str = "") -> str:
    """Run an ffmpeg/ffprobe argument list. Raises on non-zero exit."""
    cmd = [str(ffmpeg_bin()), *[str(a) for a in args]]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-15:])
        raise RuntimeError(f"ffmpeg failed ({desc or ' '.join(map(str, args[:4]))}):\n{tail}")
    config.log_line("ffmpeg", f"ok: {desc or args[0]}")
    return proc.stderr or ""


def probe(path: Path | str) -> dict:
    """Full ffprobe JSON for a media file."""
    cmd = [
        str(ffprobe_bin()), "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {proc.stderr}")
    return json.loads(proc.stdout)


def duration_s(path: Path | str) -> float:
    return float(probe(path)["format"]["duration"])


def video_stream(path: Path | str) -> dict:
    for s in probe(path)["streams"]:
        if s.get("codec_type") == "video":
            return s
    raise RuntimeError(f"no video stream in {path}")


def audio_stream(path: Path | str) -> dict | None:
    for s in probe(path)["streams"]:
        if s.get("codec_type") == "audio":
            return s
    return None


def has_encoder(name: str) -> bool:
    """True if this ffmpeg build exposes the encoder (e.g. h264_nvenc)."""
    out = subprocess.run(
        [str(ffmpeg_bin()), "-hide_banner", "-encoders"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout or ""
    return name in out


def measure_loudness(path: Path | str) -> float | None:
    """Integrated loudness in LUFS, or None if the measurement cannot be parsed.

    ffmpeg prints a JSON block that is followed by more log lines, so the block has
    to be located rather than split on the first brace.
    """
    proc = subprocess.run(
        [str(ffmpeg_bin()), "-hide_banner", "-nostats", "-i", str(path),
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    match = re.search(r"\{[^{}]*\"input_i\"\s*:\s*\"(-?[\d.]+)\"[^{}]*\}", proc.stderr or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None