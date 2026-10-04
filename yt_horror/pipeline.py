#!/usr/bin/env python
"""Orchestrator for the Sheesha Shorts pipeline.

    python pipeline.py preflight        # can this machine run it, and with what
    python pipeline.py status           # what is rendered, what is promised
    python pipeline.py episode 1        # guard -> tts -> visuals -> edit -> qc
    python pipeline.py batch 1 3        # episodes 1..3
    python pipeline.py publish 1        # print the upload metadata + disclosure
    python pipeline.py prompts 1        # compile + print the diffusion prompt set

Every step is idempotent and resumable: existing clips, voice and QC reports are
reused unless --force is passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agents import director, dop, editor, guard, preflight, prompter, scriptwriter  # noqa: E402
from lib import config  # noqa: E402

# Every string this CLI prints can contain Devanagari or an em dash. The default
# Windows console codec is cp1252, which raises UnicodeEncodeError on those, so
# `publish` used to die while printing the description.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _force_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument("--force", action="store_true", help="re-render even if output exists")


def cmd_preflight(_args) -> int:
    cfg = config.load_config()
    config.ensure_dirs()
    report = preflight.run(cfg)
    preflight.print_report(report)

    from lib.visuals import pollinations as pv

    info = pv.probe()
    print()
    print("=" * 70)
    print("VIDEO PROVIDER (pollinations)")
    print("=" * 70)
    print(f"  model       : {info['model']}")
    print(f"  key         : {'configured' if info['key_configured'] else 'MISSING'}")
    print(f"  status      : {info['detail']}")
    if not info["key_configured"]:
        print()
        print("  This is the only thing standing between you and a finished Short.")
        print("  1. sign up at https://enter.pollinations.ai")
        print("  2. copy your sk_ key")
        print("  3. set it:  set POLLINATIONS_API_KEY=sk_...")
        print("  then run:   python pipeline.py episode 1 --provider pollinations")
    print()

    if not report["ffmpeg_ok"] or not report["tts_ok"]:
        return 1
    return 0


def cmd_status(_args) -> int:
    cfg = config.load_config()
    bible, season = director.load()
    cov = director.coverage(season)
    hw = config.read_json(ROOT / "config" / "hardware.json", {}) or {}

    print(f"season   : {bible['title']} - {cov['planned']} episodes planned")
    print(f"rendered : {cov['published']}/{cov['planned']}")
    print(f"provider : {hw.get('visual_provider', 'unknown')}")
    if cov["remaining"]:
        preview = ", ".join(str(e) for e in cov["remaining"][:10])
        more = "" if len(cov["remaining"]) <= 10 else f" (+{len(cov['remaining']) - 10} more)"
        print(f"remaining: {preview}{more}")

    outs = sorted(config.OUT_DIR.glob("ep*.mp4"))
    if not outs:
        print("\nno rendered episodes yet - run:  python pipeline.py episode 1")
        return 0
    print()
    for f in outs:
        qc = config.read_json(config.QC_DIR / f"{f.stem}_qc.json", {}) or {}
        flag = "PASS" if qc.get("pass") else ("FAIL" if qc else "no qc")
        print(f"  {f.name:<12} {qc.get('actual_duration_s','?')}s  "
              f"{qc.get('resolution','?')}  {flag}  {f.stat().st_size // 1024} KB")
    return 0


def render_one(cfg: dict, ep: int, force: bool, provider: str = "auto") -> dict:
    final = config.OUT_DIR / f"ep{ep:02d}.mp4"
    if final.exists() and not force:
        print(f"ep{ep:02d} already rendered - skipping (use --force to redo)")
        return {"final": final, "qc": config.read_json(config.QC_DIR / f"ep{ep:02d}_qc.json", {})}

    bible, season = director.load()
    director.seed_ledger(bible, season)

    script = scriptwriter.load_or_write(cfg, ep, season)
    problems = scriptwriter.validate(script)
    if problems:
        raise SystemExit("script invalid:\n  - " + "\n  - ".join(problems))

    # guard runs before a single second of audio or video is produced
    guard.run(cfg, bible, season, script)

    prompts = prompter.build_promptset(script, ep, cfg)
    config.write_json(config.episode_dir(ep) / "prompts.json", prompts)
    for p in prompts:
        for w in p["warnings"]:
            config.log_line("prompter", f"ep{ep} {p['id']}: {w}")

    grammar = dop.load_grammar()
    print(f"ep{ep:02d}  {script['title']}  |  {len(script['shots'])} shots  |  "
          f"dop {dop.describe(grammar)}")
    result = editor.render_episode(cfg, ep, provider=provider, force=force)

    director.record_published(bible, season, ep)
    qc = result["qc"]
    print(f"        -> {result['final'].name}  {qc['actual_duration_s']}s  "
          f"{qc['resolution']}  {qc['size_bytes'] // 1024} KB  "
          f"{'PASS' if qc['pass'] else 'FAIL'}")
    if not qc["pass"]:
        for k, v in qc["checks"].items():
            if not v:
                print(f"        QC FAILED: {k}")
    return result


def cmd_episode(args) -> int:
    cfg = config.load_config()
    config.ensure_dirs()
    render_one(cfg, args.episode, args.force, provider=args.provider)
    return 0


def cmd_batch(args) -> int:
    cfg = config.load_config()
    config.ensure_dirs()
    for ep in range(args.first, args.last + 1):
        render_one(cfg, ep, args.force, provider=args.provider)
    return 0


def cmd_prompts(args) -> int:
    cfg = config.load_config()
    script = config.read_json(config.script_path(args.episode))
    if script is None:
        raise SystemExit(f"no script for ep{args.episode:02d}")
    for p in prompter.build_promptset(script, args.episode, cfg):
        print("=" * 68)
        print(f"{p['id']}  kind={p['kind']}  seed={p['seed']}")
        print(f"  + {p['positive']}")
        print(f"  - {p['negative']}")
        for w in p["warnings"]:
            print(f"  ! {w}")
    return 0


def cmd_video_jobs(args: argparse.Namespace) -> int:
    """Write the manifest the Colab notebook turns into clips."""
    from lib.visuals.wan import NOTEBOOK_REL, build_jobs, manifest_path, wan_dir

    cfg = config.load_config()
    ep = args.episode
    bible, season = director.load()
    director.seed_ledger(bible, season)
    script = scriptwriter.load_or_write(cfg, ep, season)
    problems = scriptwriter.validate(script)
    if problems:
        raise SystemExit("script invalid:\n  - " + "\n  - ".join(problems))
    guard.run(cfg, bible, season, script)

    shots, _tts, voice_total = editor.allocate(cfg, script, ep, config.episode_dir(ep))
    promptset = {p["id"]: p for p in prompter.build_promptset(script, ep, cfg)}
    manifest = build_jobs(cfg, ep, shots, promptset)

    if getattr(args, "test", False):
        # One clip, on purpose. A free Colab T4 takes ~30 min per clip, so the cheapest
        # way to find out whether the art direction works before paying for a whole
        # episode is to render the single most revealing shot and look at it.
        pick = max(shots, key=lambda s: (bool(s.get("character_visual")),
                                         s.get("kind") == "doorway_figure",
                                         s["frames"]))
        manifest["jobs"] = [j for j in manifest["jobs"] if j["id"] == pick["id"]]
        manifest["notes"].append(
            "TEST MANIFEST: one shot only, to validate the look before committing "
            "to a full episode.")
        pick = manifest["jobs"][0]
        print(f"TEST manifest: 1 clip only -> {pick['id']} ({pick['kind']})")
        print("  This is the free rehearsal. ~30 min on a free Colab T4.")
        print()

    path = manifest_path(ep)
    config.write_json(path, manifest)

    print(f"ep{ep:02d}  {script['title']}")
    print(f"  narration {round(voice_total, 2)}s  ->  {len(shots)} clips")
    print(f"  manifest  {path}")
    print()
    total = 0.0
    for j in manifest["jobs"]:
        n = float(j["want_duration"])
        total += n
        print(f"  {j['id']:<4} {j['kind']:<15} {n:>5.2f}s  seed={j['seed']}  {j['out_name']}")
    print(f"\n  {total:.1f}s of clip, roughly {len(manifest['jobs']) * 30} min of T4 time")
    if len(manifest["jobs"]) < len(shots):
        print(f"\n  Only {len(manifest['jobs'])} of {len(shots)} shots. This is a test:")
        print(f"  preview it with `python pipeline.py preview {ep}`, then run")
        print(f"  `python pipeline.py video-jobs {ep}` for the full manifest.")
    print("\nNext:")
    if len(manifest["jobs"]) < len(shots):
        print(f"  1. upload {path.name} to Google Drive at MyDrive/sheesha/")
        print(f"  2. open {NOTEBOOK_REL}, Runtime > T4 GPU, run all cells")
        print(f"  3. download clips.zip, unzip over {wan_dir()}")
        print(f"  4. python pipeline.py preview {ep}")
    else:
        print(f"  1. upload {path.name} to Google Drive at MyDrive/sheesha/")
        print(f"  2. open {NOTEBOOK_REL}, Runtime > Change runtime type > T4 GPU, run all cells")
        print(f"  3. download MyDrive/sheesha/clips.zip, unzip over {wan_dir()}")
        print(f"  4. python pipeline.py episode {ep} --provider wan")
    return 0


def cmd_preview(args) -> int:
    """Fit and play whatever clips have come back, without assembling an episode.

    A test manifest renders one shot. This makes that one clip watchable straight
    away, so a look can be judged before committing money or another three hours to
    the remaining shots.
    """
    import os

    from lib.visuals.fit import fit
    from lib.visuals.wan import manifest_path, missing, wan_path
    from lib.visuals.wan import settings as wan_settings

    cfg = config.load_config()
    ep = args.episode
    m = config.read_json(manifest_path(ep))
    if not m:
        raise SystemExit(f"no manifest at {manifest_path(ep)}")
    gaps = missing(cfg, ep, m)
    d = wan_path()
    have = [j for j in m["jobs"] if (d / j["out_name"]).exists()]
    if not have:
        print(f"no clips yet in {d}")
        return 1

    print(f"ep{ep:02d}: {len(have)}/{len(m['jobs'])} clips available")
    if gaps:
        print(f"  still waiting on: {', '.join(gaps)}")
    for job in have:
        src = d / job["out_name"]
        frames = int(job.get("want_frames") or round(float(job["want_duration"]) * 24))
        out = d / f"preview_{job['id']}.mp4"
        fit(src, out, frames, cfg, int(wan_settings(cfg).get("grain", 6)))
        print(f"  {job['id']} {job['kind']:<16} -> {out.name}  {ffmpeg_probe(out)}")
        if not getattr(args, "no_open", False):
            os.startfile(str(out))
    print("\nJudge the look, then decide: free Colab route or paid API route.")
    return 0


def ffmpeg_probe(path):
    from lib import ffmpeg as _ff

    st = _ff.probe(path)["streams"][0]
    return (f"{st['width']}x{st['height']} "
            f"{round(float(st['r_frame_rate'].split('/')[0]))}fps "
            f"{round(float(st.get('nb_frames', 0)))}f")


def cmd_publish(args) -> int:
    cfg = config.load_config()
    bible, season = director.load()
    ep = args.episode
    script = config.read_json(config.script_path(ep))
    final = config.OUT_DIR / f"ep{ep:02d}.mp4"
    if script is None or not final.exists():
        raise SystemExit(f"ep{ep:02d} is not ready to publish")
    beat = next((e for e in season["episodes"] if e["ep"] == ep), {})

    title = f"{beat.get('title', script['title'])} | Sheesha Ep {ep}"
    description = "\n".join([
        f"Ep {ep} of {bible['season_length']} - {bible['tagline']}",
        "",
        beat.get("beat", ""),
        "",
        f"Next: Ep {ep + 1} - {next((e['title'] for e in season['episodes'] if e['ep'] == ep + 1), '...')}",
        "",
        bible["disclosure_line"],
        "Footage, voice and captions generated with AI. Fiction only.",
        "",
        "#shorts #hindi #horror #india",
    ])
    print("=" * 68)
    print("UPLOAD METADATA - copy into YouTube Studio")
    print("=" * 68)
    print(f"file        : {final}")
    print(f"title       : {title}")
    print(f"title chars : {len(title)}  (Shorts truncate around 100)")
    print("\ndescription :")
    print(description)
    print("\n-- tick 'Altered or synthetic content' in the upload dialog (India's IT")
    print("   Rules require AI-generated content to be disclosed).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("preflight"); p.set_defaults(fn=cmd_preflight)

    p = sub.add_parser("status"); p.set_defaults(fn=cmd_status)

    p = sub.add_parser("episode"); p.add_argument("episode", type=int)
    p.add_argument("--provider", default="auto", choices=["auto", "pollinations", "wan", "motion", "diffusion"])
    _force_flag(p); p.set_defaults(fn=cmd_episode)

    p = sub.add_parser("batch"); p.add_argument("first", type=int); p.add_argument("last", type=int)
    p.add_argument("--provider", default="auto", choices=["auto", "pollinations", "wan", "motion", "diffusion"])
    _force_flag(p); p.set_defaults(fn=cmd_batch)

    p = sub.add_parser("prompts"); p.add_argument("episode", type=int)
    p.set_defaults(fn=cmd_prompts)

    p = sub.add_parser("preview"); p.add_argument("episode", type=int)
    p.add_argument("--no-open", action="store_true")
    p.set_defaults(fn=cmd_preview)

    p = sub.add_parser("publish"); p.add_argument("episode", type=int)
    p.set_defaults(fn=cmd_publish)

    p = sub.add_parser("video-jobs"); p.add_argument("episode", type=int)
    p.add_argument("--test", action="store_true",
                   help="emit a single-clip manifest, to validate the look for free")
    p.set_defaults(fn=cmd_video_jobs)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except guard.Veto as exc:
        print("\nGUARD VETO - nothing was rendered.\n  - " + "\n  - ".join(exc.reasons))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())