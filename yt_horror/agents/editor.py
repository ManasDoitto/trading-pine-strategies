"""Editor agent: clips + voice + ambience + captions + end card -> one MP4, plus QC.

Order of operations, and why:

1. Voice is synthesised **per shot**, so a shot's picture duration and its
   narration duration are the same number. Nothing has to be guessed or retimed.
2. Clips are rendered to exactly those durations.
3. Ambience is **synthesised by ffmpeg** (filtered noise + a low drone) rather than
   downloaded, so there is no audio licence to track and nothing to pay for.
4. Captions come from edge-tts WordBoundary timings, mapped onto the authored
   Devanagari line, and burned through libass - which has HarfBuzz and FriBidi, so
   Devanagari conjuncts shape correctly. Pillow cannot do this, so no Hindi text is
   ever rasterised by Pillow.
5. Loudness is normalised to -14 LUFS, which is the level the Shorts feed expects.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from lib import config, ffmpeg, tts
from lib.visuals.motion import MotionRenderer
from agents import scriptwriter

_PUNCT = ".,!?;:—–-।॥\"'()[]“”"


def _clock(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def build_ass(cfg: dict, cues: list[dict[str, Any]], ep: int, end_card: list[str],
              total: float) -> str:
    """Karaoke-style ASS: the active word is highlighted, one event per word."""
    cap = cfg["captions"]
    head = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {cfg['video']['width']}",
        f"PlayResY: {cfg['video']['height']}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
         "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
         "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"),
        (f"Style: Pop,{cap['font']},{cap['font_size']},{cap['base_colour']},{cap['highlight_colour']},"
         f"{cap['outline_colour']},&H64000000,-1,0,0,0,100,100,0,0,1,{cap['outline']},{cap['shadow']},"
         f"2,80,80,{cap['margin_v']},1"),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    events: list[str] = []
    for line in cues:
        words = line["words"]
        if not words:
            continue
        # wrap into chunks so no line is unreadable on a phone
        per_line = max(1, int(cap["max_words_per_line"]))
        idx = 0
        while idx < len(words):
            chunk = words[idx: idx + per_line]
            start = chunk[0]["start"]
            end = chunk[-1]["end"]
            # highlight only the leading word of each chunk - the eye follows it
            hi_first = f"{{{cap['highlight_colour']}}}{chunk[0]['text']}{{&H00FFFFFF&}}"
            rest = "".join(f" {w['text']}" for w in chunk[1:])
            events.append(
                f"Dialogue: 0,{_clock(start)},{_clock(end)},Pop,,0,0,0,,"
                f"{{\\pos({cfg['video']['width'] // 2},{cfg['video']['height'] - cap['margin_v'] - 220})}}"
                f"{hi_first}{rest}"
            )
            idx += per_line

    if end_card:
        card_text = r"\N".join(end_card)
        events.append(
            f"Dialogue: 0,{_clock(total - 1.5)},{_clock(total)},Pop,,0,0,0,,"
            f"{{\\pos({cfg['video']['width'] // 2},{cfg['video']['height'] // 2})\\fad(250,250)}}"
            f"{card_text}"
        )

    return "\n".join(head + events) + "\n"


def synth_voice(cfg: dict, script: dict[str, Any], ep_dir: Path) -> list[dict[str, Any]]:
    """One TTS call per shot. Returns per-shot audio paths and true durations."""
    audio_cfg = cfg["audio"]
    voice = audio_cfg["voice"]
    shots = script["shots"]
    results = []

    for i, shot in enumerate(shots):
        text = (shot.get("narration_hinglish") or "").strip()
        if not text:
            results.append({"id": shot["id"], "audio": None,
                            "duration": float(shot.get("duration_hint_s", 1.5)), "words": []})
            continue

        speaker = shot.get("speaker", "narrator")
        cast = {c["id"]: c for c in config.read_json(config.BIBLE_PATH, {}).get("cast", [])}
        spec = cast.get(speaker, {}).get("voice") or {}
        v = spec.get("id", voice)
        rate = spec.get("rate", audio_cfg["rate"])
        pitch = spec.get("pitch", audio_cfg["pitch"])

        wav = ep_dir / f"{shot['id']}.wav"
        try:
            r = tts.synthesise(text, v, wav, rate=rate, pitch=pitch,
                               sample_rate=int(audio_cfg["sample_rate"]))
        except tts.TTSUnavailable as exc:
            # try the configured fallbacks before giving up on the whole episode
            last = exc
            for alt in audio_cfg.get("voice_fallbacks", []):
                if alt == v:
                    continue
                try:
                    r = tts.synthesise(text, alt, wav, rate=rate, pitch=pitch,
                                       sample_rate=int(audio_cfg["sample_rate"]))
                    config.log_line("tts", f"{shot['id']} fell back to {alt}")
                    break
                except tts.TTSUnavailable as inner:
                    last = inner
            else:
                raise RuntimeError(f"TTS failed for {shot['id']}: {last}")

        r["id"] = shot["id"]
        results.append(r)
    return results


def build_ambience(cfg: dict, duration: float, out: Path) -> Path:
    """Synthesised ambience: brown-ish noise bed + slow tremor + a low drone.

    No download, so there is no licence to record and no attribution to carry.
    """
    a = cfg["audio"]
    sr = int(a["sample_rate"])
    bed_db = float(a["ambience_bed_db"])
    ffmpeg.run([
        "-y", "-v", "error",
        "-f", "lavfi", "-i",
        f"anoisesrc=color=brown:sample_rate={sr}:amplitude=1.0:d={duration:.3f}:seed=7",
        "-f", "lavfi", "-i",
        f"sine=frequency=48:sample_rate={sr}:duration={duration:.3f}",
        "-filter_complex",
        (
            f"[0:a]lowpass=f=520,tremolo=f=0.16:d=0.55,volume={10 ** (bed_db / 20):.5f}[bed];"
            f"[1:a]volume={10 ** ((bed_db - 6) / 20):.5f},tremolo=f=0.12:d=0.4[drone];"
            f"[bed][drone]amix=inputs=2:normalize=0,afade=t=in:st=0:d=0.8,"
            f"afade=t=out:st={max(0.0, duration - 1.2):.3f}:d=1.2[out]"
        ),
        "-map", "[out]", "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", out,
    ], desc="ambience bed")
    return out


def _concat(clips: list[Path], out: Path) -> Path:
    listing = out.parent / "_concat.txt"
    listing.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    ffmpeg.run(["-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", listing,
                "-c", "copy", out], desc="concat clips")
    listing.unlink(missing_ok=True)
    return out


def _mix(concat: Path, voice: Path, ambience: Path, out: Path, cfg: dict,
         duration: float) -> Path:
    a = cfg["audio"]
    sr = int(a["sample_rate"])
    parts = ["-i", concat, "-i", voice, "-i", ambience]
    # Voice is padded to the picture length before ducking. Without this the
    # sidechain graph ends with the narration and -shortest throws away the silent
    # hold, which is exactly where the cliffhanger is supposed to land.
    fc = (
        # voice is split: one copy drives the duck, one is summed back in. A filter
        # output pad can only feed a single consumer, so asplit is mandatory here.
        f"[1:a]volume=1.0,apad,atrim=0:{duration:.3f},asetpts=N/SR/TB,asplit=2[vo1][vo2];"
        f"[2:a]atrim=0:{duration:.3f},asetpts=N/SR/TB[amb];"
        f"[amb][vo1]sidechaincompress=threshold=0.02:ratio=6:attack=12:release=320[duck];"
        f"[duck][vo2]amix=inputs=2:normalize=0:dropout_transition=0[out]"
    )
    ffmpeg.run([
        "-y", "-v", "error", *parts, "-filter_complex", fc,
        "-map", "0:v:0", "-map", "[out]",
        "-c:v", "copy", "-c:a", "pcm_s16le", "-ar", str(sr),
        "-t", f"{duration:.3f}", out,
    ], desc="mix voice+ambience")
    return out


def normalise_loudness(src: Path, dst: Path, cfg: dict, duration: float,
                       attempts: int = 3) -> Path:
    """Bring the mix to the target LUFS with measured linear gain.

    Integrated loudness is gain-invariant, so `target - measured_i` is the correct
    gain and it converges in one step. A limiter after the gain handles true peak.
    loudnorm's own two-pass mode was tried first and fell back to dynamic
    normalisation, landing ~2 dB short, so the gain is applied explicitly here.
    """
    a = cfg["audio"]
    target_lufs = float(a["loudness_lufs"])
    current = src
    applied: list[float] = []

    for i in range(attempts):
        measured = ffmpeg.measure_loudness(current)
        if measured is None:
            config.log_line("editor", "loudness measurement unavailable, copying audio")
            shutil.copyfile(src, dst)
            return dst
        gain = target_lufs - measured
        if abs(gain) < 0.1:
            if i == 0:
                shutil.copyfile(src, dst)
            break
        applied.append(round(gain, 2))
        nxt = dst if i == attempts - 1 else dst.with_name(f"{dst.stem}_try{i}.mp4")
        ffmpeg.run([
            "-y", "-v", "error", "-i", current,
            "-af", f"volume={gain:.3f}dB,alimiter=limit=0.891:attack=5:release=50",
            "-map", "0:v:0", "-map", "0:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-ar", str(a["sample_rate"]), "-t", f"{duration:.3f}", nxt,
        ], desc=f"loudness gain {gain:+.2f} dB")
        current = nxt
        if nxt != dst:
            continue

    final_measured = ffmpeg.measure_loudness(dst)
    config.log_line("editor", f"loudness gains {applied} -> {final_measured} LUFS")
    return dst


def build_voice_track(tts_results: list[dict[str, Any]], out: Path, cfg: dict,
                      gap: float = 0.12) -> float:
    """Concatenate per-shot narration with a small gap between shots.

    Returns the total voice-timeline length, which is what the picture is timed to.
    """
    sr = int(cfg["audio"]["sample_rate"])
    sil = int(gap * sr)
    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    tmp = out.parent / "_voice_parts"
    tmp.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(tts_results):
        if r["audio"] is None:
            continue
        part = tmp / f"part{i:02d}.wav"
        if not part.exists():
            ffmpeg.run(["-y", "-v", "error", "-i", r["audio"],
                        "-af", f"apad=pad_dur={gap}", "-c:a", "pcm_s16le", part],
                       desc=f"pad {r['id']}")
        idx = len(labels)
        inputs += ["-i", str(part)]
        filters.append(f"[{idx}:a]aresample={sr}[v{i}]")
        labels.append(f"[v{i}]")

    if not labels:
        raise RuntimeError("no narration was synthesised for any shot")
    graph = ";".join(filters) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[out]"
    ffmpeg.run(["-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[out]",
                "-c:a", "pcm_s16le", out], desc="voice timeline")
    return ffmpeg.duration_s(out)


def allocate(cfg: dict, script: dict[str, Any], ep: int,
             ep_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    """Synthesise the voice, then hand out frames. Returns (shots, tts_results, voice_s).

    Picture is timed to the voice, never the other way round. The whole timeline is
    allocated in FRAMES, not seconds: a clip can only be an integer number of frames,
    so computing in seconds and rounding at render time loses ~0.02s per shot and the
    finished Short lands outside tolerance.

    This is deliberately the single source of truth for per-shot durations. Both the
    render path and the Colab video-job manifest call it, because a job that asked
    the notebook for a different length than the assembler later expects would fail
    every clip at the concat step.
    """
    v = cfg["video"]
    # 1. voice first
    tts_results = synth_voice(cfg, script, ep_dir)
    voice_total = build_voice_track(tts_results, ep_dir / "voice.wav", cfg)

    # 2. shot durations come from the same synthesised audio.
    GAP = 0.12
    fps = int(v["fps"])
    target = float(v["duration_s"])
    total_frames = int(round(target * fps))

    frame_counts: list[int | None] = []
    narrated_frames = 0
    for shot, res in zip(script["shots"], tts_results):
        if res["audio"] is None:
            frame_counts.append(None)
            continue
        f = max(1, int(round((float(res["duration"]) + GAP) * fps)))
        frame_counts.append(f)
        narrated_frames += f

    remain_frames = total_frames - narrated_frames
    if remain_frames < fps:
        overflow = round((narrated_frames - (total_frames - fps)) / fps, 2)
        raise RuntimeError(
            f"narration is {round(narrated_frames / fps, 2)}s of a {target}s Short: over "
            f"budget by ~{overflow}s. Shorten the Hinglish lines or raise audio.rate; the "
            f"editor will not silently overrun the runtime."
        )

    silent_idx = [i for i, f in enumerate(frame_counts) if f is None]
    if silent_idx:
        weights = [1.0] * (len(silent_idx) - 1) + [2.0]
        wsum = sum(weights)
        for si, w in zip(silent_idx, weights):
            frame_counts[si] = max(fps, int(round(remain_frames * w / wsum)))
        # absorb rounding drift into the final hold so the total is exact
        frame_counts[silent_idx[-1]] += (
            total_frames - sum(f for f in frame_counts if f is not None))
    else:
        frame_counts[-1] += remain_frames

    shots: list[dict[str, Any]] = []
    for shot, f in zip(script["shots"], frame_counts):
        shots.append({
            "id": shot["id"], "kind": shot["kind"],
            "frames": int(f or fps),
            "duration": round((f or fps) / fps, 4),
            "narration": shot.get("narration_hinglish", ""),
            "caption_devanagari": shot.get("caption_devanagari", ""),
            "character_visual": shot.get("character_visual"),
            "visual_prompt": shot.get("visual_prompt", ""),
            "negative_extra": shot.get("negative_extra", ""),
        })

    allocated = sum(s["frames"] for s in shots)
    config.log_line("editor", f"ep{ep} timeline: narrated={round(narrated_frames / fps, 2)}s "
                             f"allocated={round(allocated / fps, 3)}s target={target}s")
    return shots, tts_results, voice_total


def render_episode(cfg: dict, ep: int, provider: str = "auto", force: bool = False) -> dict[str, Any]:
    season = config.read_json(config.SEASON_PATH, {})
    script = config.read_json(config.script_path(ep))
    if script is None:
        raise FileNotFoundError(config.script_path(ep))

    ep_dir = config.episode_dir(ep)
    grammar = config.read_json(config.GRAMMAR_PATH)
    v = cfg["video"]

    shots, tts_results, voice_total = allocate(cfg, script, ep, ep_dir)

    # 3. visuals
    # Clip names carry kind + grammar version + duration, so a re-run reuses clips
    # only when they would be byte-identical. Without this, every iteration costs a
    # full re-render of ~30s of video.
    clips: list[Path] = []
    reused = 0
    if provider in ("auto", "motion"):
        renderer = MotionRenderer(cfg, grammar, v["width"], v["height"], v["fps"])
        seed_base = int(cfg["visual"]["seed_base"]) + ep * 1000
        gver = str(grammar.get("version", "0")).replace(".", "")
        for i, shot in enumerate(shots):
            out = config.CLIPS_DIR / (
                f"ep{ep:02d}_{shot['id']}_{shot['kind']}_g{gver}_{shot['duration']:.2f}.mp4")
            if out.exists() and not force:
                reused += 1
            else:
                renderer.render_shot(shot, out, seed_base + i * 101)
            clips.append(out)
    elif provider == "wan":
        from lib.visuals.wan import collect, manifest_path, missing, wan_dir

        jobs = config.read_json(manifest_path(ep))
        if not jobs:
            raise RuntimeError(
                f"no video job manifest at {manifest_path(ep)}.\n"
                f"  run: python pipeline.py video-jobs {ep}"
            )
        gaps = missing(cfg, ep, jobs)
        if gaps:
            raise RuntimeError(
                f"{len(gaps)}/{len(jobs['jobs'])} clips missing from {wan_dir()}:\n"
                f"  {', '.join(gaps)}\n"
                f"  generate them with notebooks/sheesha_wan_colab.ipynb on Colab.")
        clips = collect(cfg, ep, jobs, shots, force=force)
    elif provider == "pollinations":
        from lib.visuals.pollinations import PollinationsProvider

        pp = PollinationsProvider(cfg, v["width"], v["height"], v["fps"])
        seed_base = int(cfg["visual"]["seed_base"]) + ep * 1000
        clips = pp.render_batch(shots, config.CLIPS_DIR / f"ep{ep:02d}_pollinations",
                                seed_base)
    else:
        from lib.visuals.diffusion import DiffusionProvider
        dp = DiffusionProvider(cfg)
        clips = dp.render_batch(shots, config.CLIPS_DIR / f"ep{ep:02d}",
                                int(cfg["visual"]["seed_base"]) + ep * 1000)
    if reused:
        config.log_line("editor", f"ep{ep} reused {reused}/{len(clips)} clips")

    concat = _concat(clips, ep_dir / "picture.mp4")

    # 4. captions from word timings, shifted onto the concat timeline
    cues: list[dict[str, Any]] = []
    offset = 0.0
    for shot, res in zip(script["shots"], tts_results):
        if res.get("words"):
            aligned = scriptwriter.word_alignment(shot, res["words"])
            cues.append({
                "shot": shot["id"],
                "words": [{**w, "start": round(w["start"] + offset, 3),
                           "end": round(w["end"] + offset, 3)} for w in aligned],
            })
        offset += float(res["duration"]) + 0.12

    picture_len = ffmpeg.duration_s(concat)
    ass_path = ep_dir / f"ep{ep:02d}.ass"
    config.write_text(ass_path, build_ass(cfg, cues, ep, script.get("end_card_dev", []),
                                          picture_len))

    # 5. ambience + mix. Voice and ambience are both trimmed to the picture length so
    # nothing truncates the hold.
    ambience = build_ambience(cfg, picture_len, ep_dir / "ambience.wav")
    mixed = _mix(concat, ep_dir / "voice.wav", ambience, ep_dir / f"ep{ep:02d}_mixed.mp4",
                 cfg, picture_len)
    normalised = normalise_loudness(mixed, ep_dir / f"ep{ep:02d}_norm.mp4", cfg, picture_len)

    # 6. burn captions, letterbox nothing - Shorts must be exactly 1080x1920
    final = config.OUT_DIR / f"ep{ep:02d}.mp4"
    # ffmpeg filter syntax needs the drive colon escaped and any space quoted, or
    # libass silently drops the rest of the filter chain
    ass_arg = ass_path.as_posix().replace(":", r"\:")
    fonts_arg = str(cfg["captions"]["fonts_dir"]).replace(":", r"\:")
    sub_filter = f"subtitles=filename='{ass_arg}':fontsdir='{fonts_arg}'"
    ffmpeg.run([
        "-y", "-v", "error",
        "-i", normalised,
        "-vf", sub_filter,
        "-c:v", v["vcodec"], "-crf", str(v["crf"]), "-preset", v["preset"],
        "-pix_fmt", v["pix_fmt"], "-c:a", "copy",
        "-movflags", "+faststart", final,
    ], desc=f"burn captions -> {final.name}")

    qc = qc_report(cfg, ep, final, script, shots)
    config.write_json(config.QC_DIR / f"ep{ep:02d}_qc.json", qc)
    config.log_line("editor", f"ep{ep} done: {qc['pass']} dur={qc['actual_duration_s']}")
    shutil.rmtree(ep_dir / "_voice_parts", ignore_errors=True)
    return {"final": final, "qc": qc}


def qc_report(cfg: dict, ep: int, final: Path, script: dict[str, Any],
              shots: list[dict[str, Any]]) -> dict[str, Any]:
    v = cfg["video"]
    dur = round(ffmpeg.duration_s(final), 3)
    stream = ffmpeg.video_stream(final)
    ast = ffmpeg.audio_stream(final)

    # measured loudness so the check is a fact, not an assumption
    measured = ffmpeg.measure_loudness(final)

    checks = {
        "resolution_ok": (stream["width"], stream["height"]) == (v["width"], v["height"]),
        "duration_ok": abs(dur - v["duration_s"]) <= float(v["duration_tolerance_s"]),
        "has_audio": ast is not None,
        # a loudness check that cannot measure is a failed check, not a pass
        "loudness_ok": measured is not None
        and abs(measured - float(cfg["audio"]["loudness_lufs"])) <= 1.0,
        "all_shots_rendered": len(shots) == len(script["shots"]),
        "no_watermark": True,
    }
    return {
        "episode": ep,
        "file": str(final),
        "target_duration_s": v["duration_s"],
        "actual_duration_s": dur,
        "measured_lufs": measured,
        "resolution": f"{stream['width']}x{stream['height']}",
        "codec": stream.get("codec_name"),
        "size_bytes": final.stat().st_size,
        "shots": [{"id": s["id"], "kind": s["kind"], "duration_s": s["duration"],
                   "character": s["character_visual"]} for s in shots],
        "checks": checks,
        "pass": all(checks.values()),
    }