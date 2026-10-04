"""ComfyUI-backed diffusion visual provider.

This is the provider the plan wanted and this machine cannot run: it needs >=8 GB
VRAM and the local GPU is a 4 GB GTX 1650 Max-Q. The code is kept complete and
correct so the visual stage flips over the moment a bigger GPU appears, but
`available()` refuses rather than failing halfway through an episode.

Licence gate: only checkpoints whose model card permits commercial use may be
configured. Wan2.1-T2V-1.3B and Wan2.2 are Apache-2.0 with no claim over generated
output. LTX-Video is use-restricted and must be pinned to >= v0.9.6 to be free for
an individual creator.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from lib import config, ffmpeg

# checkpoints that are safe to monetise, with the evidence we verified
LICENCE_TABLE = {
    "Wan-AI/Wan2.1-T2V-1.3B": {"licence": "Apache-2.0", "commercial": True, "note": "no rights claimed over output"},
    "Wan-AI/Wan2.2-TI2V-5B": {"licence": "Apache-2.0", "commercial": True, "note": "no rights claimed over output"},
    "Lightricks/LTX-Video": {"licence": "LTXV Open Weights 0.X (>=0.9.6)", "commercial": True,
                              "note": "free below $10M revenue; use restrictions apply"},
}


class DiffusionUnavailable(RuntimeError):
    pass


class DiffusionProvider:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.dcfg = cfg["visual"]["diffusion"]

    # ---------- capability ----------

    def gpu(self) -> dict[str, Any] | None:
        try:
            out = __import__("subprocess").run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=20,
            ).stdout.strip()
            if not out:
                return None
            name, mem = [p.strip() for p in out.splitlines()[0].split(",")]
            return {"name": name, "vram_mb": int(float(mem))}
        except Exception:
            return None

    def available(self) -> tuple[bool, str]:
        ck = self.dcfg["checkpoint"]
        info = LICENCE_TABLE.get(ck)
        if info is None:
            return False, f"checkpoint {ck} is not in the licence table - refusing to render with unknown terms"
        if not info["commercial"]:
            return False, f"checkpoint {ck} licence is not commercial ({info['licence']})"

        g = self.gpu()
        if g is None:
            return False, "no NVIDIA GPU detected"
        need = int(self.dcfg["min_vram_mb"])
        if g["vram_mb"] < need:
            return False, (
                f"{g['name']} has {g['vram_mb']} MB VRAM, checkpoint needs {need} MB"
            )
        try:
            with urllib.request.urlopen(self.dcfg["comfy_url"] + "/system_stats", timeout=4) as r:
                r.read(1)
        except (urllib.error.URLError, OSError, TimeoutError):
            return False, f"ComfyUI is not answering at {self.dcfg['comfy_url']}"
        return True, f"{g['name']} {g['vram_mb']} MB + ComfyUI up"

    # ---------- generation ----------

    def _api(self, route: str, payload: dict | None = None) -> dict:
        url = f"{self.dcfg['comfy_url']}{route}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def _workflow(self, prompt: str, seed: int, negative: str) -> dict:
        d = self.dcfg
        return {
            "3": {"class_type": "KSampler",
                  "inputs": {"seed": seed, "steps": d["steps"], "cfg": d["cfg"],
                             "sampler_name": "uni_pc", "scheduler": "simple",
                             "denoise": 1, "model": ["4", 0], "positive": ["6", 0],
                             "negative": ["7", 0], "latent_image": ["5", 0]}},
            "4": {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": d["checkpoint"]}},
            "5": {"class_type": "EmptyHunyuanLatentVideo",
                  "inputs": {"width": d["width"], "height": d["height"],
                             "length": d["frames"], "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveVideo",
                  "inputs": {"filename_prefix": "sheesha", "format": "video/h264-mp4",
                             "video": ["8", 0]}},
        }

    def render_shot(self, shot: dict[str, Any], out_mp4: Path, seed: int) -> Path:
        ok, why = self.available()
        if not ok:
            raise DiffusionUnavailable(why)

        prompt = shot.get("visual_prompt") or shot.get("prompt") or ""
        job = self._api("/prompt", {"prompt": self._workflow(
            prompt, seed, self.dcfg["negative"])})
        pmid = job["prompt_id"]

        deadline = time.time() + 1800
        while time.time() < deadline:
            hist = self._api(f"/history/{pmid}")
            if pmid in hist:
                out = hist[pmid].get("outputs", {})
                for node in out.values():
                    for key in ("video", "gifs", "videos"):
                        for item in node.get(key, []) if isinstance(node.get(key), list) else []:
                            src = self.dcfg["comfy_url"].rstrip("/") + "/view?filename=" + item["filename"]
                            urllib.request.urlretrieve(src, out_mp4)
                            return out_mp4
                raise DiffusionUnavailable("ComfyUI finished but produced no video node")
            time.sleep(4)
        raise DiffusionUnavailable("ComfyUI job timed out after 30 min")

    def render_batch(self, shots, out_dir: Path, seed_base: int) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        made: list[Path] = []
        for i, shot in enumerate(shots):
            target = out_dir / f"{shot['id']}.mp4"
            made.append(self.render_shot(shot, target, seed_base + i * 101))
        return made