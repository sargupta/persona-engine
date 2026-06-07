#!/usr/bin/env python3
"""
yt_transcript.py — Pull (or build) transcripts for YouTube videos, fast.

Strategy (each step is a fallback for the previous one):
  1. youtube-transcript-api  -> fastest; grabs existing manual or auto captions.
  2. yt-dlp subtitle tracks   -> catches videos the API misses (json3 caption files).
  3. Whisper ASR on the audio -> "build it if it doesn't exist": downloads audio
                                 with yt-dlp and transcribes locally. Works even
                                 when a video has NO captions at all.

Inputs:
  - one or more video URLs / IDs
  - OR a channel/handle with --channel + --limit N (pulls the N most recent uploads)

Outputs (written to --outdir, default ./transcripts):
  - <video_id>.txt   : clean, de-duplicated plain text (feed this to the persona layers)
  - <video_id>.jsonl : one JSON object per caption segment {start, dur, text}
  - _index.csv       : video_id, title, source(method), lang, n_segments, chars

Install (one line):
  pip install youtube-transcript-api yt-dlp faster-whisper

Whisper fallback also needs ffmpeg on PATH:
  macOS:  brew install ffmpeg
  Ubuntu: sudo apt-get install ffmpeg

Usage examples:
  # one video
  python yt_transcript.py https://www.youtube.com/watch?v=bMTlNeKqV4o

  # several videos, prefer Hindi then English
  python yt_transcript.py VID1 VID2 VID3 --langs hi en

  # 15 most-recent uploads from a channel/handle
  python yt_transcript.py --channel @CarryMinati --limit 15

  # force-build transcripts with Whisper even if captions exist (highest fidelity)
  python yt_transcript.py @CarryMinati --channel --limit 5 --force-whisper --whisper-model small
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# ----------------------------------------------------------------------------- helpers

VIDEO_ID_RE = re.compile(r"(?:v=|/shorts/|/live/|youtu\.be/|/embed/)([0-9A-Za-z_-]{11})")


def extract_video_id(s: str) -> str:
    """Accept a full URL or a bare 11-char ID and return the ID."""
    s = s.strip()
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", s):
        return s
    m = VIDEO_ID_RE.search(s)
    if m:
        return m.group(1)
    raise ValueError(f"Could not parse a video ID from: {s!r}")


def have(cmd: str) -> bool:
    """Is an executable available on PATH?"""
    from shutil import which
    return which(cmd) is not None


def clean_text(segments) -> str:
    """Join caption segments into readable prose, dropping exact consecutive dupes
    (auto-captions repeat lines as they scroll)."""
    out, prev = [], None
    for seg in segments:
        t = re.sub(r"\s+", " ", seg["text"]).strip()
        t = t.replace("​", "")
        if not t or t == prev:
            continue
        out.append(t)
        prev = t
    text = " ".join(out)
    # tidy spacing around sentence punctuation
    text = re.sub(r"\s+([.,!?।])", r"\1", text)
    return text.strip()


def write_outputs(outdir: Path, vid: str, segments, source: str, lang: str, title: str, index_rows):
    txt = clean_text(segments)
    (outdir / f"{vid}.txt").write_text(txt, encoding="utf-8")
    with (outdir / f"{vid}.jsonl").open("w", encoding="utf-8") as f:
        for seg in segments:
            f.write(json.dumps(seg, ensure_ascii=False) + "\n")
    index_rows.append({
        "video_id": vid, "title": title, "source": source,
        "lang": lang, "n_segments": len(segments), "chars": len(txt),
    })
    print(f"  [{source}] {vid} :: {len(segments)} segments, {len(txt)} chars -> {vid}.txt")


# ----------------------------------------------------------------------------- method 1: API

def via_api(vid: str, langs):
    """youtube-transcript-api: prefer manual captions, then auto-generated."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None, None
    try:
        listing = YouTubeTranscriptApi.list_transcripts(vid)
        # 1) manually created in a preferred language
        try:
            tr = listing.find_manually_created_transcript(langs)
        except Exception:
            # 2) auto-generated in a preferred language
            try:
                tr = listing.find_generated_transcript(langs)
            except Exception:
                # 3) anything, then translate to first preferred lang if possible
                tr = next(iter(listing))
                if langs and tr.is_translatable:
                    try:
                        tr = tr.translate(langs[0])
                    except Exception:
                        pass
        data = tr.fetch()
        segments = [{"start": round(d["start"], 2), "dur": round(d.get("duration", 0), 2),
                     "text": d["text"]} for d in data]
        kind = "api-manual" if not getattr(tr, "is_generated", True) else "api-auto"
        return segments, f"{kind}:{tr.language_code}"
    except Exception as e:
        print(f"  api miss ({type(e).__name__})", file=sys.stderr)
        return None, None


# ----------------------------------------------------------------------------- method 2: yt-dlp subs

def via_ytdlp_subs(vid: str, langs):
    """Download caption tracks with yt-dlp (json3) and parse them."""
    if not have("yt-dlp"):
        return None, None
    url = f"https://www.youtube.com/watch?v={vid}"
    sub_langs = ",".join(langs + [f"{l}-orig" for l in langs] + ["en", "hi"])
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ["yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs",
               "--sub-langs", sub_langs, "--sub-format", "json3",
               "-o", os.path.join(tmp, "%(id)s.%(ext)s"), url]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"  yt-dlp subs miss: {e.stderr.strip().splitlines()[-1:] }", file=sys.stderr)
            return None, None
        files = sorted(Path(tmp).glob(f"{vid}*.json3"))
        if not files:
            return None, None
        # pick the first file matching language priority
        chosen = files[0]
        lang_code = "unknown"
        for l in langs + ["en", "hi"]:
            cand = [f for f in files if f".{l}." in f.name]
            if cand:
                chosen, lang_code = cand[0], l
                break
        data = json.loads(chosen.read_text(encoding="utf-8"))
        segments = []
        for ev in data.get("events", []):
            if "segs" not in ev:
                continue
            text = "".join(s.get("utf8", "") for s in ev["segs"]).strip()
            if not text:
                continue
            segments.append({"start": round(ev.get("tStartMs", 0) / 1000, 2),
                             "dur": round(ev.get("dDurationMs", 0) / 1000, 2), "text": text})
        if not segments:
            return None, None
        return segments, f"yt-dlp:{lang_code}"


# ----------------------------------------------------------------------------- method 3: Whisper ASR

def via_whisper(vid: str, model_name: str):
    """Last resort / highest fidelity: download audio and transcribe locally.
    This is the 'build the transcript if it doesn't exist' path."""
    if not have("yt-dlp"):
        print("  whisper fallback needs yt-dlp", file=sys.stderr)
        return None, None
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("  whisper fallback needs: pip install faster-whisper", file=sys.stderr)
        return None, None
    url = f"https://www.youtube.com/watch?v={vid}"
    with tempfile.TemporaryDirectory() as tmp:
        audio = os.path.join(tmp, f"{vid}.mp3")
        cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "5",
               "-o", os.path.join(tmp, "%(id)s.%(ext)s"), url]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"  audio download failed: {e.stderr.strip().splitlines()[-1:]}", file=sys.stderr)
            return None, None
        if not os.path.exists(audio):
            cand = list(Path(tmp).glob(f"{vid}.*"))
            if not cand:
                return None, None
            audio = str(cand[0])
        print(f"  transcribing with faster-whisper ({model_name}) — this is the slow path...")
        wmodel = WhisperModel(model_name, device="auto", compute_type="auto")
        segs, info = wmodel.transcribe(audio, vad_filter=True)
        segments = [{"start": round(s.start, 2), "dur": round(s.end - s.start, 2),
                     "text": s.text.strip()} for s in segs]
        if not segments:
            return None, None
        return segments, f"whisper-{model_name}:{info.language}"


# ----------------------------------------------------------------------------- channel listing

def channel_video_ids(channel: str, limit: int):
    """Use yt-dlp to list the most recent uploads of a channel/handle."""
    if not have("yt-dlp"):
        sys.exit("--channel needs yt-dlp installed (pip install yt-dlp)")
    handle = channel if channel.startswith(("http", "@")) else "@" + channel
    url = handle if handle.startswith("http") else f"https://www.youtube.com/{handle}/videos"
    cmd = ["yt-dlp", "--flat-playlist", "--playlist-end", str(limit),
           "--print", "%(id)s\t%(title)s", url]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"Could not list channel: {out.stderr.strip()}")
    pairs = []
    for line in out.stdout.strip().splitlines()[:limit]:
        parts = line.split("\t", 1)
        pairs.append((parts[0], parts[1] if len(parts) > 1 else ""))
    return pairs


def title_for(vid: str):
    if not have("yt-dlp"):
        return ""
    out = subprocess.run(["yt-dlp", "--skip-download", "--print", "%(title)s",
                          f"https://www.youtube.com/watch?v={vid}"],
                         capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else ""


# ----------------------------------------------------------------------------- main

def process(vid, title, langs, outdir, force_whisper, whisper_model, index_rows):
    segments = source = lang = None
    if force_whisper:
        segments, source = via_whisper(vid, whisper_model)
    if not segments:
        segments, source = via_api(vid, langs)
    if not segments:
        segments, source = via_ytdlp_subs(vid, langs)
    if not segments and not force_whisper:
        segments, source = via_whisper(vid, whisper_model)
    if not segments:
        print(f"  !! no transcript obtained for {vid}", file=sys.stderr)
        index_rows.append({"video_id": vid, "title": title, "source": "FAILED",
                           "lang": "", "n_segments": 0, "chars": 0})
        return
    lang = source.split(":")[-1] if ":" in source else ""
    write_outputs(outdir, vid, segments, source.split(":")[0], lang, title, index_rows)


def main():
    ap = argparse.ArgumentParser(description="Pull or build YouTube transcripts.")
    ap.add_argument("targets", nargs="*", help="video URLs/IDs, or a channel handle if --channel is set")
    ap.add_argument("--channel", action="store_true", help="treat the (single) target as a channel/handle")
    ap.add_argument("--limit", type=int, default=10, help="max recent videos when using --channel")
    ap.add_argument("--langs", nargs="+", default=["hi", "en"], help="language priority (default: hi en)")
    ap.add_argument("--outdir", default="transcripts", help="output directory")
    ap.add_argument("--force-whisper", action="store_true", help="always transcribe with Whisper (ignore captions)")
    ap.add_argument("--whisper-model", default="small",
                    help="faster-whisper model: tiny/base/small/medium/large-v3 (bigger=better, slower)")
    args = ap.parse_args()

    if not args.targets:
        ap.error("give at least one video URL/ID, or a channel handle with --channel")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    index_rows = []

    if args.channel:
        if len(args.targets) != 1:
            ap.error("--channel expects exactly one channel/handle")
        videos = channel_video_ids(args.targets[0], args.limit)
        print(f"Found {len(videos)} videos for {args.targets[0]}")
    else:
        videos = [(extract_video_id(t), "") for t in args.targets]

    for i, (vid, title) in enumerate(videos, 1):
        if not title:
            title = title_for(vid)
        print(f"[{i}/{len(videos)}] {vid}  {title[:70]}")
        process(vid, title, args.langs, outdir, args.force_whisper, args.whisper_model, index_rows)

    with (outdir / "_index.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["video_id", "title", "source", "lang", "n_segments", "chars"])
        w.writeheader()
        w.writerows(index_rows)
    ok = sum(1 for r in index_rows if r["source"] != "FAILED")
    print(f"\nDone. {ok}/{len(index_rows)} transcripts written to {outdir}/  (see _index.csv)")


if __name__ == "__main__":
    main()
