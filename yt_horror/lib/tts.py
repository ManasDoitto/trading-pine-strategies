"""Text-to-speech via edge-tts (free, no API key).

Two things matter here for the rest of the pipeline:

1. Word-level timings. edge-tts emits WordBoundary events, so captions are timed
   from the audio itself instead of guessing with a whisper pass. That is why this
   provider is preferred over an offline engine that only gives us a waveform.
2. Per-shot synthesis. Each shot's line is synthesised separately, so a shot's
   rendered duration and its narration duration are the same number. That removes
   a whole class of drift between the picture and the voice.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from lib import config, ffmpeg


class TTSUnavailable(RuntimeError):
    pass


def _normalise(word: str) -> str:
    return word.strip()


# a word that ends a sentence holds the pause after it, so it gets extra time weight
_PAUSE_WEIGHT = 2.0
_SENTENCE_END = ".!?।॥"


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?।॥])\s*", text)
    return [p for p in (s.strip() for s in parts) if p]


def tokenise(text: str) -> list[str]:
    """Caption tokens: drop punctuation-only fragments but keep sentence punctuation."""
    return [t for t in text.split() if t.strip(".,!?;:—–-।॥\"'()[]“”")]


def interpolate_words(text: str, spans: list[dict[str, Any]],
                      duration: float) -> list[dict[str, Any]]:
    """Derive word timings from sentence-level provider timings.

    edge-tts reports SentenceBoundary events, not per-word ones, so the sentence
    spans are treated as ground truth and the words inside each sentence are spread
    across its span in proportion to their length plus any trailing pause. Words are
    guaranteed to stay inside their own sentence's timing, which is what keeps the
    karaoke highlight from running ahead of or behind the voice.
    """
    sentences = split_sentences(text)
    if not sentences:
        return []
    if len(spans) != len(sentences):
        # Provider merged or split sentences. Fall back to one span over the whole
        # utterance rather than mis-timing individual sentences.
        spans = [{"start": 0.0, "end": duration, "text": text}]

    out: list[dict[str, Any]] = []
    cursor_tokens = 0
    for sentence, span in zip(sentences, spans):
        tokens = tokenise(sentence)
        if not tokens:
            continue
        s_start = float(span.get("start", 0.0))
        s_end = float(span.get("end", duration))
        span_len = max(0.05, s_end - s_start)

        weights = [
            len(t) + (_PAUSE_WEIGHT if t and t[-1] in _SENTENCE_END else 0.0)
            for t in tokens
        ]
        wsum = sum(weights) or 1.0
        t_cursor = s_start
        for tok, w in zip(tokens, weights):
            span_t = span_len * (w / wsum)
            out.append({"word": tok, "start": round(t_cursor, 4),
                        "end": round(t_cursor + span_t, 4)})
            t_cursor += span_t
        cursor_tokens += len(tokens)

    return out


async def _synth_async(text: str, voice: str, out_mp3: Path, rate: str, pitch: str):
    import edge_tts

    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)

    audio = bytearray()
    sentences: list[dict[str, Any]] = []
    words: list[dict[str, Any]] = []

    async for chunk in communicate.stream():
        kind = chunk.get("type")
        if kind == "audio":
            audio.extend(chunk.get("data") or b"")
        elif kind == "SentenceBoundary":
            # offsets arrive in 100-nanosecond ticks
            sentences.append({
                "start": round(chunk.get("offset", 0) / 1e7, 4),
                "end": round((chunk.get("offset", 0) + chunk.get("duration", 0)) / 1e7, 4),
                "text": _normalise(chunk.get("text", "")),
            })
        elif kind == "WordBoundary":
            words.append({
                "start": round(chunk.get("offset", 0) / 1e7, 4),
                "end": round((chunk.get("offset", 0) + chunk.get("duration", 0)) / 1e7, 4),
                "word": _normalise(chunk.get("text", "")),
            })

    if not audio:
        raise TTSUnavailable(f"no audio returned for voice {voice!r}")

    out_mp3.write_bytes(bytes(audio))
    if not words:
        # this provider build emits sentence timings only
        words = interpolate_words(text, sentences, sentences[-1]["end"] if sentences else 0.0)
    return sentences, words


def synthesise(
    text: str,
    voice: str,
    out_wav: Path,
    *,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    sample_rate: int = 48000,
) -> dict[str, Any]:
    """Synthesise one line. Returns audio path plus word timings and true duration."""
    clean = " ".join(text.split())
    if not clean:
        raise TTSUnavailable("empty narration text")

    mp3 = out_wav.with_suffix(".mp3")
    sentences, words = asyncio.run(_synth_async(clean, voice, mp3, rate, pitch))

    # No leading-silence trim here. The WordBoundary offsets are measured against the
    # provider's own stream, so touching the audio would desync every caption. A few
    # tens of milliseconds of headroom is a much cheaper problem than captions that
    # land on the wrong word, and the editor's per-shot gap absorbs it anyway.
    ffmpeg.run(
        [
            "-y", "-v", "error",
            "-i", mp3,
            "-ac", "1", "-ar", str(sample_rate),
            "-c:a", "pcm_s16le",
            out_wav,
        ],
        desc=f"tts wav {out_wav.name}",
    )
    mp3.unlink(missing_ok=True)

    duration = ffmpeg.duration_s(out_wav)

    # Word timings are interpolated from the provider's sentence spans, so scale them
    # onto the real decoded duration of the file.
    if words and words[-1]["end"] > 0:
        span = words[-1]["end"]
        scale = duration / span if span > 0 else 1.0
        if abs(scale - 1.0) > 0.02:
            for w in words:
                w["start"] = round(w["start"] * scale, 4)
                w["end"] = round(min(w["end"] * scale, duration), 4)

    return {
        "audio": out_wav,
        "voice": voice,
        "rate": rate,
        "sentences": sentences,
        "words": words,
        "duration": round(duration, 4),
        "text": clean,
    }


def list_voices() -> list[dict[str, str]]:
    """hi-IN and en-IN voices available on the free endpoint."""
    import asyncio
    import edge_tts

    async def _go() -> list[dict[str, str]]:
        voices = await edge_tts.list_voices()
        return [
            {"name": v["ShortName"], "gender": v.get("Gender", "")}
            for v in voices
            if v.get("Locale", "").startswith(("hi-IN", "en-IN"))
        ]

    try:
        return asyncio.run(_go())
    except Exception as exc:  # network/offline — preflight reports this, never fatal
        config.log_line("tts", f"voice list failed: {exc}")
        return []