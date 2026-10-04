# YouTube Horror Saga — Agentic Shorts Pipeline (Pilot-First)

## Goal

Build a fully agentic, ~$0 pipeline that produces one 30-second 9:16 YouTube Short per day
from an **original serialized horror saga** written in advance, with self-hosted open-weight
video generation. Ship **Episode 1 first** and inspect it before anything is batched.

## Decisions (settled with the user)

| Decision | Value |
|---|---|
| Niche | Original serialized horror saga, YouTube Shorts |
| Story | Inherited old house in a small North-Indian town + **one rule** |
| Language | Hinglish narration, **Devanagari** burned-in captions |
| Season | **Full 30-episode season planned upfront**, including the finale |
| Visual grammar | **First-person POV** handheld; place + rule + motif; **no recurring human face** |
| Generation | **Self-hosted** open-weight video model via ComfyUI |
| Cadence | 1/day target; **pilot → 3-episode batch → daily** |
| Human gate | **1 gate only**: approve the finished MP4. Every prior stage must self-gate. |
| LLM | OmniRoute local gateway (`localhost:20128`), free-tier API fallback |
| Scope exclusions | No Dhan token, no trading data, no cloud services, no paid tiers |

## Why these choices (do not silently revisit)

- Self-hosted video is the right call **only** for fiction. Real people, real events, and free-tier
  terms (watermark + non-commercial) were the reasons this was ruled out for a news channel.
- No recurring face: a consistent human face is the most expensive thing to keep stable on one GPU.
  A recurring **place + rule + motif** plus one recurring narrator voice buys continuity cheaply.
- 1 human gate means the guard stage must be a hard veto, not a warning, and regenerations must be
  automatic — a bad clip must never reach you.

## Architecture

Seven agents, each a separate module over a shared JSON state store. Every step is idempotent
and resumable from `state/`.

1. **Director** — owns `story_bible.json` (premise, house, rule text verbatim, timeline,
   entities, forbidden contradictions) and `season_30.json` (30 beat sheets: hook, place, beat,
   cliffhanger, clue planted, clue paid off, est. seconds). Maintains `continuity_ledger.md`
   after each publish. Picks the next episode; **vetoes** any beat that contradicts the bible.
2. **Scriptwriter** — beat sheet → voiceover. Structure: hook 0–1.5s (≤6 words), setup 1.5–8s,
   escalation 8–22s, reveal + cliffhanger 22–30s. Word budget sized so narration lands inside 30s
   (~70–80 words). Emits `shots[]` with narration, Devanagari on-screen text, and a visual ref.
3. **DOP** — owns `dop/grammar.json`: locked lens, height, movement, grain, palette, time-of-day,
   aspect. Version-locked — changing it invalidates the season's look and requires re-approval.
   Per shot: framing, motion, subject, lighting, duration, seed policy. Produces `shotlist.json`
   that exactly fills 30s.
4. **Prompt Engineer** — `prompts/style_base.txt` (shared, version-locked) + per-shot variation
   budget so clips don't all look identical; model-specific positive/negative prompt sets.
5. **Editor** — clip concat → trim to shotlist → ambience bed → voice at −3 dB over ambience →
   Devanagari captions → end card ("Episode N of 30" + next-episode tease) → 1080×1920 export,
   −14 LUFS. Emits a QC report.
6. **Guard** — hard veto on real named persons/brands, gore, hate/communal/religious targeting,
   real-crime depiction, copyrighted characters, claims of real events. Continuity check on
   entity names, rule text, timeline, unresolved clues. Writes `verdict.json` (PASS/VETO + reasons).
7. **Publisher** (phase 3) — title, description, AI-generated disclosure, resumable upload.
   Manual upload is the default until the pilot is approved.

Orchestrator: `pipeline.py` with `preflight | bible | season | episode N | batch N | publish | status`.

## Layout

```
D:\Trading code-Claude\yt_horror\
  config/pipeline.yaml        # duration, resolution, fps, loudness, paths
  config/hardware.yaml        # written by preflight: VRAM -> model profile
  story/brief.md              # premise + the rule (human-authored once)
  story/story_bible.json
  story/season_30.json
  story/continuity_ledger.md
  agents/{director,scriptwriter,dop,prompter,editor,guard}.py
  render/{clips,frames,audio,out}/
  qc/                         # verdict.json + qc.json per episode
  state/                      # resumable step state
  logs/ licenses.csv
  ComfyUI/                    # gitignored
  .gitignore
```

Note: this is a trading repo. Keep `yt_horror/` self-contained and add it to `.gitignore`.

## Environment verified on this PC

| Component | Status |
|---|---|
| NVIDIA GPU | **Present** — `C:\Windows\System32\nvcuda.dll` exists |
| Node.js | **Present** — `C:\Program Files\nodejs\node.exe`; OmniRoute gateway is usable |
| Python | **3.13 only** at `C:\Users\Manas\AppData\Local\Programs\Python\Python313` |
| CUDA Toolkit | Not installed — not required, PyTorch bundles its own runtime |
| ffmpeg / ffprobe | **Missing** — no chocolatey, scoop, or winget install found |
| VRAM | Undetermined; `preflight` reads it via `torch.cuda.get_device_properties` |

Two consequences for setup: **install ffmpeg** (free), and **create a dedicated Python 3.12 venv for
ComfyUI rather than using the system 3.13** — ComfyUI/PyTorch wheel support on 3.13 is uneven, and
the trading repo's interpreter must not be disturbed. This also keeps the horror pipeline out of the
trading project's dependency set.

Because an NVIDIA GPU is confirmed present, the visual stage is unblocked and the `$0` claim holds,
subject to the VRAM tier chosen at preflight (an integrated laptop GPU with 2–4 GB would drop to
LTX-Video @512px low-fps or a Colab fallback).

## Cost ledger — software is $0, the rest is not

**Genuinely $0, permanently:** Wan2.1/2.2 weights (**Apache-2.0**; model card claims no rights over
your generated content, so monetized use is clean) · ComfyUI + torch · ffmpeg, Pillow, Python ·
`piper-tts` (MIT, offline) · YouTube Data API (10,000 units/day → ~6 uploads/day) · Freesound CC0
and the YouTube Audio Library, with every asset logged to `licenses.csv` · OmniRoute **if** it
routes to a local model.

**Not $0 — state these honestly rather than claiming "free":**

1. **Electricity and hardware wear.** ~6 clips × ~5–10 min ≈ **~1 GPU-hour per 30s Short**, more with
   retries. At ~400 W that is roughly ₹4–8/day, plus fan/GPU degradation amortised over thousands of
   hours.
2. **A GPU you may not own.** If `preflight` finds no suitable NVIDIA card, the visual stage is
   blocked. Options are a one-time ₹25k–60k card, or free Colab/Kaggle GPU (still $0 but semi-manual,
   quota-limited, and their ToS discourage long unattended jobs).
3. **LLM only if OmniRoute proxies a paid provider.** A 30-episode season is small (~100–200k
   tokens), so even a paid API is negligible — but "entirely free" only holds on a local/free model.
   Free-tier fallback: Google AI Studio.
4. **Deliberately excluded costs** that a paid stack would impose: text-to-video APIs run
   $0.07–0.30 per 5s clip → ~$15–60/month at 1/day; paid TTS $5–22/month; stock subscriptions.
5. **Your time.** ~2 min/day review, plus the pilot.

**The largest non-monetary risk is not cost — it is monetization.** Shorts ad-share requires 10M
Shorts views in 90 days, and an all-AI channel is exactly the profile YouTube can classify as
mass-produced/repetitive. Running at $0 and earning $0 are separate problems; the mitigations in the
risk section exist for the second one.

## Free dependencies

Python 3.11+ (present), **ffmpeg/ffprobe (must verify/install — absent today)**, `piper-tts`
(offline, licence-clean) with `edge-tts` as a *secondary* path only — it is free but an unofficial
client, so it supplies `WordBoundary` caption timings opportunistically rather than being depended
on. Also `requests`, `pyyaml`, `jsonschema`, `pillow`, ComfyUI + torch, and Freesound CC0 /
YouTube Audio Library for ambience.

**Model selection is licence-gated, not just VRAM-gated:**

- **Primary — Wan.** `Wan2.1-T2V-1.3B` (Apache-2.0, ~8.2 GB VRAM, 480p — the low-VRAM anchor) and
  `Wan2.2-TI2V-5B` (Apache-2.0, 720p/24fps, roughly 10–16 GB). Pin the exact checkpoint ID in
  `config/hardware.yaml` and re-check its licence on every upgrade.
- **Fallback — LTX-Video, version-pinned.** Licence changed repeatedly: v0.9.0/v0.9.5 use
  OpenRAIL-M (use restrictions; the 0.9.0 text limited permitted purpose to non-commercial), while
  **v0.9.6+ "LTXV Open Weights License 0.X" allows free commercial use below $10M annual revenue**
  and requires a paid licence above it. Usable by an individual at $0, but it is not Apache-2.0 —
  pin ≥v0.9.6 and record the licence text in `licenses.csv`.

**Also verify:** a Devanagari font is bundled — otherwise captions render as tofu boxes.

## Ordered tasks

0. **Install ffmpeg** (free; `winget install ffmpeg` or the official build) and **create a Python 3.12
   venv** for the pipeline. Confirm `ffmpeg -version` and `ffprobe -version` before anything else.
1. **Preflight.** Detect GPU name + VRAM via torch, ffmpeg, TTS voices, OmniRoute model list. Write
   `config/hardware.yaml` selecting a licence-clean model profile from a VRAM tier table
   (≥16 GB → Wan2.2-TI2V-5B @720p/24fps · 10–15 GB → Wan2.2-TI2V-5B @720p with lower frame
   count or Wan2.1-T2V-1.3B · 8–9 GB → Wan2.1-T2V-1.3B @480p · <8 GB → LTX-Video ≥v0.9.6
   @512px low-fps, or free Colab/Kaggle GPU). Record the chosen licence per checkpoint.
   Fail loudly and print fallbacks. **This step decides whether the "entirely free" claim holds.**
2. **Write `story/brief.md`** — premise, the house, the rule in one sentence, tone, and the
   30-episode arc shape. Human-authored once, then version-locked.
3. **Director pass 1** → `story_bible.json` (entities, timeline, rule verbatim, forbidden states).
4. **Director pass 2** → `season_30.json`, all 30 beat sheets, planted-clue and payoff map.
   Human review this once — it is the contract for the whole season.
5. **DOP pass** → `dop/grammar.json` + `prompts/style_base.txt`. Lock them.
6. **Render smoke test.** One 5-second clip end-to-end. Proves the VRAM profile holds before
   any full episode.
7. **Build the remaining agents** (scriptwriter, prompter, editor, guard) against episode 1.
8. **Render Episode 1** → `render/out/ep01.mp4` + `qc/ep01_verdict.json` + `qc/ep01_qc.json`.
9. **Validate** (below). Watch it yourself. Only then batch.
10. **Batch 3 → then daily.** Add `publish` last, after the pilot is approved.

## Validation (the pilot is the gate)

`preflight` output is sane → smoke-test clip is watchable → then assert on `ep01.mp4`:
1080×1920; 30.0 s ±0.2; −14 LUFS ±1; no tofu glyphs; all shots present; no watermark;
narration intelligible on a phone speaker. Confirm the hook lands in the first second and the
cliffhanger pulls. Upload once as **unlisted** to validate metadata, AI-disclosure labelling, and
Shorts eligibility. Then decide manual vs API publishing.

## Risks and guards

- **No capable GPU** → preflight blocks the visual stage. Options: free Colab/Kaggle GPU
  (semi-manual), lower tier profile, or revisit the visual stack. This is the one hard blocker.
- **Unusable clip** → regenerate with a new seed, max 3 tries, then substitute a black+text beat.
  Never ship a bad clip, because the only human gate is at the end.
- **OmniRoute down / weak model** → fail closed. A bad script is the most expensive defect here.
- **Edge-TTS outage** → Piper fallback; if both fail, stop.
- **Every episode looking identical** → seed discipline + per-shot framing variation; variety
  comes from framing, not from style.
- **"Mass-produced / repetitive content" flag** → mitigations: original IP, one consistent
  narrator voice, per-episode distinct visuals, human review, season playlist grouping, and a
  description carrying real story context. YouTube's altered-content label + the IT Rules
  synthetic-content disclosure go on every upload.
- **Copyright** → self-generated footage only; CC0/licensed audio with a licenses manifest;
  no broadcaster clips, no brand logos, no real names.

## Success targets

- One finished 30 s MP4/day on one consumer GPU, **₹0 in software** (see cost ledger for the
  electricity/hardware/time that this does not include).
- Episode 1 approved by you before any batch runs.
- Channel judgement gate: publish 30 episodes, then apply fixed decision rules
  (median views < 300 → rewrite the hook; 300–1500 → change topic framing; > 1500 → double down).
  Single-episode numbers before 30 uploads are noise.

## Open questions

- Which OmniRoute models are configured, and whether any is strong enough to hold 30-beat-sheet
  coherence in one pass. `preflight` reports this; no local model available would drop the LLM stage
  to a free-tier API (Google AI Studio), still $0.
- Do you want to write the first draft of the premise and the rule yourself? (Recommended — the
  hook is the product, and it is cheap to change now and expensive later.)
- Channel name and branding (not blocking).
