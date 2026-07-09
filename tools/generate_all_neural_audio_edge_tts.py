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

def slugify(text: str) -> str:
    text = html.unescape(str(text or ""))
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.translate(GERMAN_REPL).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:160]

def clean_candidate(x: str) -> str:
    x = html.unescape(str(x or "")).strip()
    if not x:
        return ""
    before = x.split("(")[0].strip()
    if before and re.search(r"[A-Za-zÄÖÜäöüß]", before) and not CYR.search(before):
        return before
    if re.search(r"[A-Za-zÄÖÜäöüß]", x) and not CYR.search(x):
        return x
    return ""

def add_item(items: dict, text: str, source: str):
    text = clean_candidate(text)
    if not text:
        return
    if len(text) > 180:
        text = text[:180].strip()
    slug = slugify(text)
    if not slug:
        return
    if slug not in items:
        items[slug] = {"text": text, "sources": []}
    if source not in items[slug]["sources"]:
        items[slug]["sources"].append(source)

def load_data(index_path: Path):
    raw = index_path.read_text(encoding="utf-8")
    m = re.search(r'<script[^>]+id=["\']app-data["\'][^>]*>(.*?)</script>', raw, re.S)
    if not m:
        raise RuntimeError("app-data not found")
    return json.loads(html.unescape(m.group(1)))

def collect_from_obj(obj, items, source_prefix):
    if isinstance(obj, dict):
        if "de" in obj:
            add_item(items, obj.get("de"), source_prefix + ".de")
        if "example" in obj:
            add_item(items, obj.get("example"), source_prefix + ".example")
        if "ru" in obj:
            # нужно для старых v13-записей, где немецкая фраза лежит в ru/example
            add_item(items, obj.get("ru"), source_prefix + ".ru")
        if "options" in obj and isinstance(obj["options"], list):
            for i, opt in enumerate(obj["options"]):
                add_item(items, opt, source_prefix + f".options[{i}]")
        for k, v in obj.items():
            collect_from_obj(v, items, source_prefix + "." + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            collect_from_obj(v, items, source_prefix + f"[{i}]")
    elif isinstance(obj, str):
        add_item(items, obj, source_prefix)

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
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    audio_dir = root / "audio"
    audio_dir.mkdir(exist_ok=True)

    data = load_data(root / "index.html")
    items = {}

    collect_from_obj(data.get("lessons", []), items, "lessons")
    collect_from_obj(data.get("vocab", []), items, "vocab")
    collect_from_obj(data.get("diagnostic", []), items, "diagnostic")
    collect_from_obj(data.get("examPrompts", []), items, "examPrompts")
    collect_from_obj(data.get("b2Prompts", []), items, "b2Prompts")

    # системные тестовые фразы
    for t in [
        "Guten Tag. Ich lerne Deutsch.",
        "Ich lerne Deutsch.",
        "Können Sie das bitte wiederholen?",
        "Ich möchte einen Termin vereinbaren.",
        "Sehr geehrte Damen und Herren",
        "Mit freundlichen Grüßen",
    ]:
        add_item(items, t, "system")

    ordered = sorted(items.items(), key=lambda kv: kv[0])
    print("Total unique German audio items:", len(ordered))
    print("Voice:", args.voice)

    source_map = {
        "version": "v15.1",
        "engine": "edge-tts",
        "voice": args.voice,
        "rate": args.rate,
        "count": len(ordered),
        "items": {slug: meta for slug, meta in ordered},
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    (root / "data" / "audio_all_items_v15_1.json").write_text(
        json.dumps(source_map, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    failures = []

    for n, (slug, meta) in enumerate(ordered, 1):
        fn = slug + ".mp3"
        out = audio_dir / fn

        if out.exists() and out.stat().st_size > 1200 and not args.overwrite:
            print(f"[{n}/{len(ordered)}] skip {fn}")
            continue

        print(f"[{n}/{len(ordered)}] synth {fn} <- {meta['text'][:100]}")
        try:
            await synth_one(meta["text"], out, args.voice, args.rate, args.pitch, args.volume)
        except Exception as e:
            failures.append({"file": fn, "text": meta["text"], "error": str(e)})
            print("  ERROR:", fn, e)

        await asyncio.sleep(0.12)

    if failures:
        (root / "data" / "audio_generation_failures_v15_1.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8"
        )
        raise RuntimeError(f"Failed files: {len(failures)}")

    files = sorted(p.name for p in audio_dir.glob("*.mp3"))
    manifest = {
        "version": "v15.1",
        "engine": "edge-tts",
        "voice": args.voice,
        "rate": args.rate,
        "count": len(files),
        "files": files,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    (audio_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print("Done.")
    print("MP3 files:", len(files))

if __name__ == "__main__":
    asyncio.run(main())