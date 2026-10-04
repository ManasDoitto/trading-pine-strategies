"""Preflight: decide whether this machine can run the pipeline, before any work starts.

The plan made this the gate that decides if the "$0" claim holds. On this box it
found a 4 GB GTX 1650 Max-Q, which is below the floor for every open video model,
so the diffusion provider refuses and the motion provider takes over.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from typing import Any

from lib import config, ffmpeg, llm, tts
from lib.visuals.diffusion import DiffusionProvider


def gpu_info() -> dict[str, Any] | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None
    if not out:
        return None
    parts = [p.strip() for p in out.splitlines()[0].split(",")]
    return {"name": parts[0], "vram_mb": int(float(parts[1])),
            "driver": parts[2] if len(parts) > 2 else ""}


def run(cfg: dict, write_hw: bool = True) -> dict[str, Any]:
    report: dict[str, Any] = {}
    report["python"] = sys.version.split()[0]
    report["platform"] = f"{platform.system()} {platform.release()}"

    try:
        report["ffmpeg"] = str(ffmpeg.ffmpeg_bin())
        report["ffmpeg_ok"] = True
        report["nvenc"] = ffmpeg.has_encoder("h264_nvenc")
    except ffmpeg.FFmpegMissing as exc:
        report["ffmpeg_ok"] = False
        report["ffmpeg_error"] = str(exc)

    report["gpu"] = gpu_info()

    voices = tts.list_voices()
    report["tts_voices"] = [v["name"] for v in voices]
    configured = cfg["audio"]["voice"]
    report["tts_ok"] = configured in report["tts_voices"] or bool(report["tts_voices"])
    if report["tts_voices"] and configured not in report["tts_voices"]:
        report["tts_ok"] = False

    report["llm"] = llm.describe(cfg)

    dp = DiffusionProvider(cfg)
    diff_ok, diff_why = dp.available()
    report["diffusion_available"] = diff_ok
    report["diffusion_reason"] = diff_why
    report["visual_provider"] = "diffusion" if diff_ok else "motion"

    report["models_needed_vram_mb"] = cfg["visual"]["diffusion"]["min_vram_mb"]
    report["monetisation_note"] = (
        "Software cost is 0. Electricity ~1 GPU-hour per Short is not, and an "
        "adequate GPU is a one-time purchase if this card cannot hold the tier."
    )

    story_ok = all(p.exists() for p in (config.BIBLE_PATH, config.SEASON_PATH, config.GRAMMAR_PATH))
    report["story_assets"] = story_ok

    if write_hw:
        config.write_json(ROOT_HW, {
            "generated_from": "preflight",
            "gpu": report["gpu"],
            "visual_provider": report["visual_provider"],
            "diffusion": {"available": diff_ok, "reason": diff_why,
                          "checkpoint": cfg["visual"]["diffusion"]["checkpoint"],
                          "min_vram_mb": cfg["visual"]["diffusion"]["min_vram_mb"]},
        })
        config.log_line("preflight", f"provider={report['visual_provider']}")
    return report


ROOT_HW = config.ROOT / "config" / "hardware.json"


def print_report(report: dict[str, Any]) -> None:
    print("=" * 68)
    print("PREFLIGHT")
    print("=" * 68)
    print(f"python        : {report['python']} on {report['platform']}")
    print(f"ffmpeg        : {'ok' if report['ffmpeg_ok'] else 'MISSING'} "
          f"{report.get('nvenc') and '(nvenc available)' or ''}")
    gpu = report["gpu"]
    if gpu:
        print(f"gpu           : {gpu['name']}  {gpu['vram_mb']} MB VRAM  driver {gpu['driver']}")
    else:
        print("gpu           : none detected")
    print(f"tts           : {'ok' if report['tts_ok'] else 'UNAVAILABLE'} "
          f"({', '.join(report['tts_voices']) or 'no voices'})")
    print(f"llm           : {report['llm']}")
    print(f"story assets  : {'present' if report['story_assets'] else 'MISSING'}")
    print("-" * 68)
    print(f"visual provider: {report['visual_provider']}")
    print(f"  diffusion    : {report['diffusion_reason']}")
    print("-" * 68)
    for k, v in report.items():
        if isinstance(v, dict):
            continue
        if k in ("gpu",):
            continue
        print(f"  {k:<13}: {v}")
    print("=" * 68)