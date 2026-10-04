"""Emit a fully self-contained Colab notebook for a single test clip.

Why this exists
---------------
``drive.mount()`` in Colab intermittently fails with
``MessageError: credential propagation was unsuccessful``. For a one-clip rehearsal
that is a pointless failure point: the whole point of Drive here was to ferry one
small JSON file in and one small MP4 out.

So this notebook has no Drive at all. The job list is baked into the notebook as a
base64 blob, which sidesteps every quoting problem a prompt full of commas would
otherwise cause, and the finished clip is handed back through
``google.colab.files.download``, which drops straight into the browser's download
folder.

Regenerate after changing the manifest::

    python tools\\make_oneshot_notebook.py [episode]
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import config  # noqa: E402

OUT_NAME = "sheesha_wan_oneshot.ipynb"

# Rehearsal settings. 81 frames at 30 steps is what a real clip needs; this cuts the
# generation to roughly 12 minutes on a T4. 49 frames satisfies Wan's 4k+1 rule.
TEST_FRAMES = 49
TEST_STEPS = 20


def build(ep: int) -> Path:
    manifest_path = config.episode_dir(ep) / "video_jobs.json"
    if not manifest_path.exists():
        raise SystemExit(f"no manifest at {manifest_path}\n"
                         f"  run: python pipeline.py video-jobs {ep} --test")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    jobs = manifest["jobs"]
    # This is a rehearsal, so shrink the generation job. The download is the
    # irreducible cost (~29 GB, ~17 min, all fp32 - the Diffusers repo ships no fp16
    # variant of the 22.7 GB umT5 encoder). Generation time, by contrast, is cheap to
    # give up: fewer frames and fewer steps still show whether the art direction and
    # the motion read correctly, in roughly a third of the time.
    for j in jobs:
        j["num_frames"] = int(TEST_FRAMES)
    manifest["steps"] = int(TEST_STEPS)
    blob = base64.b64encode(
        json.dumps(manifest, ensure_ascii=False).encode("utf-8")).decode("ascii")
    job_names = ", ".join(j["out_name"] for j in jobs)
    est = 17 + len(jobs) * (TEST_FRAMES / 81) * (TEST_STEPS / 30) * 30

    intro = (
        "# SHEESHA - one-shot test clip (no Google Drive needed)\n"
        "\n"
        f"Generates the test clip from episode {ep} and downloads it straight to\n"
        "your machine. This replaces the Drive-based notebook, which intermittently\n"
        "fails with `credential propagation was unsuccessful`.\n"
        "\n"
        "**Do these three things, in order:**\n"
        "\n"
        "1. **Runtime > Change runtime type > T4 GPU**, then Save. Skip this and the\n"
        "   GPU is not attached.\n"
        "2. Run every cell below, top to bottom. The model cell downloads about 29 GB\n"
        "   the first time; the last cell downloads your clip to the normal Downloads\n"
        "   folder.\n"
        "3. When the clip lands, copy it into this project at `render\\clips\\wan\\` and\n"
        "   run `python pipeline.py preview " + str(ep) + "`.\n"
        "\n"
        f"Expected file: `{job_names}`\n"
        "\n"
        f"Rehearsal settings: {TEST_FRAMES} frames at {TEST_STEPS} steps, not the full\n"
        "81/30. That is deliberate: the ~29 GB model download is the unavoidable cost\n"
        "(about 17 minutes, and this repo ships fp32 weights only), so generation time\n"
        "is what gets sacrificed. It is still enough to judge the look and the motion.\n"
        "\n"
        f"Budget roughly {est:.0f} minutes total, and run it straight through in one\n"
        "go. An interrupted session loses the download and has to start again. Keep the\n"
        "tab focused, do not let the laptop sleep, and do not click Stop. If it does\n"
        "disconnect, re-run the last two cells; finished work is skipped."
    )

    cells = [
        markdown(intro),
        code('!pip install -q --upgrade "diffusers>=0.33" transformers accelerate '
             'imageio imageio-ffmpeg ftfy sentencepiece'),
        code(
            "# The job list travels inside this notebook, so nothing has to be uploaded\n",
            "# and Drive is never touched.\n",
            "import base64, json, pathlib, time\n",
            "import torch\n",
            f"MANIFEST_B64 = \"{blob}\"\n",
            "manifest = json.loads(base64.b64decode(MANIFEST_B64))\n",
            "jobs = manifest[\"jobs\"]\n",
            "OUT = pathlib.Path(\"out\"); OUT.mkdir(exist_ok=True)\n",
            "\n",
            "gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"NONE\"\n",
            "vram = (torch.cuda.get_device_properties(0).total_memory / 2**30\n",
            "        if torch.cuda.is_available() else 0)\n",
            "print(f\"GPU     : {gpu} ({vram:.1f} GB)\")\n",
            "print(f\"episode : {manifest['episode']}   jobs: {len(jobs)}\")\n",
            "for j in jobs:\n",
            "    print(f\"  {j['id']} {j['kind']} {j['width']}x{j['height']} \"\n",
            "          f\"{j['num_frames']}f seed={j['seed']}\")\n",
            "print(f\"bfloat16 available: {torch.cuda.is_bf16_supported()}\")\n",
            "if \"T4\" not in gpu:\n",
            "    print(\"\\nWARNING: no T4. A GPU with under 10 GB will probably OOM.\")\n",
        ),
        code(
            "# float16, never bfloat16: a T4 is Turing (sm_75) and has no bf16 support.\n",
            "from diffusers import AutoencoderKLWan, WanPipeline\n",
            "\n",
            "MODEL = manifest[\"model\"]\n",
            "print(f\"loading {MODEL} ... (~9 GB of weights, this takes a few minutes)\")\n",
            "vae = AutoencoderKLWan.from_pretrained(\n",
            "    MODEL, subfolder=\"vae\", torch_dtype=torch.float32)\n",
            "pipe = WanPipeline.from_pretrained(MODEL, vae=vae, torch_dtype=torch.float16)\n",
            "pipe.set_progress_bar_config(disable=True)\n",
            "OFFLOAD = False   # set True if you get CUDA out of memory\n",
            "pipe.enable_model_cpu_offload() if OFFLOAD else pipe.to(\"cuda\")\n",
            "print(\"model ready\")\n",
        ),
        code(
            "from diffusers.utils import export_to_video\n",
            "\n",
            "for n, job in enumerate(jobs, 1):\n",
            "    out = OUT / job[\"out_name\"]\n",
            "    if out.exists() and out.stat().st_size > 20_000:\n",
            "        print(f\"[{n}/{len(jobs)}] {job['out_name']} already done, skipping\")\n",
            "        continue\n",
            "    print(f\"[{n}/{len(jobs)}] {job['id']} {job['kind']} seed={job['seed']}\")\n",
            "    t0 = time.time()\n",
            "    gen = torch.Generator(device=\"cuda\").manual_seed(int(job[\"seed\"]))\n",
            "    frames = pipe(\n",
            "        prompt=job[\"prompt\"],\n",
            "        negative_prompt=job[\"negative_prompt\"],\n",
            "        height=int(job[\"height\"]), width=int(job[\"width\"]),\n",
            "        num_frames=int(job[\"num_frames\"]),\n",
            "        guidance_scale=float(manifest[\"guidance_scale\"]),\n",
            "        num_inference_steps=int(manifest[\"steps\"]),\n",
            "        generator=gen,\n",
            "    ).frames[0]\n",
            "    export_to_video(frames, str(out), fps=int(job[\"fps\"]))\n",
            "    torch.cuda.empty_cache()\n",
            "    print(f\"    done in {time.time() - t0:.0f}s -> {out.name}\")\n",
            "print(\"generation complete\")\n",
        ),
        code(
            "# Hands the clip to your browser's normal download folder.\n",
            "from google.colab import files\n",
            "\n",
            "for job in jobs:\n",
            "    p = OUT / job[\"out_name\"]\n",
            "    if p.exists() and p.stat().st_size > 20_000:\n",
            "        print(f\"downloading {p.name} ({p.stat().st_size/1e6:.1f} MB)\")\n",
            "        files.download(str(p))\n",
            "    else:\n",
            "        print(f\"MISSING: {p.name}\")\n",
        ),
    ]

    nb = {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"provenance": [], "gpuType": "T4"},
            "kernelspec": {"display_name": "Python 3", "language": "python",
                           "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }
    out = ROOT / "notebooks" / OUT_NAME
    config.write_text(out, json.dumps(nb, ensure_ascii=False, indent=1) + "\n")
    return out


def markdown(*lines: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": list(lines)}


def code(*lines: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": list(lines)}


if __name__ == "__main__":
    ep = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    p = build(ep)
    print(f"wrote {p}")
    print(f"  {p.stat().st_size} bytes, self-contained, no Drive needed")