# SHEESHA — agentic horror Shorts pipeline

Produces one 30-second, 1080×1920, Hindi/Hinglish YouTube Short per day from a
30-episode horror saga that is planned in advance. Faceless: no presenter, no visible
faces, no photoreal footage. Characters are recurring **silhouettes with distinct voices**.

Software cost is **₹0**. One episode rendered on this machine at zero marginal cost.

---

## This machine

`python pipeline.py preflight` is the gate. On this box it reports:

```
gpu           : GeForce GTX 1650 with Max-Q Design  4096 MB VRAM
ffmpeg        : ok (nvenc available)
tts           : ok (hi-IN-MadhurNeural, hi-IN-SwaraNeural, ...)
visual provider: wan (clips generated on a free Colab T4)
```

**Your GPU cannot generate video.** Wan2.1-T2V-1.3B needs 8.19 GB in bf16, and even
the Q4-GGUF offload floor is ~5 GB. You have 4 GB. There is also no free keyless video
API — the free image endpoint returns `image/jpeg` and every video route returns `401`.

So clips are generated on a **free Google Colab T4** (15 GB) via
`notebooks/sheesha_wan_colab.ipynb`. Software cost stays ₹0. The cost is wall-clock
and attention: roughly 30 minutes per 5-second clip, so 3–4 hours per episode, and
Colab disconnects idle sessions. The notebook is resumable, so a disconnect costs the
clip in progress, not the episode.

## Commands

```powershell
python pipeline.py preflight          # can this machine run it, and with which provider
python pipeline.py status             # what is rendered, what the season still owes
python pipeline.py episode 1          # guard -> TTS -> visuals -> edit -> QC
python pipeline.py episode 1 --force  # re-render even if cached
python pipeline.py batch 1 3          # episodes 1..3
python pipeline.py video-jobs 1       # write the clip manifest for the Colab notebook
python pipeline.py prompts 1          # the compiled diffusion prompt set for ep1
python pipeline.py publish 1          # upload metadata + AI disclosure text
```

Output lands in `render/out/epNN.mp4`. Watch it, and if it is good, publish it.
That single human check is the only approval gate in the system.

## Making an episode

### 1. Local — write the job manifest

```powershell
python pipeline.py video-jobs 1
```

This runs the guard, synthesises the voice, allocates the timeline and writes
`episodes/ep01/video_jobs.json`: one job per shot with the prompt, negative, seed,
portrait generation size and output filename.

### 2. Colab — generate the clips

Upload `video_jobs.json` to Google Drive at `MyDrive/sheesha/`. Open
`notebooks/sheesha_wan_colab.ipynb`, set **Runtime → Change runtime type → T4 GPU**,
and run the cells. It downloads the model once (~9 GB), then writes one `.mp4` per job
into `MyDrive/sheesha/clips/` and zips it.

### 3. Local — assemble

Unzip `clips.zip` over `render/clips/wan/` and run:

```powershell
python pipeline.py episode 1 --provider wan
```

Each generated clip is 5.0 s but shots need 2.4–6.8 s. The assembler trims the long
ones and **slows** the short ones rather than freezing them, because a held final frame
reads as a freeze-frame while a modest slow-down reads as ordinary slow camera work.
Everything is cut to an exact frame count, then upscaled 480×832 → 1080×1920 and
graded to match the rest of the season.

## How an episode is built

```
season_30.json (beat sheet)
   └─ guard          content veto + continuity check   ← refuses before any work
   └─ scriptwriter   narration + shot list
   └─ tts            one call per shot → per-shot duration IS the shot duration
   └─ prompter       locked style base + negatives + seeds
   └─ dop            camera grammar, palette, character silhouette per shot
   └─ video-jobs     manifest of prompts/seeds/frames          → Colab
   └─ collect        clip fit: trim / slow-down / upscale / grade
   └─ editor         concat → ambience+voice mix → loudness → burn captions → QC
   └─ director       record in the continuity ledger, flag overdue clues
```

## Five decisions that are load-bearing

**The picture is timed to the voice, not the reverse.** Each shot's line is synthesised
separately, so the clip duration is the narration duration. The silent hold shot absorbs
whatever is left to reach exactly 30.0 s. Narration that overruns fails the render with
the exact overage rather than shipping a long Short.

**The timeline is allocated in frames, not seconds.** A clip can only be an integer number
of frames, so per-shot rounding lost ~0.02 s each and the final landed outside tolerance.
All 720 frames are allocated up front, which is why the output is exactly 30.0 s. The
Colab manifest and the assembler both call the same `editor.allocate()` for this reason:
a job asking for a different length than the assembler expects would fail every clip.

**Portrait is generated, not cropped.** A Short is 9:16. Generating Wan2.1 landscape and
cropping would throw away two thirds of every frame, so generation is 480×832 — both
sides divisible by 16, which Wan2.1 requires.

**float16, never bfloat16.** A Colab T4 is Turing (sm_75) and has no bfloat16 support.
The VAE is additionally kept in float32, per the model card.

**Captions are authored, not machine-translated.** Every shot carries a word-for-word
parallel Devanagari line. Synthesised word timings are mapped onto it by index, so a
caption can never drift off its word. A mismatch is a hard validation failure.

**All Hindi text goes through libass.** This ffmpeg build has HarfBuzz and FriBidi, so
Devanagari conjuncts shape correctly. Pillow has no Raqm here, so Hindi text is *never*
rasterised by Pillow — a real trap that produces silently broken conjuncts.

## Characters

Recurring silhouettes, never faces. Defined in `story/dop_grammar.json` and voiced from
`story/story_bible.json`:

| Character | On screen | Voice |
|---|---|---|
| Narrator | camera POV | `hi-IN-MadhurNeural` @ +6% |
| Nana | cane silhouette | `hi-IN-MadhurNeural` @ −25%, −20 Hz |
| Maa | sari pallu silhouette | `hi-IN-SwaraNeural` @ +0% |
| Papa | never on screen | `hi-IN-MadhurNeural` @ +14%, +8 Hz |
| The Presence | doorway silhouette | `hi-IN-SwaraNeural` @ −35%, −25 Hz |

Only two Hindi voices exist on the free endpoint, so the ensemble is separated by rate
and pitch rather than by casting. Babulal never speaks — he only ever appears as a note.

## Compliance

- AI-generated content is disclosed in every description, and the "Altered or synthetic
  content" box is called out at upload (India's IT Rules require it).
- No gore, no real persons, no brands, no financial promises, no engagement bait.
- No copyrighted footage or music at all: visuals are generated, ambience is synthesised.
- Full picture in `licenses.csv`.

## Known limitations

- **Clips are generated off-machine.** Nothing runs unattended end to end: the Colab
  step is manual and 3–4 hours per episode. A one-time GPU upgrade removes this.
- **Generated clips are 480×832 upscaled to 1080×1920.** Soft at full size, though the
  grain pass hides most of it.
- **edge-tts is an unofficial client.** Free to use, but not an official commercial API.
  Piper (MIT) is declared as the clean fallback if that matters to you.
- **Word-level caption timing is interpolated** from the provider's sentence boundaries,
  because this build of edge-tts emits `SentenceBoundary`, not `WordBoundary`. Captions
  stay locked to their sentence; the karaoke highlight inside a sentence is proportional.
- **Only Episode 1 is authored.** Episodes 2–30 have beat sheets but no scripts. With
  `llm.provider=static` the scriptwriter refuses rather than inventing one, so the season
  cannot silently degrade into 30 near-identical videos.
- **Clip quality is unreviewed.** Wan at 30 steps on a 1.3B model sometimes warps hands
  or drifts. Review the contact frames before publishing.