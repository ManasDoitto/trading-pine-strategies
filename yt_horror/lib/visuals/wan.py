"""Wan2.1 text-to-video provider, driven from a Google Colab T4 session.

Why this is split across two machines
-------------------------------------
Wan2.1-T2V-1.3B needs 8.19 GB in bf16, and even the Q4-GGUF offload floor is about
5 GB. This machine has 4 GB, so the model cannot run here at all. A free Colab T4 has
15 GB and runs it comfortably, which keeps the software cost at zero.

So this provider has no rendering code. It produces a job list, and a notebook in
``notebooks/`` turns that list into clips on Colab's GPU. The clips come back to
``render/clips/wan/`` and this module normalises and assembles them. Nothing else in
the pipeline changes: story, script, voices, captions, grade and QC are untouched.

The contract the notebook has to honour
---------------------------------------
For each job it writes ``<out_name>`` into its output directory, and nothing else is
read. The frame count in the job is the *allocation* (what the edit needs); the frame
count the notebook generates is the *generation* length (what the model is willing to
produce, in 4k+1 frames at 16 fps). Those are deliberately different numbers, and
:func:`prepare` reconciles them by slowing or freezing the generated clip.

Portrait, not landscape
-----------------------
Wan2.1 is trained at 480p and wants both dimensions divisible by 16. A Short is 9:16,
so generation is 480x832 and the result is upscaled to 1080x1920 locally. Generating
landscape and cropping would throw away two thirds of every frame.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lib import config, ffmpeg

NOTEBOOK_REL = "notebooks/sheesha_wan_colab.ipynb"


class ClipsMissing(RuntimeError):
    """Raised when the notebook has not yet produced every clip."""


def _join(*parts: str) -> str:
    """Comma-join prompt fragments, dropping empties and duplicate terms."""
    seen: dict[str, str] = {}
    for part in parts:
        for term in (part or "").split(","):
            key = term.strip().lower()
            if key and key not in seen:
                seen[key] = term.strip()
    return ", ".join(seen.values())


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg["visual"]["wan"]


def wan_dir() -> Path:
    d = config.CLIPS_DIR / "wan"
    d.mkdir(parents=True, exist_ok=True)
    return d


def wan_path() -> Path:
    """Read-only view of the clip directory. Used where creating it would be wrong:
    a check that reports missing clips should not bring the directory back to life."""
    return config.CLIPS_DIR / "wan"


def video_style_base() -> str:
    """The locked style prefix for generated clips, with the file's comments stripped."""
    raw = config.read_text(config.STYLE_VIDEO_PATH, "")
    body = [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    return ", ".join(body)


def out_name(shot: dict[str, Any]) -> str:
    """Filename shared by the manifest and the assembler. Both sides derive it here."""
    return f"ep{shot['ep']:02d}_{shot['id']}_{config.slug(shot['kind'])}_ai.mp4"


def build_jobs(cfg: dict[str, Any], ep: int, shots: list[dict[str, Any]],
               prompts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Turn the allocated timeline into a notebook-ready job list."""
    from agents import dop

    s = settings(cfg)
    v = cfg["video"]
    grammar = dop.load_grammar()
    cam = grammar.get("shot_kinds", {})

    # Wan2.1 wants both sides divisible by 16. 480x832 is the portrait 480p size.
    gen_h = int(s["gen_height"]) // 16 * 16
    gen_w = int(s["gen_width"]) // 16 * 16

    jobs: list[dict[str, Any]] = []
    style = video_style_base()
    for shot in shots:
        p = prompts.get(shot["id"], {})
        kind = shot["kind"]
        spec = cam.get(kind, {})
        camera = str(spec.get("camera", "slow push in")).strip()
        # The channel is face-free by design. One camera move in the grammar asked for
        # a push on a face, which would both break that rule and fight the prompt
        # engineer's own negative.
        camera = camera.replace("on the face", "on the clock")

        # The image style base is not reused here: it opens with "cinematic horror
        # still", and telling a video model the scene is a still invites a frozen
        # frame. Only the shot text and the seed are carried over from the prompter.
        positive = _join(style, shot.get("visual_prompt", ""), camera)
        if shot.get("character_visual"):
            positive += ", unidentifiable figure, face hidden, backlit silhouette only"

        # Wan has its own negative vocabulary. The image negatives (jpeg artifacts,
        # "cheerful") mean nothing to it, but the face block and the shot-specific
        # exclusions still do, so those are merged in rather than replaced.
        negative = _join(s["negative"], shot.get("negative_extra", ""),
                         ("detailed face, facial features, eyes, portrait"
                          if shot.get("character_visual") else ""))

        jobs.append({
            "id": shot["id"],
            "kind": kind,
            "out_name": out_name({**shot, "ep": ep}),
            "prompt": positive,
            "negative_prompt": negative,
            "seed": int(p.get("seed", s.get("seed_base", 20261003))),
            "height": gen_h,
            "width": gen_w,
            "num_frames": int(s["num_frames"]),
            "fps": int(s["gen_fps"]),
            # informational: what the edit needs, not what the model generates
            "want_frames": int(shot["frames"]),
            "want_duration": round(float(shot["duration"]), 4),
            "narration": shot.get("narration", ""),
        })

    return {
        "episode": ep,
        "schema": "sheesha.video_jobs/1",
        "model": s["model"],
        "steps": int(s["steps"]),
        "guidance_scale": float(s["guidance_scale"]),
        "delivery": {"width": int(v["width"]), "height": int(v["height"]),
                     "fps": int(v["fps"]), "duration_s": float(v["duration_s"])},
        "notes": [
            "Generate every job into out_name inside the output directory.",
            f"num_frames must be 4k+1; {s['num_frames']} is {int(s['num_frames'])} frames "
            f"at {s['gen_fps']} fps.",
            "float16 is required: a Colab T4 is Turing (sm_75) and has no bfloat16.",
        ],
        "jobs": jobs,
    }


def manifest_path(ep: int) -> Path:
    return config.episode_dir(ep) / "video_jobs.json"


def missing(cfg: dict[str, Any], ep: int, jobs: dict[str, Any]) -> list[str]:
    d = wan_path()
    return [j["out_name"] for j in jobs["jobs"] if not (d / j["out_name"]).exists()]


def _reject_placeholder(cfg: dict[str, Any], src: Path, job: dict[str, Any]) -> None:
    """Refuse a clip that is not the shape the notebook was told to produce.

    Worth guarding explicitly: a test-pattern or upscaled placeholder sitting in the
    clip directory would otherwise pass every duration and QC check and ship as
    though it were generated video. The only reliable tell is geometry, so compare
    against the manifest's own generation size.
    """
    want = (int(job["width"]), int(job["height"]))
    st = ffmpeg.probe(src)["streams"][0]
    got = (int(st["width"]), int(st["height"]))
    if got != want:
        raise ClipsMissing(
            f"{src.name} is {got[0]}x{got[1]}, but the manifest asked the notebook for "
            f"{want[0]}x{want[1]}.\n  This usually means a placeholder or an already-"
            f"rescaled file got left in the clip directory.\n  Delete {src} and put "
            f"the raw notebook output back.")


def prepare(src: Path, dst: Path, frames: int, cfg: dict[str, Any]) -> Path:
    """Normalise one generated clip to the exact allocated length and delivery size."""
    from lib.visuals.fit import fit

    return fit(src, dst, frames, cfg, int(settings(cfg).get("grain", 6)))


def collect(cfg: dict[str, Any], ep: int, jobs: dict[str, Any],
            shots: list[dict[str, Any]], force: bool = False) -> list[Path]:
    """Normalise every returned clip. Fails loudly rather than silently using the
    procedural provider, because a half-AI episode looks like a mistake."""
    d = wan_dir()
    gaps = missing(cfg, ep, jobs)
    if gaps:
        raise ClipsMissing(
            f"{len(gaps)} of {len(jobs['jobs'])} clips are missing from {d}.\n"
            f"  missing: {', '.join(gaps)}\n"
            f"  run {NOTEBOOK_REL} on Colab, or upload the clips into {d}."
        )

    out: list[Path] = []
    by_name = {j["out_name"]: j for j in jobs["jobs"]}
    for shot in shots:
        name = out_name({**shot, "ep": ep})
        src = d / name
        _reject_placeholder(cfg, src, by_name[name])
        dst = d / f"{config.slug(shot['id'])}_fit_{shot['frames']}.mp4"
        if dst.exists() and not force:
            out.append(dst)
            continue
        prepare(src, dst, int(shot["frames"]), cfg)
        out.append(dst)
    return out