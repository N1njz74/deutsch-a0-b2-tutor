import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

VERSION = "v15.5"
DATE = "2026-07-09"

CYR = re.compile(r"[А-Яа-яЁё]")
LAT = re.compile(r"[A-Za-zÄÖÜäöüß]")


def load_index(index_path):
    text = index_path.read_text(encoding="utf-8")
    match = re.search(
        r'(<script[^>]+id=["\']app-data["\'][^>]*>)(.*?)(</script>)',
        text,
        re.S,
    )
    if not match:
        raise RuntimeError("app-data JSON not found")
    data = json.loads(html.unescape(match.group(2)))
    return text, match, data


def replace_index_data(text, match, data):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text[: match.start(2)] + payload + text[match.end(2) :]


def clean(value):
    return str(value or "").strip()


def has_german_text(value):
    value = clean(value)
    return bool(LAT.search(value)) and not CYR.search(value)


def classify_lesson(lesson):
    tags = set(lesson.get("tags") or [])
    blob = " ".join(
        [
            clean(lesson.get("id")),
            clean(lesson.get("title")),
            clean(lesson.get("module")),
            clean(lesson.get("rule")),
            " ".join(tags),
        ]
    ).lower()

    def has(*needles):
        return any(n in blob for n in needles)

    if has("pronunciation", "произнош", "алфавит", "умлаут", "ß"):
        return "pronunciation"
    if has("word-order", "порядок", "v2", "satzbau", "verbposition", "рамка"):
        return "word_order"
    if has("question", "вопрос", "ja/nein", "w-вопрос", "indirekte fragen"):
        return "questions"
    if has("artikel", "article", "артик", "der/die/das", "nominativ"):
        return "articles"
    if has("akkusativ", "dativ", "genitiv", "падеж", "case"):
        return "cases"
    if has("nicht", "kein", "negation", "отриц"):
        return "negation"
    if has("modal", "модаль", "müssen", "können", "möchten", "dürfen", "sollen"):
        return "modal"
    if has("trennbare", "separable", "отделяем", "anrufen", "aufstehen"):
        return "separable"
    if has("imperativ", "imperative", "императив"):
        return "imperative"
    if has("perfekt", "präteritum", "praeteritum", "plusquamperfekt", "partizip", "past"):
        return "past"
    if has("weil", "dass", "wenn", "obwohl", "damit", "um-zu", "um zu", "придат"):
        return "clauses"
    if has("adjektiv", "adjective", "прилагательн"):
        return "adjectives"
    if has("pronomen", "pronoun", "местоим", "da-wo", "wo-", "relativ"):
        return "pronouns"
    if has("passiv", "passive", "пассив"):
        return "passive"
    if has("konjunktiv", "косвенная речь"):
        return "konjunktiv"
    if has("präposition", "praeposition", "preposition", "предлог", "управление"):
        return "prepositions"
    if has("konnektor", "connector", "argumentation", "аргументац", "kohärenz"):
        return "connectors"
    if has("brief", "bewerbung", "beschwerde", "formal", "официаль", "register", "style"):
        return "writing"
    if has("nominal", "nominalstil"):
        return "nominal"
    if has("medizin", "medical", "patient", "aufklärung", "клиник"):
        return "medical"
    if has("schweiz", "swiss", "krankenkasse", "spital"):
        return "swiss"
    if has("chirurgie", "surgery", "пластическ", "эстетическ"):
        return "surgery"
    if has("mündlich", "muendlich", "speaking", "говорение"):
        return "speaking"
    return "default"


EXPLAIN_BY_KIND = {
    "pronunciation": "Для русскоговорящего здесь важен не перевод, а звук: немецкое буквосочетание читается стабильно, но не по-русски и не по-английски.",
    "word_order": "Для русскоговорящего ключевой контроль - место спрягаемого глагола. В главном предложении он стоит на позиции 2.",
    "questions": "В русском вопрос часто держится интонацией, а в немецком его показывает порядок слов: глагол первым или после W-слова.",
    "articles": "Артикль нужно учить вместе с существительным: он показывает род, число и падеж, которых в русском нет в такой форме.",
    "cases": "Сравнивайте не русский перевод, а роль слова: Nominativ - кто, Akkusativ - кого/что, Dativ - кому/с кем/где, Genitiv - чей/из-за чего.",
    "negation": "nicht отрицает действие, качество или всю мысль; kein отрицает существительное. Русское «не/нет» нельзя переносить одним способом.",
    "modal": "Модальный глагол занимает вторую позицию, а смысловой глагол уходит в конец в инфинитиве.",
    "separable": "У отделяемого глагола спрягается основа, а приставка закрывает фразу в конце: rufe ... an.",
    "imperative": "Форма команды зависит от дистанции: с незнакомыми безопаснее Verb + Sie + bitte.",
    "past": "В Perfekt нужен помощник haben/sein и Partizip II в конце; движение с изменением места часто берет sein.",
    "clauses": "После weil/dass/wenn/obwohl спрягаемый глагол уходит в конец придаточного.",
    "adjectives": "Окончание прилагательного зависит от артикля, рода, числа и падежа, а не только от русского смысла.",
    "pronouns": "Местоимение выбирается по роли внутри немецкой части фразы, а не по русскому вопросу целиком.",
    "passive": "Passiv переносит фокус с исполнителя на действие или результат: wird geprüft, wurde geprüft, ist geprüft worden.",
    "konjunktiv": "Konjunktiv нужен для вежливости, гипотез и косвенной речи; он меняет тон высказывания.",
    "prepositions": "Немецкий предлог учится вместе с падежом и глаголом управления, потому что русский предлог часто не совпадает.",
    "connectors": "Связка занимает поле предложения и влияет на порядок слов: deshalb/trotzdem требуют глагол сразу после себя.",
    "writing": "В официальном немецком важны нейтральный тон, точная просьба и стандартные формулы, а не дословная русская канцелярская фраза.",
    "nominal": "Nominalstil делает B2-текст компактнее и официальнее: действие часто превращается в существительное с Genitiv.",
    "medical": "В медицинском немецком важны точность, нейтральный тон, риск, согласие и последующее наблюдение.",
    "swiss": "Для Швейцарии нужно узнавать региональные слова, но грамматику и официальный стиль держать стандартными.",
    "surgery": "В эстетической медицине нельзя обещать результат: B2-формулировки должны говорить о рисках, ожиданиях и согласии.",
    "speaking": "В устном ответе важнее структура, чем скорость: тема, мнение, причина, пример, вывод.",
    "default": "Для русскоговорящего главное - не переводить дословно, а проверить немецкую форму: глагол, артикль, падеж, предлог и порядок слов.",
}


def specific_explanation(question, correct, lesson):
    q = clean(question.get("q")).lower()
    correct_text = clean(correct)
    correct_l = correct_text.lower()
    kind = classify_lesson(lesson)

    if re.search(r"сочетани[ея].*ei|«ei»|\\bei\\b", q):
        return "Правильно: «{0}». Сочетание ei читается как «ай»: mein ≈ майн, nein ≈ найн.".format(correct_text)
    if re.search(r"сочетани[ея].*sch|«sch»|\\bsch\\b", q):
        return "Правильно: «{0}». sch читается как «ш»: Schule, Deutsch, sprechen.".format(correct_text)
    if "guten tag" in q or "guten tag" in correct_l:
        return "Правильно: «{0}». Guten Tag - нейтральное дневное приветствие, безопасное в официальной ситуации.".format(correct_text)
    if "меня зовут" in q or "heiße" in correct_l:
        return "Правильно: «{0}». Русское «меня зовут» по-немецки выражается глаголом heißen: Ich heiße Anna.".format(correct_text)
    if "повтор" in q and ("wiederholen" in correct_l or "noch einmal" in correct_l):
        return "Правильно: «{0}». Вежливая просьба строится через Können Sie ... bitte ...?, а не через прямой приказ.".format(correct_text)
    if "du ..." in q and "zeit" in q and correct_l == "hast":
        return "Правильно: «hast». У haben форма для du - du hast; русское «у тебя есть» переводится через haben."
    if "werden" in q and "станов" in correct_l:
        return "Правильно: «становиться». werden сначала значит «становиться», а уже потом участвует в Futur и Passiv."
    if "где стоит" in q and "глагол" in q:
        return "Правильно: «{0}». В немецком главном предложении спрягаемый глагол занимает вторую позицию.".format(correct_text)
    if "ja/nein" in q or "haben sie zeit" in correct_l:
        return "Правильно: «{0}». В вопросе без вопросительного слова спрягаемый глагол стоит первым.".format(correct_text)
    if "w-слово" in q or correct_l in {"wo", "wann", "warum", "wie", "wer", "was"}:
        return "Правильно: «{0}». W-слово занимает первое место, а спрягаемый глагол остается на втором.".format(correct_text)
    if "точному времени" in q or correct_l == "um acht uhr":
        return "Правильно: «{0}». Для точного времени используется um, а для дней недели - am.".format(correct_text)
    if "в понедельник" in q or correct_l == "am montag":
        return "Правильно: «am Montag». Дни недели в значении «в понедельник» оформляются через am + день."
    if "morgen" in q and "завтра" in correct_l:
        return "Правильно: «завтра». Morgen с большой буквы - утро, morgen с маленькой - завтра."
    if "nicht" in correct_l or "kein" in correct_l:
        return "Правильно: «{0}». kein отрицает существительное, nicht - действие, качество или всю мысль.".format(correct_text)
    if "akkusativ" in q or "den " in correct_l or "einen " in correct_l:
        return "Правильно: «{0}». Akkusativ показывает объект действия; у мужского рода der/ein меняется на den/einen.".format(correct_text)
    if "dativ" in q or "dem " in correct_l or "der kollegin" in correct_l or "mit " in correct_l:
        return "Правильно: «{0}». Dativ часто нужен после mit, bei, zu, aus, von, seit, nach и для адресата помощи.".format(correct_text)
    if "genitiv" in q or "wegen" in correct_l or "aufgrund" in correct_l:
        return "Правильно: «{0}». В письменном стандарте wegen/aufgrund/trotz/während обычно требуют Genitiv.".format(correct_text)
    if "muss" in correct_l or "möchte" in correct_l or "kann" in correct_l or "können" in correct_l:
        return "Правильно: «{0}». После модального глагола смысловой глагол обычно стоит в конце в инфинитиве.".format(correct_text)
    if "weil" in correct_l or "dass" in correct_l or "wenn" in correct_l or "obwohl" in correct_l:
        return "Правильно: «{0}». В придаточном предложении спрягаемый глагол уходит в конец.".format(correct_text)
    if "um " in correct_l and " zu " in correct_l:
        return "Правильно: «{0}». um ... zu выражает цель, если субъект в главной и инфинитивной части один и тот же.".format(correct_text)
    if "habe" in correct_l and ("ge" in correct_l or "partizip" in q):
        return "Правильно: «{0}». Perfekt строится как haben/sein + Partizip II, а Partizip обычно закрывает фразу.".format(correct_text)
    if "bin" in correct_l and ("ge" in correct_l or "gefahren" in correct_l or "gegangen" in correct_l):
        return "Правильно: «{0}». Движение с изменением места в Perfekt часто берет sein.".format(correct_text)
    if "wird" in correct_l or "wurde" in correct_l or "worden" in correct_l:
        return "Правильно: «{0}». Passiv строится через werden + Partizip II и фокусирует действие, а не исполнителя.".format(correct_text)
    if "hätte" in correct_l or "wäre" in correct_l or "könnte" in correct_l:
        return "Правильно: «{0}». Konjunktiv II звучит вежливо или гипотетически, что важно для B1/B2.".format(correct_text)
    if "sei" in correct_l or "er habe" in correct_l:
        return "Правильно: «{0}». Konjunktiv I используется для косвенной речи: автор передает чужие слова дистанционно.".format(correct_text)
    if "deshalb" in correct_l or "trotzdem" in correct_l or "dennoch" in correct_l:
        return "Правильно: «{0}». Эта связка занимает первое поле, поэтому после нее сразу идет спрягаемый глагол.".format(correct_text)
    if "rückmeldung" in correct_l or "mit freundlichen grüßen" in correct_l or "hiermit" in correct_l:
        return "Правильно: «{0}». Это нейтральная официальная формула; она звучит естественнее дословной русской кальки.".format(correct_text)

    return "Правильно: «{0}». {1}".format(correct_text, EXPLAIN_BY_KIND.get(kind, EXPLAIN_BY_KIND["default"]))


def fix_explanations(data):
    stats = {
        "updated": 0,
        "generic_before": 0,
        "mismatch_markers_before": 0,
    }
    bad_markers = [
        "ei читается",
        "sch читается",
        "Passiv смещает",
        "Здесь важно проверить форму",
    ]
    for lesson in data.get("lessons", []):
        for drill in lesson.get("drills") or []:
            old = clean(drill.get("explanation"))
            if "Здесь важно проверить форму" in old:
                stats["generic_before"] += 1
            if any(marker in old for marker in bad_markers):
                stats["mismatch_markers_before"] += 1
            options = drill.get("options") or []
            answer = drill.get("answer")
            try:
                correct = options[int(answer)]
            except Exception:
                correct = ""
            new = specific_explanation(drill, correct, lesson)
            if old != new:
                drill["explanation"] = new
                stats["updated"] += 1

    diagnostic_lesson = {
        "id": "diagnostic",
        "title": "Диагностика уровня",
        "tags": ["diagnostic"],
        "rule": "Проверка типичных ошибок русскоговорящего ученика.",
    }
    for question in data.get("diagnostic", []):
        old = clean(question.get("explanation"))
        if "Здесь важно проверить форму" in old:
            stats["generic_before"] += 1
        if any(marker in old for marker in bad_markers):
            stats["mismatch_markers_before"] += 1
        options = question.get("options") or []
        answer = question.get("answer")
        try:
            correct = options[int(answer)]
        except Exception:
            correct = ""
        new = specific_explanation(question, correct, diagnostic_lesson)
        if old != new:
            question["explanation"] = new
            stats["updated"] += 1
    return stats


def table(title, headers, rows):
    return {"title": title, "headers": headers, "rows": rows}


RUSSIAN_BRIDGE_LESSONS = [
    {
        "id": "a0-15-russian-bridge",
        "level": "A0",
        "module": "Русскоговорящий мост",
        "title": "Русская мысль -> немецкая фраза",
        "goal": "Научиться не переводить первые фразы дословно.",
        "rule": "В немецком часто выбирается не тот же глагол, что в русском. «Меня зовут» = ich heiße, «мне 30 лет» = ich bin 30 Jahre alt, «у меня есть» = ich habe.",
        "examples": [
            {"de": "Ich heiße Anna.", "ru": "Меня зовут Анна."},
            {"de": "Ich bin dreißig Jahre alt.", "ru": "Мне тридцать лет."},
            {"de": "Ich komme aus Russland.", "ru": "Я из России."},
            {"de": "Ich habe eine Frage.", "ru": "У меня есть вопрос."},
            {"de": "Ich brauche Hilfe.", "ru": "Мне нужна помощь."},
        ],
        "drills": [
            {
                "q": "Как сказать «Меня зовут Анна»?",
                "options": ["Ich bin Anna heißen.", "Ich heiße Anna.", "Mich nennt Anna."],
                "answer": 1,
                "topic": "russian-transfer",
            },
            {
                "q": "Как сказать «Мне 30 лет»?",
                "options": ["Ich habe dreißig Jahre.", "Ich bin dreißig Jahre alt.", "Mir ist dreißig."],
                "answer": 1,
                "topic": "russian-transfer",
            },
            {
                "q": "Как сказать «У меня есть вопрос»?",
                "options": ["Ich habe eine Frage.", "Bei mir ist eine Frage.", "Ich bin eine Frage."],
                "answer": 0,
                "topic": "russian-transfer",
            },
            {
                "q": "Как сказать «Мне нужна помощь»?",
                "options": ["Ich brauche Hilfe.", "Mir muss Hilfe.", "Ich habe helfen."],
                "answer": 0,
                "topic": "russian-transfer",
            },
        ],
        "deepTheoryRu": "Русскоговорящий новичок часто ищет немецкое слово под каждое русское слово. На A0 это мешает: немецкий берет готовую конструкцию целиком. Поэтому фразу нужно учить как шаблон, а не как набор отдельных переводов.",
        "russianTrap": "Ловушка: «мне 30 лет» перевести через haben, потому что по-русски есть скрытая идея «у меня 30 лет». В немецком возраст выражается через sein: Ich bin ... Jahre alt.",
        "germanLogic": "Немецкий выбирает устойчивый глагол конструкции: heißen для имени, sein для возраста, kommen aus для происхождения, haben для наличия.",
        "formula": "русская мысль -> немецкий шаблон: меня зовут -> ich heiße; мне ... лет -> ich bin ... Jahre alt",
        "typicalMistakes": [
            "Ich habe dreißig Jahre",
            "Ich bin heißen Anna",
            "Ich brauche eine Hilfe вместо Ich brauche Hilfe",
        ],
        "grammarTables": [
            table(
                "Русская мысль и немецкий шаблон",
                ["Русский смысл", "Немецкая форма", "Почему"],
                [
                    ["меня зовут", "ich heiße", "глагол heißen"],
                    ["мне ... лет", "ich bin ... Jahre alt", "возраст через sein"],
                    ["я из России", "ich komme aus Russland", "происхождение через kommen aus"],
                    ["у меня есть", "ich habe", "наличие через haben"],
                ],
            )
        ],
        "contrastExamples": [
            {
                "ru": "Мне тридцать лет.",
                "literal": "Не так: Ich habe dreißig Jahre.",
                "de": "Ich bin dreißig Jahre alt.",
                "note": "Возраст в немецком - через sein.",
            },
            {
                "ru": "Меня зовут Анна.",
                "literal": "Не так: Ich bin heißen Anna.",
                "de": "Ich heiße Anna.",
                "note": "heißen уже содержит смысл «зваться».",
            },
        ],
    },
    {
        "id": "a1-18-russian-cases",
        "level": "A1",
        "module": "Русскоговорящий мост",
        "title": "Падежи без русской кальки",
        "goal": "Выбирать Akkusativ и Dativ по немецкой роли слова.",
        "rule": "Русский вопрос помогает не всегда. В немецком падеж часто задают глагол и предлог: sehen + Akkusativ, helfen + Dativ, mit + Dativ, warten auf + Akkusativ.",
        "examples": [
            {"de": "Ich sehe den Arzt.", "ru": "Я вижу врача."},
            {"de": "Ich spreche mit dem Arzt.", "ru": "Я говорю с врачом."},
            {"de": "Ich helfe der Kollegin.", "ru": "Я помогаю коллеге."},
            {"de": "Ich habe einen Termin.", "ru": "У меня есть запись/приём."},
            {"de": "Ich gehe zur Apotheke.", "ru": "Я иду в аптеку."},
        ],
        "drills": [
            {
                "q": "sehen + der Arzt ->",
                "options": ["Ich sehe der Arzt.", "Ich sehe den Arzt.", "Ich sehe dem Arzt."],
                "answer": 1,
                "topic": "cases",
            },
            {
                "q": "mit + der Arzt ->",
                "options": ["mit den Arzt", "mit dem Arzt", "mit der Arzt"],
                "answer": 1,
                "topic": "cases",
            },
            {
                "q": "helfen + die Kollegin ->",
                "options": ["Ich helfe die Kollegin.", "Ich helfe der Kollegin.", "Ich helfe den Kollegin."],
                "answer": 1,
                "topic": "cases",
            },
            {
                "q": "warten auf + der Bus ->",
                "options": ["Ich warte auf den Bus.", "Ich warte auf dem Bus.", "Ich warte den Bus."],
                "answer": 0,
                "topic": "prepositions",
            },
        ],
        "deepTheoryRu": "Русские падежные вопросы похожи на немецкие только частично. Немецкий падеж нельзя выбирать только по переводу: его задаёт управление глагола или предлог.",
        "russianTrap": "Ловушка: «помогаю коллегу» по смыслу кажется объектом, но helfen требует Dativ: ich helfe der Kollegin.",
        "germanLogic": "Глагол и предлог управляют формой артикля. Сначала ищем управление, потом выбираем падеж.",
        "formula": "глагол/предлог -> падеж -> артикль: mit -> Dativ -> dem Arzt",
        "typicalMistakes": [
            "Ich helfe die Kollegin",
            "mit den Arzt",
            "Ich warte den Bus",
        ],
        "grammarTables": [
            table(
                "Управление для A1",
                ["Конструкция", "Падеж", "Пример"],
                [
                    ["sehen", "Akkusativ", "Ich sehe den Arzt."],
                    ["helfen", "Dativ", "Ich helfe der Kollegin."],
                    ["mit", "Dativ", "mit dem Arzt"],
                    ["warten auf", "Akkusativ", "auf den Bus warten"],
                ],
            )
        ],
        "contrastExamples": [
            {
                "ru": "Я помогаю коллеге.",
                "literal": "Не так: Ich helfe die Kollegin.",
                "de": "Ich helfe der Kollegin.",
                "note": "helfen требует Dativ.",
            },
            {
                "ru": "Я жду автобус.",
                "literal": "Не так: Ich warte den Bus.",
                "de": "Ich warte auf den Bus.",
                "note": "warten требует auf + Akkusativ.",
            },
        ],
    },
    {
        "id": "a2-18-russian-nebensatz",
        "level": "A2",
        "module": "Русскоговорящий мост",
        "title": "Придаточные после русских «потому что/что/если»",
        "goal": "Ставить глагол в конец после weil, dass, wenn и ob.",
        "rule": "В русском после «потому что» порядок часто остаётся обычным. В немецком после weil/dass/wenn/ob спрягаемый глагол уходит в конец придаточной части.",
        "examples": [
            {"de": "Ich bleibe zu Hause, weil ich krank bin.", "ru": "Я остаюсь дома, потому что я болею."},
            {"de": "Ich glaube, dass der Termin wichtig ist.", "ru": "Я думаю, что приём важен."},
            {"de": "Wenn ich Zeit habe, rufe ich Sie an.", "ru": "Если у меня будет время, я Вам позвоню."},
            {"de": "Ich lerne Deutsch, um in Deutschland zu arbeiten.", "ru": "Я учу немецкий, чтобы работать в Германии."},
            {"de": "Können Sie mir sagen, wann der Termin ist?", "ru": "Не могли бы Вы сказать, когда приём?"},
        ],
        "drills": [
            {
                "q": "Выберите правильный порядок после weil:",
                "options": ["weil ich bin krank", "weil ich krank bin", "weil bin ich krank"],
                "answer": 1,
                "topic": "clauses",
            },
            {
                "q": "Выберите правильный порядок после dass:",
                "options": ["dass der Termin wichtig ist", "dass ist der Termin wichtig", "dass der Termin ist wichtig"],
                "answer": 0,
                "topic": "clauses",
            },
            {
                "q": "Косвенный вопрос:",
                "options": ["wann ist der Termin", "wann der Termin ist", "wann ist der Termin ist"],
                "answer": 1,
                "topic": "indirect-questions",
            },
            {
                "q": "Цель через um ... zu:",
                "options": ["um Deutsch zu üben", "um Deutsch übe", "zu um Deutsch üben"],
                "answer": 0,
                "topic": "um-zu",
            },
        ],
        "deepTheoryRu": "Русскоговорящий ученик часто сохраняет обычный порядок слов после союза. Для немецкого это одна из самых заметных ошибок A2: союз открывает придаточное, а глагол закрывает его.",
        "russianTrap": "Ловушка: weil ich habe Zeit. По-русски «потому что у меня есть время» не меняет порядок, но немецкий требует weil ich Zeit habe.",
        "germanLogic": "Придаточное предложение работает как закрытая рамка: союз в начале, спрягаемый глагол в конце.",
        "formula": "weil/dass/wenn/ob + подлежащее + ... + Verb am Ende",
        "typicalMistakes": [
            "weil ich habe Zeit",
            "dass der Termin ist wichtig",
            "Können Sie sagen, wann ist der Termin?",
        ],
        "grammarTables": [
            table(
                "Русский союз и немецкий порядок",
                ["Русский смысл", "Союз", "Немецкий пример"],
                [
                    ["потому что", "weil", "..., weil ich krank bin."],
                    ["что", "dass", "Ich glaube, dass es wichtig ist."],
                    ["если/когда", "wenn", "Wenn ich Zeit habe, ..."],
                    ["ли", "ob", "Ich weiß nicht, ob er kommt."],
                ],
            )
        ],
        "contrastExamples": [
            {
                "ru": "Потому что у меня есть время.",
                "literal": "Не так: weil ich habe Zeit.",
                "de": "weil ich Zeit habe",
                "note": "haben уходит в конец придаточного.",
            },
            {
                "ru": "Когда приём?",
                "literal": "Не так: Können Sie sagen, wann ist der Termin?",
                "de": "Können Sie mir sagen, wann der Termin ist?",
                "note": "В косвенном вопросе глагол в конце.",
            },
        ],
    },
    {
        "id": "b1-20-russian-formal-writing",
        "level": "B1",
        "module": "Русскоговорящий мост",
        "title": "Официальное письмо без русской кальки",
        "goal": "Писать просьбы и жалобы нейтрально, коротко и по-немецки.",
        "rule": "Немецкое официальное письмо строится вокруг цели, фактов, просьбы и вежливого закрытия. Русскую эмоциональность и тяжёлую канцелярию лучше заменить ясной формулой.",
        "examples": [
            {"de": "Hiermit möchte ich einen Termin verschieben.", "ru": "Настоящим я хотел(а) бы перенести приём."},
            {"de": "Ich bitte um eine kurze Rückmeldung.", "ru": "Прошу дать короткий ответ."},
            {"de": "Könnten Sie mir die Unterlagen per E-Mail zusenden?", "ru": "Не могли бы Вы отправить мне документы по электронной почте?"},
            {"de": "Leider wurde der Termin nicht eingehalten.", "ru": "К сожалению, срок/приём не был соблюдён."},
            {"de": "Vielen Dank im Voraus.", "ru": "Заранее благодарю."},
        ],
        "drills": [
            {
                "q": "Нейтральная просьба об ответе:",
                "options": ["Ich bitte um eine kurze Rückmeldung.", "Geben Sie mir sofort Antwort.", "Ich will Antwort."],
                "answer": 0,
                "topic": "formal-writing",
            },
            {
                "q": "Вежливая просьба отправить документы:",
                "options": ["Schicken Unterlagen.", "Könnten Sie mir die Unterlagen zusenden?", "Sie müssen Unterlagen senden."],
                "answer": 1,
                "topic": "formal-writing",
            },
            {
                "q": "Формальное начало заявления:",
                "options": ["Hiermit möchte ich...", "Also ich will...", "Na gut, ich brauche..."],
                "answer": 0,
                "topic": "formal-writing",
            },
            {
                "q": "Заключительная формула:",
                "options": ["Vielen Dank im Voraus.", "Danke, пока.", "Ich warte!"],
                "answer": 0,
                "topic": "formal-writing",
            },
        ],
        "deepTheoryRu": "В русском деловом письме часто появляются длинные обороты и эмоциональные оценки. В немецком B1 лучше писать проще: факт, причина, просьба, срок, вежливая формула.",
        "russianTrap": "Ловушка: усиливать просьбу давлением. Немецкое письмо должно звучать уверенно, но не агрессивно.",
        "germanLogic": "Формальный стиль держится на стандартных блоках: Bezug, Anliegen, Bitte, Dank, Schlussformel.",
        "formula": "Anrede -> Anliegen -> Grund/Fakt -> Bitte -> Dank -> Gruß",
        "typicalMistakes": [
            "слишком эмоциональная жалоба",
            "прямой приказ вместо Könnten Sie...",
            "нет конкретной просьбы",
        ],
        "grammarTables": [
            table(
                "Письмо B1",
                ["Задача", "Немецкая формула", "Тон"],
                [
                    ["начать цель", "Hiermit möchte ich...", "нейтрально"],
                    ["попросить", "Ich bitte um...", "официально"],
                    ["смягчить", "Könnten Sie bitte...?", "вежливо"],
                    ["закрыть", "Vielen Dank im Voraus.", "стандартно"],
                ],
            )
        ],
        "contrastExamples": [
            {
                "ru": "Ответьте мне как можно скорее.",
                "literal": "Не так: Antworten Sie mir sofort.",
                "de": "Ich bitte um eine kurze Rückmeldung.",
                "note": "Просьба звучит официально и без давления.",
            },
            {
                "ru": "Пришлите документы.",
                "literal": "Не так: Schicken Sie Dokumente.",
                "de": "Könnten Sie mir die Unterlagen per E-Mail zusenden?",
                "note": "Könnten Sie смягчает просьбу.",
            },
        ],
    },
    {
        "id": "b2-35-russian-precision",
        "level": "B2",
        "module": "Русскоговорящий мост",
        "title": "B2: точность вместо русского длинного предложения",
        "goal": "Делать немецкий B2-текст ясным, точным и официальным.",
        "rule": "Русское сложное предложение часто лучше разбить или перевести немецкой структурой: Nominalstil, Passiv, zu-Infinitiv, безличное es ist zu prüfen.",
        "examples": [
            {"de": "Aus meiner Sicht ist diese Maßnahme nachvollziehbar.", "ru": "С моей точки зрения эта мера понятна/обоснована."},
            {"de": "Unter Berücksichtigung der Kosten ist die Entscheidung schwierig.", "ru": "С учётом расходов решение сложное."},
            {"de": "Nach Prüfung der Unterlagen erhalten Sie eine Rückmeldung.", "ru": "После проверки документов Вы получите ответ."},
            {"de": "Es ist zu prüfen, ob weitere Maßnahmen erforderlich sind.", "ru": "Необходимо проверить, требуются ли дополнительные меры."},
            {"de": "Die Risiken sollten sachlich erläutert werden.", "ru": "Риски следует объяснить нейтрально."},
        ],
        "drills": [
            {
                "q": "Официальнее: nachdem man die Unterlagen geprüft hat ->",
                "options": ["Nach Prüfung der Unterlagen", "Nach man prüft Unterlagen", "Nachdem Prüfung Unterlagen"],
                "answer": 0,
                "topic": "nominalstil",
            },
            {
                "q": "Безличная проверочная формула:",
                "options": ["Es ist zu prüfen, ob...", "Man muss schauen, ob...", "Es prüft, ob..."],
                "answer": 0,
                "topic": "formal-style",
            },
            {
                "q": "Нейтральная B2-оценка:",
                "options": ["Das ist total gut.", "Diese Maßnahme ist nachvollziehbar.", "Das passt irgendwie."],
                "answer": 1,
                "topic": "register",
            },
            {
                "q": "Пассив для фокуса на рисках:",
                "options": ["Die Risiken sollten erläutert werden.", "Die Risiken sollten erläutern.", "Man die Risiken erläutert."],
                "answer": 0,
                "topic": "passive",
            },
        ],
        "deepTheoryRu": "На B2 русскоговорящий часто пишет длинно: много придаточных, вводных слов и эмоциональных оценок. Немецкий B2 ценит ясную структуру, точные связки и компактные официальные формы.",
        "russianTrap": "Ловушка: переносить русскую длину предложения и получать тяжёлый немецкий текст с потерей глагола и падежа.",
        "germanLogic": "B2-текст держится на управляемых конструкциях: Nominalstil, Passiv, zu-Infinitiv, klare Konnektoren.",
        "formula": "русская длинная мысль -> немецкий блок: Nach Prüfung ... / Es ist zu prüfen ... / Die Risiken werden ...",
        "typicalMistakes": [
            "слишком длинное предложение",
            "разговорные слова в официальном тексте",
            "нет точной связки между причиной и выводом",
        ],
        "grammarTables": [
            table(
                "B2-компрессия",
                ["Русская логика", "Немецкая форма", "Эффект"],
                [
                    ["после того как проверят", "nach Prüfung der Unterlagen", "кратко и официально"],
                    ["нужно проверить", "es ist zu prüfen", "нейтрально"],
                    ["с учётом расходов", "unter Berücksichtigung der Kosten", "точный Genitiv"],
                    ["следует объяснить риски", "die Risiken sollten erläutert werden", "Passiv"],
                ],
            )
        ],
        "contrastExamples": [
            {
                "ru": "После того как документы проверят, Вам ответят.",
                "literal": "Не так: Nachdem man die Unterlagen prüft, bekommen Sie Antwort.",
                "de": "Nach Prüfung der Unterlagen erhalten Sie eine Rückmeldung.",
                "note": "Nominalstil звучит компактнее и официальнее.",
            },
            {
                "ru": "Нужно проверить, нужны ли ещё меры.",
                "literal": "Не так: Man muss schauen, ob noch Maßnahmen brauchen.",
                "de": "Es ist zu prüfen, ob weitere Maßnahmen erforderlich sind.",
                "note": "Безличная формула звучит нейтрально.",
            },
        ],
    },
]


EXISTING_LESSON_BRIDGES = {
    "a0-02-": [
        {
            "ru": "Я из России.",
            "literal": "Не так: Ich bin aus Russland.",
            "de": "Ich komme aus Russland.",
            "note": "Происхождение обычно выражается через kommen aus.",
        },
        {
            "ru": "Не могли бы Вы повторить?",
            "literal": "Не так: Wiederholen Sie!",
            "de": "Können Sie das bitte wiederholen?",
            "note": "Können Sie ... bitte звучит вежливо.",
        },
    ],
    "a0-04-": [
        {
            "ru": "Сегодня я учу немецкий.",
            "literal": "Не так: Heute ich lerne Deutsch.",
            "de": "Heute lerne ich Deutsch.",
            "note": "Heute занимает первое поле, поэтому lerne стоит вторым.",
        },
        {
            "ru": "Во Франкфурте я живу.",
            "literal": "Не так: In Frankfurt ich wohne.",
            "de": "In Frankfurt wohne ich.",
            "note": "После обстоятельства места глагол остаётся на позиции 2.",
        },
    ],
    "a0-07-nicht-kein": [
        {
            "ru": "У меня нет записи.",
            "literal": "Не так: Ich habe nicht Termin.",
            "de": "Ich habe keinen Termin.",
            "note": "kein отрицает существительное Termin.",
        },
        {
            "ru": "Я этого не понимаю.",
            "literal": "Не так: Ich verstehe kein das.",
            "de": "Ich verstehe das nicht.",
            "note": "nicht отрицает действие verstehen.",
        },
    ],
    "a0-09-artikel-merken": [
        {
            "ru": "Формуляр лежит здесь.",
            "literal": "Не так: Formular liegt hier.",
            "de": "Das Formular liegt hier.",
            "note": "Существительное учим с артиклем.",
        }
    ],
    "a1-01-praesens": [
        {
            "ru": "Ты учишь немецкий.",
            "literal": "Не так: Du lernen Deutsch.",
            "de": "Du lernst Deutsch.",
            "note": "Для du нужно окончание -st.",
        }
    ],
    "a1-04-akkusativ": [
        {
            "ru": "Я вижу врача.",
            "literal": "Не так: Ich sehe der Arzt.",
            "de": "Ich sehe den Arzt.",
            "note": "sehen требует Akkusativ.",
        }
    ],
    "a1-05-dativ": [
        {
            "ru": "Я еду на автобусе.",
            "literal": "Не так: Ich fahre mit den Bus.",
            "de": "Ich fahre mit dem Bus.",
            "note": "mit требует Dativ.",
        }
    ],
    "a1-11-trennbare-verben": [
        {
            "ru": "Я тебе позвоню.",
            "literal": "Не так: Ich anrufe dich.",
            "de": "Ich rufe dich an.",
            "note": "Приставка an уходит в конец.",
        }
    ],
    "a2-05-weil-dass-wenn-ob": [
        {
            "ru": "Потому что у меня есть время.",
            "literal": "Не так: weil ich habe Zeit.",
            "de": "weil ich Zeit habe",
            "note": "В придаточном haben стоит в конце.",
        }
    ],
    "b1-13-bewerbung": [
        {
            "ru": "Я подаю заявку на эту вакансию.",
            "literal": "Не так: Ich bewerbe diese Stelle.",
            "de": "Ich bewerbe mich um diese Stelle.",
            "note": "sich bewerben требует um + Akkusativ.",
        }
    ],
    "b2-21-fehleranalyse": [
        {
            "ru": "Нужно проверить, правильно ли выбрана форма.",
            "literal": "Не так: Man muss schauen die Form.",
            "de": "Es ist zu prüfen, ob die Form korrekt gewählt wurde.",
            "note": "B2-стиль использует нейтральную проверочную формулу.",
        }
    ],
    "b2-32-nominalstil-verben-in-nomen-umformen": [
        {
            "ru": "После проверки документов мы ответим.",
            "literal": "Не так: Nachdem wir die Unterlagen prüfen, antworten wir.",
            "de": "Nach Prüfung der Unterlagen geben wir eine Rückmeldung.",
            "note": "Nominalstil делает официальный текст короче.",
        }
    ],
}


RUSSIAN_BRIDGE_VOCAB = [
    ("A0", "Русскоговорящий мост", "ich heiße", "меня зовут", "Ich heiße Anna.", "phrase"),
    ("A0", "Русскоговорящий мост", "Ich bin dreißig Jahre alt.", "мне тридцать лет", "Ich bin dreißig Jahre alt.", "phrase"),
    ("A0", "Русскоговорящий мост", "Ich komme aus Russland.", "я из России", "Ich komme aus Russland.", "phrase"),
    ("A0", "Русскоговорящий мост", "Ich habe eine Frage.", "у меня есть вопрос", "Ich habe eine Frage.", "phrase"),
    ("A0", "Русскоговорящий мост", "Ich brauche Hilfe.", "мне нужна помощь", "Ich brauche Hilfe.", "phrase"),
    ("A0", "Русскоговорящий мост", "Sprechen Sie bitte langsam.", "говорите, пожалуйста, медленно", "Sprechen Sie bitte langsam.", "phrase"),
    ("A0", "Русскоговорящий мост", "Sagen Sie das bitte noch einmal.", "скажите это, пожалуйста, ещё раз", "Sagen Sie das bitte noch einmal.", "phrase"),
    ("A0", "Русскоговорящий мост", "der Artikel", "артикль", "Der Artikel gehört zum Wort.", "noun"),
    ("A0", "Русскоговорящий мост", "das Verb", "глагол", "Das Verb steht auf Position zwei.", "noun"),
    ("A0", "Русскоговорящий мост", "die Frage", "вопрос", "Ich habe eine Frage.", "noun"),
    ("A1", "Русскоговорящий мост", "einen Termin haben", "иметь запись/приём", "Ich habe einen Termin.", "verb-phrase"),
    ("A1", "Русскоговорящий мост", "mit dem Arzt sprechen", "говорить с врачом", "Ich spreche mit dem Arzt.", "verb-phrase"),
    ("A1", "Русскоговорящий мост", "zur Apotheke gehen", "идти в аптеку", "Ich gehe zur Apotheke.", "verb-phrase"),
    ("A1", "Русскоговорящий мост", "auf den Bus warten", "ждать автобус", "Ich warte auf den Bus.", "verb-phrase"),
    ("A1", "Русскоговорящий мост", "Mir tut der Kopf weh.", "у меня болит голова", "Mir tut der Kopf weh.", "phrase"),
    ("A1", "Русскоговорящий мост", "Ich nehme den Bus.", "я поеду на автобусе", "Ich nehme den Bus.", "phrase"),
    ("A1", "Русскоговорящий мост", "die Unterlagen mitbringen", "принести документы", "Bringen Sie bitte die Unterlagen mit.", "verb-phrase"),
    ("A1", "Русскоговорящий мост", "Können Sie mir helfen?", "Вы можете мне помочь?", "Können Sie mir bitte helfen?", "phrase"),
    ("A1", "Русскоговорящий мост", "mit Karte bezahlen", "платить картой", "Ich möchte mit Karte bezahlen.", "verb-phrase"),
    ("A1", "Русскоговорящий мост", "Ich helfe der Kollegin.", "я помогаю коллеге", "Ich helfe der Kollegin.", "phrase"),
    ("A2", "Русскоговорящий мост", "weil ich krank bin", "потому что я болею", "Ich bleibe zu Hause, weil ich krank bin.", "clause"),
    ("A2", "Русскоговорящий мост", "dass der Termin wichtig ist", "что приём важен", "Ich glaube, dass der Termin wichtig ist.", "clause"),
    ("A2", "Русскоговорящий мост", "wenn ich Zeit habe", "если у меня есть время", "Wenn ich Zeit habe, rufe ich Sie an.", "clause"),
    ("A2", "Русскоговорящий мост", "um Deutsch zu üben", "чтобы тренировать немецкий", "Ich lese laut, um Deutsch zu üben.", "infinitive"),
    ("A2", "Русскоговорящий мост", "Trotzdem komme ich pünktlich.", "несмотря на это, я приду вовремя", "Trotzdem komme ich pünktlich.", "sentence"),
    ("A2", "Русскоговорящий мост", "Deshalb rufe ich an.", "поэтому я звоню", "Deshalb rufe ich an.", "sentence"),
    ("A2", "Русскоговорящий мост", "seit drei Jahren", "уже три года", "Ich lerne seit drei Jahren Deutsch.", "phrase"),
    ("A2", "Русскоговорящий мост", "vor dem Termin", "перед приёмом", "Vor dem Termin fülle ich das Formular aus.", "phrase"),
    ("A2", "Русскоговорящий мост", "nach dem Termin", "после приёма", "Nach dem Termin gehe ich nach Hause.", "phrase"),
    ("A2", "Русскоговорящий мост", "die Bescheinigung abholen", "забрать справку", "Ich hole die Bescheinigung ab.", "verb-phrase"),
    ("B1", "Русскоговорящий мост", "Ich bitte um Rückmeldung.", "прошу дать ответ", "Ich bitte um eine kurze Rückmeldung.", "phrase"),
    ("B1", "Русскоговорящий мост", "Hiermit bewerbe ich mich.", "настоящим я подаю заявку", "Hiermit bewerbe ich mich um die Stelle.", "phrase"),
    ("B1", "Русскоговорящий мост", "aufgrund meiner Erfahrung", "на основании моего опыта", "Aufgrund meiner Erfahrung bin ich geeignet.", "phrase"),
    ("B1", "Русскоговорящий мост", "Meiner Meinung nach", "по моему мнению", "Meiner Meinung nach ist das sinnvoll.", "connector"),
    ("B1", "Русскоговорящий мост", "Einerseits ..., andererseits ...", "с одной стороны ..., с другой стороны ...", "Einerseits ist es teuer, andererseits ist es sinnvoll.", "connector"),
    ("B1", "Русскоговорящий мост", "Ein Vorteil besteht darin, dass ...", "одно преимущество состоит в том, что ...", "Ein Vorteil besteht darin, dass man flexibler ist.", "phrase"),
    ("B1", "Русскоговорящий мост", "ein Nachteil", "недостаток", "Ein Nachteil ist der hohe Preis.", "noun"),
    ("B1", "Русскоговорящий мост", "Ich stimme dem Vorschlag zu.", "я согласен с предложением", "Ich stimme dem Vorschlag zu.", "phrase"),
    ("B1", "Русскоговорящий мост", "Ich bin damit nicht einverstanden.", "я с этим не согласен", "Ich bin damit nicht einverstanden.", "phrase"),
    ("B1", "Русскоговорящий мост", "sachlich bleiben", "оставаться объективным", "In einem Konflikt sollte man sachlich bleiben.", "verb-phrase"),
    ("B1", "Русскоговорящий мост", "eine Lösung finden", "найти решение", "Wir müssen gemeinsam eine Lösung finden.", "verb-phrase"),
    ("B1", "Русскоговорящий мост", "die Frist einhalten", "соблюдать срок", "Bitte halten Sie die Frist ein.", "verb-phrase"),
    ("B2", "Русскоговорящий мост", "unter Berücksichtigung der Kosten", "с учётом расходов", "Unter Berücksichtigung der Kosten ist die Entscheidung schwierig.", "phrase"),
    ("B2", "Русскоговорящий мост", "nach Prüfung der Unterlagen", "после проверки документов", "Nach Prüfung der Unterlagen erhalten Sie eine Rückmeldung.", "phrase"),
    ("B2", "Русскоговорящий мост", "Es ist zu prüfen, ob ...", "необходимо проверить, ли ...", "Es ist zu prüfen, ob weitere Maßnahmen erforderlich sind.", "phrase"),
    ("B2", "Русскоговорящий мост", "eine Maßnahme umsetzen", "реализовать меру", "Die Maßnahme wird nächste Woche umgesetzt.", "verb-phrase"),
    ("B2", "Русскоговорящий мост", "nachvollziehbar sein", "быть понятным/обоснованным", "Die Entscheidung ist nachvollziehbar.", "adjective-phrase"),
    ("B2", "Русскоговорящий мост", "verhältnismäßig sein", "быть соразмерным", "Die Maßnahme muss verhältnismäßig sein.", "adjective-phrase"),
    ("B2", "Русскоговорящий мост", "Risiken sachlich erläutern", "объективно объяснять риски", "Die Risiken werden sachlich erläutert.", "verb-phrase"),
    ("B2", "Русскоговорящий мост", "realistische Erwartungen klären", "прояснить реалистичные ожидания", "Vor dem Eingriff sollten realistische Erwartungen geklärt werden.", "verb-phrase"),
    ("B2", "Русскоговорящий мост", "eine Einwilligung einholen", "получить согласие", "Vor der Behandlung muss eine Einwilligung eingeholt werden.", "verb-phrase"),
    ("B2", "Русскоговорящий мост", "die Kostenübernahme klären", "прояснить покрытие расходов", "Die Kostenübernahme muss vorher geklärt werden.", "verb-phrase"),
    ("B2", "Русскоговорящий мост", "die Nachsorge planen", "планировать последующее наблюдение", "Nach dem Eingriff wird die Nachsorge geplant.", "verb-phrase"),
    ("B2", "Русскоговорящий мост", "die Aufenthaltsbewilligung verlängern", "продлить вид на жительство", "Ich muss die Aufenthaltsbewilligung verlängern.", "verb-phrase"),
    ("B2", "Русскоговорящий мост", "die Franchise beachten", "учитывать франшизу", "In der Schweiz muss man die Franchise beachten.", "verb-phrase"),
    ("B2", "Русскоговорящий мост", "eine Offerte prüfen", "проверить смету/предложение", "Bitte prüfen Sie die Offerte.", "verb-phrase"),
    ("B2", "Русскоговорящий мост", "eine Stellungnahme verfassen", "составить позицию/мнение", "Ich verfasse eine sachliche Stellungnahme.", "verb-phrase"),
    ("B2", "Русскоговорящий мост", "eine Schlussfolgerung ziehen", "сделать вывод", "Daraus lässt sich eine klare Schlussfolgerung ziehen.", "verb-phrase"),
]


def max_order_by_level(data):
    result = Counter()
    for lesson in data.get("lessons", []):
        level = lesson.get("level")
        try:
            order = int(lesson.get("order") or 0)
        except Exception:
            order = 0
        if order > result[level]:
            result[level] = order
    return result


def add_lessons(data):
    existing_ids = {lesson.get("id") for lesson in data.get("lessons", [])}
    orders = max_order_by_level(data)
    added = 0
    for lesson in RUSSIAN_BRIDGE_LESSONS:
        if lesson["id"] in existing_ids:
            continue
        copy = json.loads(json.dumps(lesson, ensure_ascii=False))
        orders[copy["level"]] += 1
        copy["order"] = orders[copy["level"]]
        copy["tags"] = ["russian-transfer", "russian-speakers"]
        copy["whyForRussian"] = "Этот урок добавлен специально для русскоговорящего ученика: сначала фиксируем русскую мысль, затем выбираем естественную немецкую конструкцию."
        data.setdefault("lessons", []).append(copy)
        added += 1
    return added


def add_example(lesson, de, ru):
    examples = lesson.setdefault("examples", [])
    if any(clean(item.get("de")) == de for item in examples if isinstance(item, dict)):
        return False
    examples.append({"de": de, "ru": ru})
    return True


def add_existing_bridges(data):
    by_id = {lesson.get("id"): lesson for lesson in data.get("lessons", [])}
    bridge_count = 0
    example_count = 0
    for lesson_id, bridges in EXISTING_LESSON_BRIDGES.items():
        lesson = by_id.get(lesson_id)
        if not lesson:
            continue
        current = lesson.setdefault("contrastExamples", [])
        current_keys = {(clean(item.get("de")), clean(item.get("literal"))) for item in current if isinstance(item, dict)}
        for item in bridges:
            key = (item["de"], item["literal"])
            if key not in current_keys:
                current.append(item)
                bridge_count += 1
            if add_example(lesson, item["de"], item["ru"]):
                example_count += 1
    return {"contrast_examples_added": bridge_count, "lesson_examples_added": example_count}


def add_vocab(data):
    vocab = data.setdefault("vocab", [])
    existing_de = {clean(item.get("de")).lower() for item in vocab if isinstance(item, dict)}
    existing_ids = {item.get("id") for item in vocab if isinstance(item, dict)}
    added = 0
    skipped = 0
    for idx, (level, topic, de, ru, example, pos) in enumerate(RUSSIAN_BRIDGE_VOCAB, 1):
        if de.lower() in existing_de:
            skipped += 1
            continue
        base_id = "ru-bridge-" + re.sub(r"[^a-z0-9]+", "-", de.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")).strip("-")
        item_id = base_id[:90] or f"ru-bridge-{idx}"
        suffix = 2
        while item_id in existing_ids:
            item_id = f"{base_id[:80]}-{suffix}"
            suffix += 1
        vocab.append(
            {
                "id": item_id,
                "level": level,
                "topic": topic,
                "de": de,
                "ru": ru,
                "example": example,
                "pos": pos,
            }
        )
        existing_de.add(de.lower())
        existing_ids.add(item_id)
        added += 1
    return {"added": added, "skipped_existing_de": skipped}


CSS = r'''
/* v155-russian-bridge-css */
.contrast-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;margin-top:10px}
.contrast-card{border:1px solid var(--line);border-radius:14px;padding:12px;background:rgba(15,23,42,.36)}
.contrast-card .literal{color:#fecdd3}
.contrast-card .right{color:#bbf7d0}
.contrast-card p{margin:6px 0}
'''


BRIDGE_RENDER_HELPER = r'''
    // v155-russian-bridge-render
    function renderRussianBridge(l){
      const items = Array.isArray(l.contrastExamples) ? l.contrastExamples : [];
      if (!items.length) return '';
      return `<details open>
        <summary>Русский перенос → немецкая форма</summary>
        <div class="contrast-grid">
          ${items.map(item => `<div class="contrast-card">
            <p><b>${esc(item.ru || '')}</b></p>
            <p class="literal">${esc(item.literal || '')}</p>
            <p class="right"><b>${esc(item.de || '')}</b> ${item.de ? `<button class="speak" data-speak="${esc(item.de)}">🔊</button>` : ''}</p>
            <p class="muted">${esc(item.note || '')}</p>
          </div>`).join('')}
        </div>
      </details>`;
    }

'''


def patch_rendering(index_html):
    if "v155-russian-bridge-css" not in index_html:
        index_html = index_html.replace("</style>", CSS + "\n</style>", 1)

    if "v155-russian-bridge-render" not in index_html:
        marker = "    function renderLessonDeepTheory(l){"
        pos = index_html.find(marker)
        if pos < 0:
            raise RuntimeError("renderLessonDeepTheory not found")
        index_html = index_html[:pos] + BRIDGE_RENDER_HELPER + "\n" + index_html[pos:]

    if "${renderRussianBridge(l)}" not in index_html:
        needle = "          ${l.formula ? `<p class=\"formula-line\">${esc(l.formula)}</p>` : ''}\n          ${l.whyForRussian ? `<p class=\"muted\">${esc(l.whyForRussian)}</p>` : ''}\n        </details>"
        repl = "          ${l.formula ? `<p class=\"formula-line\">${esc(l.formula)}</p>` : ''}\n          ${l.whyForRussian ? `<p class=\"muted\">${esc(l.whyForRussian)}</p>` : ''}\n        </details>\n\n        ${renderRussianBridge(l)}"
        if needle not in index_html:
            raise RuntimeError("deep theory insertion point not found")
        index_html = index_html.replace(needle, repl, 1)

    index_html = index_html.replace("<span class=\"badge\">v15.4</span>", f"<span class=\"badge\">{VERSION}</span>")
    index_html = re.sub(r"<b>Версия v\d+\.\d+\.</b>", f"<b>Версия {VERSION}.</b>", index_html)
    index_html = index_html.replace(
        "Сначала выберите сценарий. Не нужно разбираться в длинном меню: B2-грамматика, словарь, путь с нуля и диагностика открываются сразу.",
        "Сначала выберите сценарий. В версии v15.5 немецкий объясняется через типичные русские переносы: артикли, падежи, рамку, порядок слов и официальный стиль.",
    )
    index_html = index_html.replace(
        "${infoCard('Учебный путь', `${DATA.lessons.length} урок: короткое правило → примеры → тренировка.`, 'path')}",
        "${infoCard('Учебный путь', `${DATA.lessons.length} уроков: правило → русский перенос → примеры → тренировка.`, 'path')}",
    )
    return index_html


def analyze(data):
    lessons = data.get("lessons", [])
    vocab = data.get("vocab", [])
    diagnostic = data.get("diagnostic", [])
    drills = [d for lesson in lessons for d in (lesson.get("drills") or []) if isinstance(d, dict)]
    explanations = [clean(d.get("explanation")) for d in drills]
    explanations += [clean(q.get("explanation")) for q in diagnostic if isinstance(q, dict)]
    contrast = sum(len(lesson.get("contrastExamples") or []) for lesson in lessons)
    examples = sum(len(lesson.get("examples") or []) for lesson in lessons)
    by_level = Counter(lesson.get("level") for lesson in lessons)
    vocab_by_level = Counter(item.get("level") for item in vocab)
    generic = sum(1 for item in explanations if "Здесь важно проверить форму" in item)
    mismatch = sum(
        1
        for item in explanations
        if any(marker in item for marker in ["ei читается", "sch читается", "Passiv смещает"])
    )
    return {
        "lessons": len(lessons),
        "lessonsByLevel": dict(by_level),
        "vocab": len(vocab),
        "vocabByLevel": dict(vocab_by_level),
        "diagnosticQuestions": len(diagnostic),
        "lessonExamples": examples,
        "contrastExamples": contrast,
        "drills": len(drills),
        "genericExplanations": generic,
        "mismatchMarkerExplanations": mismatch,
    }


def collect_audio_items(data):
    items = {}
    repl = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"})

    def slugify(value):
        value = html.unescape(str(value or ""))
        value = re.sub(r"\([^)]*\)", " ", value)
        value = value.translate(repl).lower()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        value = re.sub(r"-+", "-", value).strip("-")
        return value[:80]

    def add(value, source):
        value = clean(value)
        if not has_german_text(value):
            return
        slug = slugify(value[:180])
        if slug:
            items.setdefault(slug, {"text": value[:180], "sources": []})
            items[slug]["sources"].append(source)

    def walk(obj, source):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in {"de", "example"}:
                    add(value, source + "." + key)
                elif key == "options" and isinstance(value, list):
                    for i, option in enumerate(value):
                        add(option, source + f".options[{i}]")
                else:
                    walk(value, source + "." + str(key))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                walk(item, source + f"[{i}]")

    for key in ["lessons", "vocab", "diagnostic"]:
        walk(data.get(key, []), key)
    return items


def write_reports(root, before, after, explain_stats, lesson_stats, vocab_stats, audio_before, audio_after):
    data_dir = root / "data"
    docs_dir = root / "docs" / "diagnostics"
    docs_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(exist_ok=True)
    report = {
        "version": VERSION,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "diagnosticScope": [
            "content structure",
            "lesson examples",
            "Russian-speaker transfer support",
            "drill and diagnostic explanations",
            "vocabulary coverage",
            "offline MP3 slug compatibility",
        ],
        "before": before,
        "after": after,
        "weakSpotsDetected": [
            "Many explanations were generic or attached to the wrong concept, especially phonetics/passive explanations reused in unrelated drills.",
            "The course had Russian-speaker notes, but no dedicated bridge lessons that start from Russian transfer mistakes.",
            "The average lesson had about three examples; there were not enough contrastive examples for word order, articles, cases, clauses and formal writing.",
            "The vocabulary lacked a single focused topic for Russian-speaker transfer formulas across A0-B2.",
            "The full-audio generator used a 160-character slug while the app searches 80-character MP3 filenames.",
        ],
        "actionsApplied": {
            "explanations": explain_stats,
            "lessonsAdded": lesson_stats["lessons_added"],
            "existingLessonBridge": lesson_stats["existing_bridge"],
            "vocab": vocab_stats,
            "audioItemsBefore": len(audio_before),
            "audioItemsAfter": len(audio_after),
            "audioItemsDelta": len(audio_after) - len(audio_before),
        },
    }
    (data_dir / "tutor_diagnostic_v15_5.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    md = f"""# Tutor diagnostic {VERSION}

Дата: {DATE}

## Слабые места

- Объяснения в упражнениях были главным дефектом: часть ответов объяснялась чужой темой, например фонетикой вместо фразы или пассивом вместо `werden`.
- Материалов именно для русскоговорящего ученика было недостаточно как отдельного маршрута: ловушки были в теории, но не были собраны в явные мост-уроки.
- Примеров было мало для переноса с русского: до обновления {before['lessonExamples']} обычных примеров и {before['contrastExamples']} контрастных примеров.
- Словарь не имел отдельного сквозного раздела «Русскоговорящий мост».
- Генератор MP3 мог создавать длинные имена, которые приложение не ищет в offline-режиме.

## Что изменено

- Добавлены 5 мост-уроков A0-B2 для русскоговорящих.
- Добавлены контрастные блоки «русский перенос -> немецкая форма» в ключевые старые уроки.
- Добавлены новые словарные единицы в тему «Русскоговорящий мост»: {vocab_stats['added']} новых записей.
- Переписаны объяснения упражнений и диагностики: обновлено {explain_stats['updated']} пояснений.
- Генератор Neural MP3 приведён к тому же 80-символьному slug, который использует сайт.

## После обновления

- Уроков: {after['lessons']}
- Обычных примеров: {after['lessonExamples']}
- Контрастных примеров: {after['contrastExamples']}
- Словарь: {after['vocab']} записей
- Уникальных немецких аудио-элементов: {len(audio_after)}
"""
    (docs_dir / "tutor_diagnostic_v15_5.md").write_text(md, encoding="utf-8")


def update_project_files(root):
    package_path = root / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = "15.5.0"
    package["description"] = "Deutsch A0-B2 Tutor v15.5 with Russian-speaker bridge lessons, expanded examples and neural audio"
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readme = root / "README.md"
    readme_text = readme.read_text(encoding="utf-8")
    if "v15.5" not in readme_text:
        readme_text += (
            "\n\n## v15.5 Russian-speaker bridge\n\n"
            "- Added dedicated A0-B2 bridge lessons for Russian-speaking learners.\n"
            "- Expanded contrast examples: Russian transfer mistake -> correct German form.\n"
            "- Rebuilt drill explanations so answers explain the actual grammar point.\n"
            "- Added focused vocabulary topic `Русскоговорящий мост` and generated MP3 for new German items.\n"
            "- Added diagnostic report: `data/tutor_diagnostic_v15_5.json` and `docs/diagnostics/tutor_diagnostic_v15_5.md`.\n"
        )
        readme.write_text(readme_text, encoding="utf-8")

    worklog = root / "WORKLOG.md"
    worklog_text = worklog.read_text(encoding="utf-8")
    if "v15.5 Russian-speaker bridge" not in worklog_text:
        worklog_text += (
            "\n\n## v15.5 Russian-speaker bridge\n\n"
            "- Performed full tutor content diagnostics and saved reports in `data/` and `docs/diagnostics/`.\n"
            "- Added Russian-speaker bridge lessons for A0, A1, A2, B1 and B2.\n"
            "- Added contrastive examples for common Russian transfer mistakes in core lessons.\n"
            "- Added focused vocabulary for Russian-speaking learners and aligned MP3 generation with app slug rules.\n"
            "- Rewrote drill/diagnostic explanations to remove generic and mismatched explanations.\n"
        )
        worklog.write_text(worklog_text, encoding="utf-8")


def main():
    root = Path(__file__).resolve().parents[1]
    index_path = root / "index.html"
    index_html, match, data = load_index(index_path)
    before = analyze(data)
    audio_before = collect_audio_items(data)

    data["version"] = VERSION
    data["date"] = DATE
    explain_stats = fix_explanations(data)
    lessons_added = add_lessons(data)
    existing_bridge = add_existing_bridges(data)
    vocab_stats = add_vocab(data)

    after = analyze(data)
    audio_after = collect_audio_items(data)

    index_html = replace_index_data(index_html, match, data)
    index_html = patch_rendering(index_html)
    index_path.write_text(index_html, encoding="utf-8")

    write_reports(
        root,
        before,
        after,
        explain_stats,
        {"lessons_added": lessons_added, "existing_bridge": existing_bridge},
        vocab_stats,
        audio_before,
        audio_after,
    )
    update_project_files(root)

    print(
        json.dumps(
            {
                "version": VERSION,
                "before": before,
                "after": after,
                "explanations": explain_stats,
                "lessonsAdded": lessons_added,
                "existingBridge": existing_bridge,
                "vocab": vocab_stats,
                "audioItemsDelta": len(audio_after) - len(audio_before),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
