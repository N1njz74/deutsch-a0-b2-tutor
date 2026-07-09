import argparse
import asyncio
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import edge_tts
except Exception as e:
    print("ERROR: edge_tts import failed:", e)
    sys.exit(2)

GERMAN_REPL = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",
})
CYR = re.compile(r"[А-Яа-яЁё]")
LAT = re.compile(r"[A-Za-zÄÖÜäöüß]")

def slugify(text):
    text = html.unescape(str(text or ""))
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.translate(GERMAN_REPL).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    # Must match index.html audioFileName(); otherwise long phrases are
    # generated but the app cannot find them in offline MP3 mode.
    return text[:80]

def clean_candidate(x):
    x = html.unescape(str(x or "")).strip()
    if not x:
        return ""
    before = x.split("(")[0].strip()
    if before and LAT.search(before) and not CYR.search(before):
        return before
    if LAT.search(x) and not CYR.search(x):
        return x
    return ""

def add_item(items, text, source):
    text = clean_candidate(text)
    if not text:
        return
    if len(text) > 180:
        text = text[:180].strip()
    slug = slugify(text)
    if not slug:
        return
    items.setdefault(slug, {"text": text, "sources": []})
    if source not in items[slug]["sources"]:
        items[slug]["sources"].append(source)

def load_data(index_path):
    raw = index_path.read_text(encoding="utf-8")
    m = re.search(r'<script[^>]+id=["\']app-data["\'][^>]*>(.*?)</script>', raw, re.S)
    if not m:
        raise RuntimeError("app-data not found")
    return json.loads(html.unescape(m.group(1)))

def collect(obj, items, source):
    if isinstance(obj, dict):
        for key in ["de", "example"]:
            if key in obj:
                add_item(items, obj.get(key), source + "." + key)
        if "options" in obj and isinstance(obj["options"], list):
            for i, opt in enumerate(obj["options"]):
                add_item(items, opt, source + f".options[{i}]")
        for k, v in obj.items():
            collect(v, items, source + "." + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            collect(v, items, source + f"[{i}]")
    elif isinstance(obj, str):
        add_item(items, obj, source)

async def synth_one(text, out_path, voice, rate, pitch, volume, retries=3, timeout=45):
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
            await asyncio.wait_for(communicate.save(str(tmp)), timeout=timeout)
            if not tmp.exists() or tmp.stat().st_size < 1200:
                raise RuntimeError("generated file is missing or too small")
            tmp.replace(out_path)
            return
        except Exception:
            if tmp.exists():
                tmp.unlink()
            if attempt >= retries:
                raise
            await asyncio.sleep(1.5 + attempt)

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--voice", default="de-DE-KatjaNeural")
    ap.add_argument("--rate", default="-5%")
    ap.add_argument("--pitch", default="+0Hz")
    ap.add_argument("--volume", default="+0%")
    ap.add_argument("--item-timeout", type=int, default=45)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    audio_dir = root / "audio"
    data_dir = root / "data"
    audio_dir.mkdir(exist_ok=True)
    data_dir.mkdir(exist_ok=True)

    data = load_data(root / "index.html")
    app_version = data.get("version") or "v15.2"
    items = {}

    for key in ["lessons", "vocab", "diagnostic", "examPrompts", "b2Prompts"]:
        collect(data.get(key, []), items, key)

    for t in [
        "Guten Tag. Ich lerne Deutsch.",
        "Ich lerne Deutsch.",
        "Ich komme aus Russland.",
        "Können Sie das bitte wiederholen?",
        "Ich möchte einen Termin vereinbaren.",
        "Sehr geehrte Damen und Herren",
        "Mit freundlichen Grüßen",
    ]:
        add_item(items, t, "system")

    obsolete_ukraine = audio_dir / "ich-komme-aus-der-ukraine.mp3"
    if obsolete_ukraine.exists() and "ich-komme-aus-der-ukraine" not in items:
        obsolete_ukraine.unlink()
        print("Removed obsolete:", obsolete_ukraine.name)

    ordered = sorted(items.items(), key=lambda kv: kv[0])
    print("Total unique German audio items:", len(ordered))
    print("Voice:", args.voice)

    failures = []

    for n, (slug, meta) in enumerate(ordered, 1):
        fn = slug + ".mp3"
        out = audio_dir / fn

        if out.exists() and out.stat().st_size > 1200 and not args.overwrite:
            if n % 100 == 0:
                print(f"[{n}/{len(ordered)}] skip existing...")
            continue

        print(f"[{n}/{len(ordered)}] synth {fn} <- {meta['text'][:90]}")
        try:
            await synth_one(meta["text"], out, args.voice, args.rate, args.pitch, args.volume, timeout=args.item_timeout)
        except Exception as e:
            failures.append({"file": fn, "text": meta["text"], "error": str(e)})
            print("  ERROR:", fn, e)

        await asyncio.sleep(0.12)

    if failures:
        (data_dir / "audio_generation_failures_v15_2.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8"
        )
        raise RuntimeError(f"Failed files: {len(failures)}")

    files = sorted(p.name for p in audio_dir.glob("*.mp3"))
    manifest = {
        "version": app_version,
        "engine": "edge-tts",
        "voice": args.voice,
        "rate": args.rate,
        "count": len(files),
        "files": files,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    source_map = {
        "version": app_version,
        "engine": "edge-tts",
        "voice": args.voice,
        "rate": args.rate,
        "itemCount": len(ordered),
        "items": {slug: meta for slug, meta in ordered},
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    (audio_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    safe_version = str(app_version).replace(".", "_").replace("-", "_")
    (data_dir / f"audio_all_items_{safe_version}.json").write_text(
        json.dumps(source_map, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print("Done.")
    print("MP3 files:", len(files))
    print("Required audio items:", len(ordered))

if __name__ == "__main__":
    asyncio.run(main())
