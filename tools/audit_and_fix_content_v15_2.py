import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

CYR = re.compile(r"[А-Яа-яЁё]")
LAT = re.compile(r"[A-Za-zÄÖÜäöüß]")

def has_cyr(s):
    return bool(CYR.search(str(s or "")))

def has_lat(s):
    return bool(LAT.search(str(s or "")))

def clean(s):
    return str(s or "").strip()

def replace_country_text(s):
    if not isinstance(s, str):
        return s, 0

    old = s
    pairs = [
        ("Ich komme aus der Ukraine.", "Ich komme aus Russland."),
        ("Ich komme aus der Ukraine", "Ich komme aus Russland"),
        ("aus der Ukraine", "aus Russland"),
        ("der Ukraine", "Russland"),
        ("Ukraine", "Russland"),
        ("Я из Украины.", "Я из России."),
        ("Я из Украины", "Я из России"),
        ("из Украины", "из России"),
        ("Украины", "России"),
        ("Украине", "России"),
        ("Украина", "Россия"),
        ("украинский", "российский"),
        ("украинская", "российская"),
        ("украинское", "российское"),
        ("украинские", "российские"),
    ]

    for a, b in pairs:
        s = s.replace(a, b)

    return s, int(s != old)

def walk_replace_country(obj, stats):
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if isinstance(v, str):
                nv, changed = replace_country_text(v)
                if changed:
                    stats["country_replacements"] += 1
                    obj[k] = nv
            else:
                walk_replace_country(v, stats)
    elif isinstance(obj, list):
        for x in obj:
            walk_replace_country(x, stats)

def split_german_russian(s):
    s = clean(s)
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*\.?$", s)
    if m:
        de = clean(m.group(1))
        ru = clean(m.group(2))
        if has_lat(de) and not has_cyr(de):
            return de, ru
    return s, ""

def fix_v13_swapped_vocab(data, stats):
    for v in data.get("vocab", []):
        if not isinstance(v, dict):
            continue

        de = clean(v.get("de"))
        ru = clean(v.get("ru"))
        ex = clean(v.get("example"))

        if has_cyr(de) and has_lat(ru):
            new_de, ru_inside = split_german_russian(ru)
            if new_de and has_lat(new_de) and not has_cyr(new_de):
                old_de = de
                v["de"] = new_de

                if ru_inside and has_cyr(ru_inside):
                    v["ru"] = ru_inside
                elif has_cyr(ex):
                    v["ru"] = ex
                else:
                    v["ru"] = old_de

                if (not ex) or has_cyr(ex):
                    v["example"] = new_de

                stats["swapped_v13_vocab_fields"] += 1

def is_probably_plural_de(de):
    x = clean(de).lower()
    plural_markers = [
        "die laborwerte",
        "die unterlagen",
        "die entlassungsunterlagen",
        "die beschwerden",
        "die schmerzen",
        "die risiken",
        "die alternativen",
        "die komplikationen",
        "die kosten",
        "die daten",
        "die medikamente",
        "die quellen",
        "die maßnahmen",
        "die massnahmen",
        "erneuerbare energien",
    ]
    return any(m in x for m in plural_markers)

def fix_generated_examples(data, stats):
    for v in data.get("vocab", []):
        if not isinstance(v, dict):
            continue

        de = clean(v.get("de"))
        ex = clean(v.get("example"))

        if not de or not ex:
            continue

        if is_probably_plural_de(de) and ex.startswith(de + " ist "):
            v["example"] = ex.replace(de + " ist ", de + " sind ", 1)
            stats["plural_example_fixes"] += 1

        if "+" in de and "  ist in diesem Kontext wichtig" in ex:
            fixed = de
            fixed = fixed.replace("+ Akk.", "das Thema")
            fixed = fixed.replace("+ Akkusativ", "das Thema")
            fixed = fixed.replace("+ Dat.", "diesem Bereich")
            fixed = fixed.replace("+ Dativ", "diesem Bereich")
            fixed = fixed.replace("+ Gen.", "der Kosten")
            fixed = fixed.replace("+ Genitiv", "der Kosten")
            fixed = re.sub(r"\s+", " ", fixed).strip()
            v["example"] = fixed + " ist eine wichtige Struktur."
            stats["redemittel_example_fixes"] += 1

def explanation_for(q, correct):
    raw = " ".join([
        clean(q.get("q")),
        clean(q.get("topic")),
        clean(q.get("level")),
        clean(correct),
        " ".join(map(str, q.get("options", []))),
    ]).lower()

    if "ei" in raw or "mein" in raw:
        return "ei читается как «ай»: mein ≈ майн, nein ≈ найн."
    if "sch" in raw:
        return "sch читается как «ш»: Schule, Deutsch, sprechen."
    if "guten tag" in raw:
        return "Guten Tag — стандартное дневное приветствие: «добрый день»."
    if "ich" in raw and ("bin" in raw or "sein" in raw):
        return "С глаголом sein форма для ich — bin: ich bin. Bist относится к du, ist — к er/sie/es."
    if "du" in raw and "lernen" in raw:
        return "У регулярного глагола lernen во 2-м лице окончание -st: du lernst."
    if "haben sie zeit" in raw or "ja/nein" in raw:
        return "В Ja/Nein-вопросе глагол стоит первым: Haben Sie Zeit?"
    if "wo wohnen" in raw or "w-frage" in raw or "w-вопрос" in raw:
        return "В W-вопросе порядок: вопросительное слово + глагол + подлежащее: Wo wohnen Sie?"
    if "um acht" in raw or "точному времени" in raw:
        return "Для точного времени используется um: um acht Uhr. Для дней — am Montag."
    if "akkusativ" in raw or "den termin" in raw or "кого/что" in raw:
        return "Akkusativ отвечает на «кого? что?». У мужского рода der/ein меняется на den/einen."
    if "dativ" in raw or "mit " in raw or "bei " in raw or "zu " in raw:
        return "Dativ нужен после mit, bei, zu, aus, von, seit, nach и часто отвечает на «кому?»."
    if "genitiv" in raw or "aufgrund" in raw or "wegen" in raw or "trotz" in raw:
        return "В письменном стандарте aufgrund, wegen, trotz, während часто требуют Genitiv."
    if "modal" in raw or "muss" in raw or "möchte" in raw or "können" in raw:
        return "С модальным глаголом смысловой глагол обычно стоит в конце в инфинитиве."
    if "perfekt" in raw or "partizip" in raw or "gefahren" in raw:
        return "Perfekt строится как haben/sein + Partizip II. Движение с изменением места часто берёт sein."
    if "weil" in raw or "dass" in raw or "wenn" in raw or "obwohl" in raw or "nebensatz" in raw:
        return "После weil/dass/wenn/obwohl спрягаемый глагол уходит в конец придаточного."
    if "um" in raw and "zu" in raw:
        return "um ... zu выражает цель, если субъект в главном и инфинитивном обороте один и тот же."
    if "adjektiv" in raw or "guter" in raw or "gute idee" in raw:
        return "Окончание прилагательного зависит от рода, падежа и артикля: ein guter Plan, eine gute Idee, ein gutes Beispiel."
    if "relativ" in raw or "mit ___" in raw:
        return "В Relativsatz местоимение зависит от падежа внутри придаточного; после mit нужен Dativ."
    if "passiv" in raw or "wurde" in raw or "werden" in raw:
        return "Passiv смещает фокус на действие: wird geprüft, wurde geprüft, ist geprüft worden."
    if "konjunktiv ii" in raw or "hätte" in raw or "wäre" in raw or "könnte" in raw:
        return "Konjunktiv II используется для вежливости, гипотез и нереальных условий."
    if "konjunktiv i" in raw or "sei" in raw or "er habe" in raw:
        return "Konjunktiv I используется для косвенной речи: er habe, sie sei."
    if "dennoch" in raw or "deshalb" in raw or "trotzdem" in raw:
        return "dennoch/deshalb/trotzdem занимают первое поле, поэтому после них сразу стоит спрягаемый глагол."
    if "nominalstil" in raw or "nach prüfung" in raw:
        return "Nominalstil делает текст официальнее: nachdem man geprüft hat → nach Prüfung."
    if "rückmeldung" in raw or "официаль" in raw:
        return "В официальной ситуации нужен нейтральный регистр: Ich bitte um Rückmeldung."
    if "einwilligung" in raw:
        return "die Einwilligung — согласие пациента; в медицине это ключевое слово перед процедурой."
    if "franchise" in raw:
        return "die Franchise в Швейцарии относится к медицинской страховке и собственному участию в расходах."
    if "trockenschichtdicke" in raw:
        return "die Trockenschichtdicke — сухая толщина слоя покрытия; это термин строительства/АКЗ."

    return f"Правильный ответ: «{correct}». Здесь важно проверить форму, падеж, порядок слов, смысл или регистр."

def fill_explanations(data, stats):
    containers = []

    for lesson in data.get("lessons", []):
        if isinstance(lesson, dict):
            for d in lesson.get("drills", []):
                if isinstance(d, dict):
                    containers.append(d)

    for d in data.get("diagnostic", []):
        if isinstance(d, dict):
            containers.append(d)

    for q in containers:
        opts = q.get("options", [])
        ans = q.get("answer")
        if not isinstance(opts, list):
            continue
        try:
            correct = opts[int(ans)]
        except Exception:
            correct = ""
        if not clean(q.get("explanation")):
            q["explanation"] = explanation_for(q, correct)
            stats["explanations_filled"] += 1

def audit_counts(data):
    counts = {
        "lessons": len(data.get("lessons", [])),
        "vocab": len(data.get("vocab", [])),
        "diagnostic": len(data.get("diagnostic", [])),
    }

    cyr_de = []
    empty_expl = 0
    ukr = []

    def walk(obj, path=""):
        nonlocal empty_expl
        if isinstance(obj, dict):
            if "de" in obj and has_cyr(obj.get("de")):
                cyr_de.append({"path": path, "de": obj.get("de"), "ru": obj.get("ru"), "example": obj.get("example")})
            if "explanation" in obj and not clean(obj.get("explanation")):
                empty_expl += 1
            for k, v in obj.items():
                if isinstance(v, str) and ("Ukraine" in v or "Украин" in v or "Украин" in v or "Украины" in v):
                    ukr.append({"path": path + "." + k, "text": v})
                else:
                    walk(v, path + "." + str(k))
        elif isinstance(obj, list):
            for i, x in enumerate(obj):
                walk(x, path + f"[{i}]")

    walk(data)

    counts["cyrillic_in_de_after_fix"] = len(cyr_de)
    counts["empty_explanations_after_fix"] = empty_expl
    counts["ukraine_refs_after_fix"] = len(ukr)
    counts["cyrillic_de_samples"] = cyr_de[:30]
    counts["ukraine_samples"] = ukr[:30]
    return counts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    args = ap.parse_args()

    root = Path(args.root)
    index = root / "index.html"
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)

    html_text = index.read_text(encoding="utf-8")
    m = re.search(r'(<script[^>]+id=["\']app-data["\'][^>]*>)(.*?)(</script>)', html_text, re.S)
    if not m:
        raise RuntimeError("app-data not found")

    data = json.loads(html.unescape(m.group(2)))
    data["version"] = "v15.2"

    stats = {
        "country_replacements": 0,
        "swapped_v13_vocab_fields": 0,
        "plural_example_fixes": 0,
        "redemittel_example_fixes": 0,
        "explanations_filled": 0,
    }

    walk_replace_country(data, stats)
    fix_v13_swapped_vocab(data, stats)
    fix_generated_examples(data, stats)
    fill_explanations(data, stats)

    counts = audit_counts(data)

    new_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html_text = html_text[:m.start(2)] + new_json + html_text[m.end(2):]
    html_text = re.sub(r'("version"\s*:\s*")v\d+\.\d+(")', r'\1v15.2\2', html_text, count=1)
    html_text = re.sub(r'<b>Версия v\d+\.\d+\.</b>', '<b>Версия v15.2.</b>', html_text)

    index.write_text(html_text, encoding="utf-8")

    audit = {
        "version": "v15.2",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "counts": counts,
        "weakSpotsDetected": [
            "В старых v13-записях часть немецких фраз была в поле ru, а в поле de лежал русский ярлык.",
            "В упражнениях и диагностике было много пустых explanation.",
            "Были механические примеры вида 'X ist in diesem Kontext wichtig', иногда с ошибкой числа.",
            "Была персональная фраза про Украину, заменена на Россию.",
            "Аудио-пакет должен строиться из app-data, а не только из старого audio/manifest.json."
        ],
        "actionsApplied": [
            "Ukraine/Russian country text replacement",
            "v13 bilingual field repair",
            "missing explanation generation",
            "plural example agreement fixes",
            "audit report generation"
        ]
    }

    (data_dir / "content_audit_v15_2.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print("Content audit v15.2")
    print(json.dumps({"stats": stats, "counts": {k:v for k,v in counts.items() if not k.endswith('_samples')}}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()