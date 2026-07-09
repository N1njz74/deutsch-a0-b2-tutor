import argparse
import asyncio
import html
import json
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import edge_tts
except Exception as e:
    print("ERROR: edge_tts is not installed or cannot be imported:", e)
    sys.exit(2)


GERMAN_REPL = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",
})

CYR = re.compile(r"[А-Яа-яЁё]")

def slugify(text: str) -> str:
    text = html.unescape(str(text or ""))
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.translate(GERMAN_REPL).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:160]

def looks_german_text(s: str) -> bool:
    if not s or CYR.search(s):
        return False
    if not re.search(r"[A-Za-zÄÖÜäöüß]", s):
        return False
    if len(s.strip()) < 2:
        return False
    return True

def score_text(s: str) -> int:
    score = 0
    if re.search(r"[ÄÖÜäöüß]", s):
        score += 20
    if "." in s or "?" in s or "!" in s:
        score += 5
    if 3 <= len(s) <= 180:
        score += 5
    if "/" in s:
        score -= 5
    if len(s) > 180:
        score -= 10
    return score

def collect_texts(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k).lower()
            if isinstance(v, str):
                if lk in {"de", "text", "title"} and looks_german_text(v):
                    out.append(v.strip())
                elif lk in {"example"} and looks_german_text(v) and len(v) <= 180:
                    out.append(v.strip())
            else:
                collect_texts(v, out)
    elif isinstance(obj, list):
        for x in obj:
            if isinstance(x, str) and looks_german_text(x) and len(x) <= 180:
                out.append(x.strip())
            else:
                collect_texts(x, out)

def load_app_data(index_path: Path):
    text = index_path.read_text(encoding="utf-8")
    m = re.search(r'<script[^>]+id=["\']app-data["\'][^>]*>(.*?)</script>', text, re.S)
    if not m:
        raise RuntimeError("app-data JSON not found in index.html")
    raw = html.unescape(m.group(1))
    return json.loads(raw)

def build_source_map(root: Path, manifest_files):
    data = load_app_data(root / "index.html")
    candidates = []
    collect_texts(data, candidates)

    # Extra safe phrases for test/settings
    candidates.extend([
        "Guten Tag. Ich lerne Deutsch.",
        "Ich lerne Deutsch.",
        "Können Sie das bitte wiederholen?",
        "Ich möchte einen Termin vereinbaren.",
    ])

    by_slug = {}
    for t in candidates:
        s = slugify(t)
        if not s:
            continue
        old = by_slug.get(s)
        if old is None or score_text(t) > score_text(old):
            by_slug[s] = t

    source_map = {}
    missing = []

    for fn in manifest_files:
        stem = Path(fn).stem
        text = by_slug.get(stem)
        if not text:
            # last-resort fallback; should be rare
            text = stem.replace("-", " ")
            missing.append(fn)
        source_map[fn] = text

    return source_map, missing

async def synth_one(text, out_path, voice, rate, pitch, volume, retries=3):
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()

    for attempt in range(1, retries + 1):
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate,
                pitch=pitch,
                volume=volume,
            )
            await communicate.save(str(tmp))

            if not tmp.exists() or tmp.stat().st_size < 1200:
                raise RuntimeError("generated file is too small or missing")

            tmp.replace(out_path)
            return
        except Exception as e:
            if tmp.exists():
                tmp.unlink()
            if attempt >= retries:
                raise
            await asyncio.sleep(2 + attempt)

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--voice", default="de-DE-KatjaNeural")
    ap.add_argument("--rate", default="-5%")
    ap.add_argument("--pitch", default="+0Hz")
    ap.add_argument("--volume", default="+0%")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    audio_dir = root / "audio"
    manifest_path = audio_dir / "manifest.json"

    if not manifest_path.exists():
        raise RuntimeError("audio/manifest.json not found")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files") or sorted(p.name for p in audio_dir.glob("*.mp3"))

    if not files:
        raise RuntimeError("manifest contains no files")

    source_map, missing = build_source_map(root, files)

    print(f"Voice: {args.voice}")
    print(f"Rate: {args.rate}")
    print(f"Files: {len(files)}")
    print(f"Fallback source names: {len(missing)}")

    map_path = root / "data" / "audio_source_map_v15_0.json"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(
        json.dumps({
            "version": "v15.0",
            "voice": args.voice,
            "rate": args.rate,
            "missingExactSourceCount": len(missing),
            "missingExactSourceFiles": missing,
            "map": source_map,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    failures = []

    for idx, fn in enumerate(files, 1):
        out = audio_dir / fn
        text = source_map[fn]

        if out.exists() and out.stat().st_size > 1200 and not args.overwrite:
            print(f"[{idx}/{len(files)}] skip {fn}")
            continue

        print(f"[{idx}/{len(files)}] synth {fn} <- {text[:90]}")
        try:
            await synth_one(text, out, args.voice, args.rate, args.pitch, args.volume)
        except Exception as e:
            failures.append({"file": fn, "text": text, "error": str(e)})
            print(f"  ERROR: {fn}: {e}")

        await asyncio.sleep(0.15)

    if failures:
        fail_path = root / "data" / "audio_generation_failures_v15_0.json"
        fail_path.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(f"Audio generation failed for {len(failures)} files. See {fail_path}")

    manifest["version"] = "v15.0"
    manifest["count"] = len(files)
    manifest["files"] = files
    manifest["engine"] = "edge-tts"
    manifest["voice"] = args.voice
    manifest["rate"] = args.rate
    manifest["updatedAt"] = datetime.now(timezone.utc).isoformat()

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Done.")
    print(f"Manifest updated: {manifest_path}")
    print(f"Source map: {map_path}")

if __name__ == "__main__":
    asyncio.run(main())