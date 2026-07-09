import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

VERSION = "v15.6"
DATE = "2026-07-09"


def table(title, headers, rows):
    return {"title": title, "headers": headers, "rows": rows}


def clean(value):
    return str(value or "").strip()


def load_app(root):
    index = root / "index.html"
    text = index.read_text(encoding="utf-8")
    match = re.search(
        r'(<script[^>]+id=["\']app-data["\'][^>]*>)(.*?)(</script>)',
        text,
        re.S,
    )
    if not match:
        raise RuntimeError("app-data not found")
    return index, text, match, json.loads(html.unescape(match.group(2)))


def save_app(index, text, match, data):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    index.write_text(text[: match.start(2)] + payload + text[match.end(2) :], encoding="utf-8")


def classify_lesson(lesson):
    blob = " ".join(
        [
            clean(lesson.get("id")),
            clean(lesson.get("title")),
            clean(lesson.get("module")),
            clean(lesson.get("rule")),
            " ".join(lesson.get("tags") or []),
        ]
    ).lower()

    def has(*words):
        return any(word in blob for word in words)

    if has("pronunciation", "произнош", "алфавит", "умлаут", "ß"):
        return "pronunciation"
    if has("word-order", "satzbau", "порядок", "v2", "verbposition", "rahmen", "рамка"):
        return "word_order"
    if has("frage", "вопрос", "ja/nein", "indirekte"):
        return "questions"
    if has("artikel", "артик", "der/die/das", "nominativ"):
        return "articles"
    if has("akkusativ", "dativ", "genitiv", "падеж", "kasus"):
        return "cases"
    if has("nicht", "kein", "negation", "отриц"):
        return "negation"
    if has("modal", "müssen", "können", "möchten", "dürfen", "sollen"):
        return "modal"
    if has("trennbare", "separable", "отделяем", "anrufen", "aufstehen"):
        return "separable"
    if has("perfekt", "präteritum", "praeteritum", "partizip", "plusquamperfekt"):
        return "past"
    if has("weil", "dass", "wenn", "obwohl", "nebensatz", "придат"):
        return "clauses"
    if has("adjektiv", "adjective", "прилагатель"):
        return "adjectives"
    if has("pronomen", "relativ", "wo-", "da-", "местоим"):
        return "pronouns"
    if has("passiv", "passive", "пассив"):
        return "passive"
    if has("konjunktiv", "косвенная речь"):
        return "konjunktiv"
    if has("präposition", "praeposition", "preposition", "предлог", "управление"):
        return "prepositions"
    if has("konnektor", "connector", "argumentation", "аргументац", "kohärenz"):
        return "connectors"
    if has("brief", "bewerbung", "beschwerde", "register", "style", "formal", "официаль"):
        return "writing"
    if has("nominal", "nominalstil"):
        return "nominal"
    if has("medizin", "patient", "aufklärung", "клиник"):
        return "medical"
    if has("schweiz", "spital", "krankenkasse"):
        return "swiss"
    if has("chirurgie", "surgery", "пластическ", "эстетическ"):
        return "surgery"
    if has("mündlich", "muendlich", "speaking", "говорение"):
        return "speaking"
    return "default"


SCHEMES = {
    "pronunciation": {
        "title": "Схема чтения",
        "steps": [
            {"label": "1", "title": "Вижу сочетание", "text": "Не читаю по-английски.", "de": "ei, ie, sch, sp, st"},
            {"label": "2", "title": "Выбираю звук", "text": "Сначала звук, потом слово.", "de": "mein, Liebe, sprechen"},
            {"label": "3", "title": "Собираю фразу", "text": "Читаю вслух короткими блоками.", "de": "Ich spreche Deutsch."},
        ],
        "bars": [
            {"label": "звук", "value": 90},
            {"label": "ударение", "value": 60},
            {"label": "фраза", "value": 70},
        ],
    },
    "word_order": {
        "title": "Граф предложения V2",
        "steps": [
            {"label": "1", "title": "Поле 1", "text": "Тема, время или место.", "de": "Heute"},
            {"label": "2", "title": "Verb 2", "text": "Спрягаемый глагол закреплён.", "de": "lerne"},
            {"label": "3", "title": "Субъект", "text": "Если первым было не ich, субъект идёт после глагола.", "de": "ich"},
            {"label": "4", "title": "Рамка", "text": "Остальное закрывает смысл.", "de": "Deutsch."},
        ],
        "bars": [
            {"label": "V2", "value": 95},
            {"label": "рамка", "value": 75},
            {"label": "акцент", "value": 55},
        ],
    },
    "articles": {
        "title": "Артикль как метка формы",
        "steps": [
            {"label": "1", "title": "Род", "text": "Учить слово вместе с der/die/das.", "de": "der Termin"},
            {"label": "2", "title": "Падеж", "text": "Роль меняет артикль.", "de": "den Termin"},
            {"label": "3", "title": "Фраза", "text": "Сразу закреплять в примере.", "de": "Ich habe einen Termin."},
        ],
        "bars": [
            {"label": "род", "value": 80},
            {"label": "падеж", "value": 90},
            {"label": "пример", "value": 70},
        ],
    },
    "cases": {
        "title": "Падежная развилка",
        "steps": [
            {"label": "1", "title": "Глагол/предлог", "text": "Сначала ищу управление.", "de": "mit, helfen, sehen"},
            {"label": "2", "title": "Падеж", "text": "Выбираю роль: Akkusativ или Dativ.", "de": "Akkusativ / Dativ"},
            {"label": "3", "title": "Артикль", "text": "Меняю der/ein по таблице.", "de": "den Arzt / dem Arzt"},
        ],
        "bars": [
            {"label": "управление", "value": 90},
            {"label": "артикль", "value": 85},
            {"label": "перевод", "value": 40},
        ],
    },
    "clauses": {
        "title": "Рамка придаточного",
        "steps": [
            {"label": "1", "title": "Союз", "text": "weil/dass/wenn открывает придаточное.", "de": "weil"},
            {"label": "2", "title": "Смысл", "text": "Подлежащее и дополнения идут внутри.", "de": "ich Zeit"},
            {"label": "3", "title": "Глагол", "text": "Спрягаемый глагол закрывает часть.", "de": "habe"},
        ],
        "bars": [
            {"label": "союз", "value": 75},
            {"label": "конец", "value": 95},
            {"label": "перенос с русского", "value": 80},
        ],
    },
    "writing": {
        "title": "Схема официального текста",
        "steps": [
            {"label": "1", "title": "Цель", "text": "Сразу назвать Anliegen.", "de": "Hiermit möchte ich..."},
            {"label": "2", "title": "Факт", "text": "Коротко и проверяемо.", "de": "Der Termin wurde nicht eingehalten."},
            {"label": "3", "title": "Просьба", "text": "Вежливо и конкретно.", "de": "Ich bitte um Rückmeldung."},
            {"label": "4", "title": "Формула", "text": "Закрыть стандартно.", "de": "Mit freundlichen Grüßen"},
        ],
        "bars": [
            {"label": "структура", "value": 90},
            {"label": "регистр", "value": 95},
            {"label": "эмоции", "value": 25},
        ],
    },
    "nominal": {
        "title": "Verbalstil -> Nominalstil",
        "steps": [
            {"label": "1", "title": "Глагол", "text": "Найти действие.", "de": "prüfen"},
            {"label": "2", "title": "Существительное", "text": "Сделать официальную форму.", "de": "die Prüfung"},
            {"label": "3", "title": "Genitiv", "text": "Добавить объект.", "de": "der Unterlagen"},
            {"label": "4", "title": "Фраза", "text": "Получить компактный B2-стиль.", "de": "Nach Prüfung der Unterlagen"},
        ],
        "bars": [
            {"label": "компактность", "value": 90},
            {"label": "официальность", "value": 85},
            {"label": "риск ошибок", "value": 60},
        ],
    },
    "default": {
        "title": "Русская мысль -> немецкая форма",
        "steps": [
            {"label": "1", "title": "Смысл", "text": "Что я хочу сказать по-русски?"},
            {"label": "2", "title": "Форма", "text": "Какой немецкий механизм нужен?", "de": "Verb, Artikel, Kasus"},
            {"label": "3", "title": "Контроль", "text": "Проверяю порядок, падеж и регистр."},
        ],
        "bars": [
            {"label": "смысл", "value": 70},
            {"label": "форма", "value": 90},
            {"label": "перевод", "value": 45},
        ],
    },
}


LEVEL_GUIDES = {
    "A0": {
        "title": "A0: карта старта для русскоговорящего",
        "focus": "Звуки, готовые фразы, V2, первые артикли.",
        "blocks": [
            "Не переводить «меня зовут» и возраст дословно.",
            "Сразу учить слово с артиклем.",
            "Каждое утверждение проверять по позиции глагола.",
            "Просьбы учить готовыми вежливыми блоками.",
        ],
        "flow": ["звук", "слово с артиклем", "готовая фраза", "мини-вопрос", "ответ вслух"],
        "bars": [
            {"label": "чтение", "value": 90},
            {"label": "шаблоны", "value": 85},
            {"label": "артикль", "value": 60},
            {"label": "V2", "value": 65},
        ],
    },
    "A1": {
        "title": "A1: карта базового предложения",
        "focus": "Глагол, артикль, Akkusativ/Dativ, бытовые сценарии.",
        "blocks": [
            "Глагол согласуется с лицом: ich lerne, du lernst.",
            "Akkusativ и Dativ выбирать по управлению.",
            "Отделяемые приставки держать в конце.",
            "Ситуации «врач, город, документы, работа» тренировать фразами.",
        ],
        "flow": ["кто действует", "глагол", "объект", "падеж", "место/время"],
        "bars": [
            {"label": "Präsens", "value": 85},
            {"label": "Akk/Dativ", "value": 75},
            {"label": "сценарии", "value": 80},
            {"label": "приставки", "value": 65},
        ],
    },
    "A2": {
        "title": "A2: карта связной речи",
        "focus": "Причина, цель, прошлое, придаточные и документы.",
        "blocks": [
            "После weil/dass/wenn/ob глагол уходит в конец.",
            "Perfekt держит рамку haben/sein + Partizip II.",
            "um ... zu объясняет цель без дословного русского «чтобы».",
            "Сообщения и звонки строить короткими блоками.",
        ],
        "flow": ["главная мысль", "связка", "придаточное", "глагол в конце", "проверка смысла"],
        "bars": [
            {"label": "Nebensatz", "value": 90},
            {"label": "Perfekt", "value": 80},
            {"label": "цель", "value": 75},
            {"label": "документы", "value": 70},
        ],
    },
    "B1": {
        "title": "B1: карта самостоятельного ответа",
        "focus": "Аргумент, письмо, мнение, управление глаголов.",
        "blocks": [
            "Ответ строить блоками: Thema -> Meinung -> Grund -> Beispiel -> Fazit.",
            "В официальном письме избегать давления и эмоций.",
            "Verben mit Präpositionen учить как цельные конструкции.",
            "Relativsatz использовать для уточнения без длинной русской кальки.",
        ],
        "flow": ["тема", "мнение", "причина", "пример", "вывод"],
        "bars": [
            {"label": "структура", "value": 85},
            {"label": "письмо", "value": 80},
            {"label": "управление", "value": 75},
            {"label": "связки", "value": 80},
        ],
    },
    "B2": {
        "title": "B2: карта качества, точности и регистра",
        "focus": "Дифференцированная аргументация, Nominalstil, Passiv, Konjunktiv, регистр и редактура.",
        "blocks": [
            "Каждый B2-текст должен иметь тезис, ограничение, аргумент, пример и вывод.",
            "Nominalstil использовать там, где нужен официальный и компактный стиль.",
            "Passiv выбирать, когда важнее процесс или результат, а не исполнитель.",
            "Konnektoren должны не просто украшать текст, а показывать причинно-следственную логику.",
            "Русскую длинную фразу лучше разбить или заменить немецкой конструкцией.",
            "Перед сдачей проверять Valenz, Kasus, Verbposition, Register, Artikel.",
        ],
        "flow": ["позиция", "аргумент", "ограничение", "пример", "B2-форма", "редактура"],
        "bars": [
            {"label": "Argumentation", "value": 95},
            {"label": "Nominalstil", "value": 90},
            {"label": "Passiv", "value": 85},
            {"label": "Register", "value": 95},
            {"label": "Fehleranalyse", "value": 90},
        ],
    },
}


B2_LESSONS = [
    {
        "id": "b2-36-argumentationsarchitektur",
        "level": "B2",
        "module": "B2 Qualität",
        "title": "Argumentationsarchitektur: These, Einwand, Fazit",
        "goal": "Строить B2-аргумент не как поток мыслей, а как проверяемую структуру.",
        "rule": "B2-аргументация требует не только мнения, но и ограничения: позиция -> причина -> пример -> Einwand -> Abwägung -> Fazit.",
        "examples": [
            {"de": "Aus meiner Sicht ist die Maßnahme sinnvoll, weil sie langfristig Kosten senkt.", "ru": "С моей точки зрения мера разумна, потому что она долгосрочно снижает расходы."},
            {"de": "Ein Gegenargument besteht darin, dass die Umsetzung zunächst teuer ist.", "ru": "Контраргумент состоит в том, что реализация сначала дорогая."},
            {"de": "Trotzdem überwiegen die Vorteile, sofern die Maßnahme sorgfältig geplant wird.", "ru": "Тем не менее преимущества преобладают, если мера тщательно планируется."},
            {"de": "Daraus lässt sich schließen, dass eine differenzierte Lösung erforderlich ist.", "ru": "Из этого можно сделать вывод, что необходимо дифференцированное решение."},
            {"de": "Diese Position lässt sich mit praktischen Beispielen begründen.", "ru": "Эту позицию можно обосновать практическими примерами."},
            {"de": "Man sollte jedoch berücksichtigen, dass nicht alle Betroffenen gleichermaßen profitieren.", "ru": "Однако следует учитывать, что не все затронутые лица получают одинаковую пользу."},
        ],
        "drills": [
            {"q": "Что делает аргумент B2-качественным?", "options": ["только мнение", "мнение + причина + ограничение", "много длинных слов"], "answer": 1, "topic": "argumentation"},
            {"q": "Как ввести контраргумент?", "options": ["Ein Gegenargument besteht darin, dass ...", "Ich bin total dagegen.", "Das ist schlecht."], "answer": 0, "topic": "argumentation"},
            {"q": "B2-вывод:", "options": ["Daraus lässt sich schließen, dass ...", "Also fertig.", "Das war alles."], "answer": 0, "topic": "argumentation"},
            {"q": "Что значит abwägen?", "options": ["взвешивать аргументы", "забывать аргументы", "переводить дословно"], "answer": 0, "topic": "argumentation"},
        ],
        "deepTheoryRu": "Русскоговорящий ученик часто пишет эссе как длинный поток: «я считаю, потому что..., ещё..., также...». На B2 это выглядит слабее, чем текст, где есть архитектура: тезис, причина, пример, контраргумент, взвешивание и вывод.",
        "russianTrap": "Ловушка: усиливать позицию эмоцией вместо логики. B2 требует показать не только «за», но и границы своей позиции.",
        "germanLogic": "Немецкий B2-текст ценит nachvollziehbar: читатель должен видеть, как из аргумента получается вывод.",
        "formula": "These -> Begründung -> Beispiel -> Einwand -> Abwägung -> Fazit",
        "typicalMistakes": ["нет Einwand", "связки не показывают логику", "вывод повторяет начало без развития"],
        "grammarTables": [
            table("Архитектура аргумента", ["Блок", "Формула", "Функция"], [
                ["These", "Aus meiner Sicht...", "позиция"],
                ["Begründung", "Der Grund dafür ist...", "причина"],
                ["Einwand", "Ein Gegenargument besteht darin, dass...", "ограничение"],
                ["Abwägung", "Trotzdem überwiegt...", "взвешивание"],
                ["Fazit", "Daraus lässt sich schließen, dass...", "вывод"],
            ])
        ],
        "contrastExamples": [
            {"ru": "Я считаю, что это хорошо, потому что это полезно.", "literal": "Слабо: Ich finde das gut, weil es gut ist.", "de": "Aus meiner Sicht ist die Maßnahme sinnvoll, weil sie langfristig konkrete Vorteile bringt.", "note": "B2 требует точной причины."},
            {"ru": "Но есть и минусы.", "literal": "Слабо: Aber es gibt Minus.", "de": "Ein Gegenargument besteht darin, dass die Umsetzung zusätzliche Ressourcen erfordert.", "note": "Контраргумент формулируется предметно."},
        ],
    },
    {
        "id": "b2-37-satzbau-informationsstruktur",
        "level": "B2",
        "module": "B2 Qualität",
        "title": "Satzbau B2: Vorfeld, Mittelfeld, Nachfeld",
        "goal": "Управлять немецким предложением через информационную структуру.",
        "rule": "На B2 важно не только правило V2, но и то, что стоит в Vorfeld: тема, контраст, причина или ограничение. Выбор первого поля меняет фокус.",
        "examples": [
            {"de": "Aus diesem Grund sollte die Entscheidung sorgfältig geprüft werden.", "ru": "По этой причине решение следует тщательно проверить."},
            {"de": "Besonders problematisch ist die fehlende Transparenz.", "ru": "Особенно проблематичным является отсутствие прозрачности."},
            {"de": "Unter diesen Umständen wäre eine kurzfristige Lösung kaum sinnvoll.", "ru": "При этих обстоятельствах краткосрочное решение едва ли было бы разумным."},
            {"de": "Nicht zu unterschätzen ist der zeitliche Aufwand.", "ru": "Не следует недооценивать временные затраты."},
            {"de": "Für russischsprachige Lernende ist vor allem die Verbposition entscheidend.", "ru": "Для русскоговорящих учеников прежде всего решающей является позиция глагола."},
        ],
        "drills": [
            {"q": "Что стоит на позиции 2 после Aus diesem Grund?", "options": ["sollte", "die Entscheidung", "geprüft"], "answer": 0, "topic": "satzbau"},
            {"q": "Что делает Vorfeld?", "options": ["задаёт фокус", "отменяет падежи", "заменяет артикль"], "answer": 0, "topic": "satzbau"},
            {"q": "B2-вариант для акцента:", "options": ["Besonders problematisch ist ...", "Es problematisch besonders ist ...", "Ist besonders problematisch ..."], "answer": 0, "topic": "satzbau"},
            {"q": "Что контролировать русскоговорящему?", "options": ["Verbposition", "только перевод", "только длину слова"], "answer": 0, "topic": "satzbau"},
        ],
        "deepTheoryRu": "Русский порядок слов гибкий и часто передаёт акцент интонацией. В немецком акцент можно делать через Vorfeld, но глагол всё равно остаётся на позиции 2. Это даёт B2-тексту управляемость.",
        "russianTrap": "Ловушка: поставить два смысловых блока перед глаголом: Aus diesem Grund die Entscheidung sollte...",
        "germanLogic": "Первое поле выбирается для фокуса, второе место закреплено за спрягаемым глаголом, конец предложения часто закрывает Partizip или Infinitiv.",
        "formula": "Vorfeld + Verb 2 + Mittelfeld + rechte Klammer",
        "typicalMistakes": ["два элемента перед глаголом", "слишком длинное Mittelfeld", "Partizip не закрывает рамку"],
        "grammarTables": [
            table("Поля немецкого предложения", ["Поле", "Что там стоит", "Пример"], [
                ["Vorfeld", "акцент/тема", "Aus diesem Grund"],
                ["linke Klammer", "спрягаемый глагол", "sollte"],
                ["Mittelfeld", "субъект, объекты, обстоятельства", "die Entscheidung sorgfältig"],
                ["rechte Klammer", "Partizip/Infinitiv", "geprüft werden"],
            ])
        ],
        "contrastExamples": [
            {"ru": "По этой причине решение следует проверить.", "literal": "Не так: Aus diesem Grund die Entscheidung sollte geprüft werden.", "de": "Aus diesem Grund sollte die Entscheidung geprüft werden.", "note": "После первого поля сразу идёт глагол."},
            {"ru": "Особенно проблематично отсутствие прозрачности.", "literal": "Не так: Besonders problematisch die Transparenz fehlt.", "de": "Besonders problematisch ist die fehlende Transparenz.", "note": "B2-стиль использует компактную именную группу."},
        ],
    },
    {
        "id": "b2-38-nominalstil-passiv-zu-infinitiv",
        "level": "B2",
        "module": "B2 Qualität",
        "title": "B2-Werkzeuge: Nominalstil, Passiv, zu-Infinitiv",
        "goal": "Выбирать B2-конструкцию под задачу, а не усложнять текст случайно.",
        "rule": "Nominalstil делает текст официальнее, Passiv меняет фокус на процесс, zu-Infinitiv компактно выражает необходимость, цель или оценку.",
        "examples": [
            {"de": "Nach Prüfung der Unterlagen wird eine Entscheidung getroffen.", "ru": "После проверки документов будет принято решение."},
            {"de": "Die Risiken müssen vor der Behandlung erläutert werden.", "ru": "Риски должны быть объяснены до лечения."},
            {"de": "Es ist zu beachten, dass die Kosten variieren können.", "ru": "Следует учитывать, что расходы могут различаться."},
            {"de": "Zur Klärung der offenen Fragen ist ein Beratungsgespräch erforderlich.", "ru": "Для прояснения открытых вопросов необходима консультация."},
            {"de": "Ohne die Alternativen zu prüfen, sollte keine Entscheidung getroffen werden.", "ru": "Без проверки альтернатив не следует принимать решение."},
        ],
        "drills": [
            {"q": "Официальнее: nachdem man die Unterlagen geprüft hat", "options": ["Nach Prüfung der Unterlagen", "Nach man prüft die Unterlagen", "Nach prüfen Unterlagen"], "answer": 0, "topic": "nominalstil"},
            {"q": "Passiv:", "options": ["Die Risiken werden erläutert.", "Die Risiken erläutern.", "Die Risiken wird erläutern."], "answer": 0, "topic": "passive"},
            {"q": "zu-Infinitiv формула:", "options": ["Es ist zu beachten, dass ...", "Es ist beachten, dass ...", "Es zu ist beachten ..."], "answer": 0, "topic": "zu-infinitive"},
            {"q": "Когда использовать Nominalstil?", "options": ["для официальной компактности", "чтобы скрыть артикли", "в каждом предложении без причины"], "answer": 0, "topic": "nominalstil"},
        ],
        "deepTheoryRu": "Для русскоговорящего B2 опасность в том, что «сложнее» кажется «лучше». На самом деле B2-качество — это выбор инструмента: где нужен Nominalstil, где Passiv, где проще оставить Verbalstil.",
        "russianTrap": "Ловушка: превращать каждую русскую фразу в тяжёлую немецкую конструкцию и терять управление падежами.",
        "germanLogic": "B2-инструмент выбирается по функции: компактность, фокус, нейтральность, официальность.",
        "formula": "Funktion -> Werkzeug: offiziell = Nominalstil; Prozess = Passiv; Bewertung = zu-Infinitiv",
        "typicalMistakes": ["Nominalstil без Genitiv", "Passiv без Partizip II", "zu-Infinitiv без zu"],
        "grammarTables": [
            table("B2-инструменты", ["Задача", "Конструкция", "Пример"], [
                ["официальная краткость", "Nominalstil", "Nach Prüfung der Unterlagen"],
                ["процесс важнее исполнителя", "Passiv", "Die Risiken werden erläutert."],
                ["оценка/необходимость", "sein + zu + Infinitiv", "Es ist zu beachten."],
                ["цель", "zur + Nomen / um ... zu", "Zur Klärung / um zu klären"],
            ])
        ],
        "contrastExamples": [
            {"ru": "После того как проверят документы...", "literal": "Слабее: Nachdem man die Unterlagen geprüft hat...", "de": "Nach Prüfung der Unterlagen...", "note": "Официальный текст часто компактнее."},
            {"ru": "Нужно учитывать расходы.", "literal": "Не так: Man muss die Kosten beachten werden.", "de": "Es ist zu beachten, dass die Kosten variieren können.", "note": "sein + zu + Infinitiv даёт нейтральную формулу."},
        ],
    },
    {
        "id": "b2-39-register-redaktion",
        "level": "B2",
        "module": "B2 Qualität",
        "title": "Register und Redaktion: как звучать на B2",
        "goal": "Редактировать текст так, чтобы он звучал нейтрально, точно и естественно.",
        "rule": "B2-регистр — это не набор сложных слов. Это точность, дистанция, умеренность оценки и отсутствие русской эмоциональной кальки.",
        "examples": [
            {"de": "Die Situation ist problematisch, jedoch nicht unlösbar.", "ru": "Ситуация проблематична, однако не безвыходна."},
            {"de": "Diese Einschätzung erscheint nachvollziehbar.", "ru": "Эта оценка кажется обоснованной."},
            {"de": "Die Kritik ist teilweise berechtigt.", "ru": "Критика частично обоснована."},
            {"de": "Eine pauschale Bewertung wäre unangemessen.", "ru": "Обобщающая оценка была бы неуместной."},
            {"de": "Der Text sollte sprachlich präziser formuliert werden.", "ru": "Текст следует сформулировать языково точнее."},
        ],
        "drills": [
            {"q": "Нейтральнее:", "options": ["Die Situation ist problematisch.", "Das ist kompletter Unsinn.", "Alles ist schrecklich."], "answer": 0, "topic": "register"},
            {"q": "B2-оценка без категоричности:", "options": ["teilweise berechtigt", "immer falsch", "total super"], "answer": 0, "topic": "register"},
            {"q": "Что убрать при редактуре?", "options": ["эмоциональные усилители", "точные связки", "артикли"], "answer": 0, "topic": "redaktion"},
            {"q": "Как сказать «обобщающая оценка»?", "options": ["eine pauschale Bewertung", "eine totale Meinung", "ein ganzes Denken"], "answer": 0, "topic": "register"},
        ],
        "deepTheoryRu": "Русский текст часто допускает сильные оценки: «это ужасно», «совершенно неправильно». В немецком B2 лучше звучит умеренная точность: teilweise, tendenziell, nachvollziehbar, problematisch, jedoch.",
        "russianTrap": "Ловушка: думать, что B2 — это максимально длинно и резко. На экзамене и в рабочем письме ценится ясная умеренность.",
        "germanLogic": "Регистр управляет дистанцией: разговорное, нейтральное, официальное. B2 выбирает форму под ситуацию.",
        "formula": "stark emotional -> neutral präzise: total falsch -> teilweise problematisch",
        "typicalMistakes": ["разговорные слова в официальном тексте", "категоричность без аргумента", "слишком длинные русские вводные конструкции"],
        "grammarTables": [
            table("Редактура регистра", ["Слабо", "B2-вариант", "Почему лучше"], [
                ["total schlecht", "problematisch", "нейтральнее"],
                ["immer falsch", "teilweise nicht überzeugend", "точнее"],
                ["ich will", "ich bitte um", "официальнее"],
                ["man muss schauen", "es ist zu prüfen", "письменный стиль"],
            ])
        ],
        "contrastExamples": [
            {"ru": "Это полный бред.", "literal": "Не так: Das ist kompletter Unsinn.", "de": "Diese Einschätzung ist aus meiner Sicht nicht überzeugend.", "note": "B2 критикует предметно."},
            {"ru": "Нужно посмотреть, правильно ли это.", "literal": "Слабее: Man muss schauen, ob das richtig ist.", "de": "Es ist zu prüfen, ob diese Einschätzung zutrifft.", "note": "Нейтральная проверочная формула."},
        ],
    },
    {
        "id": "b2-40-fehlerdiagnose-russischsprachige",
        "level": "B2",
        "module": "B2 Qualität",
        "title": "Fehlerdiagnose B2 для русскоговорящих",
        "goal": "Проверять B2-текст по списку ошибок, типичных для русскоговорящих.",
        "rule": "Перед сдачей текста проверяйте пять зон: Verbposition, Valenz, Kasus, Artikel, Register. Это быстрее и надёжнее, чем перечитывать только по смыслу.",
        "examples": [
            {"de": "Ich interessiere mich für diese Stelle.", "ru": "Я интересуюсь этой вакансией."},
            {"de": "Ich verfüge über mehrjährige Erfahrung.", "ru": "У меня есть многолетний опыт."},
            {"de": "Die Entscheidung hängt von mehreren Faktoren ab.", "ru": "Решение зависит от нескольких факторов."},
            {"de": "Aus diesem Grund halte ich den Vorschlag für sinnvoll.", "ru": "По этой причине я считаю предложение разумным."},
            {"de": "Der Antrag wurde nach Prüfung der Unterlagen abgelehnt.", "ru": "Заявление было отклонено после проверки документов."},
        ],
        "drills": [
            {"q": "sich interessieren требует:", "options": ["für + Akkusativ", "mit + Dativ", "an + Genitiv"], "answer": 0, "topic": "valenz"},
            {"q": "verfügen требует:", "options": ["über + Akkusativ", "zu + Dativ", "wegen + Genitiv"], "answer": 0, "topic": "valenz"},
            {"q": "hängen ... ab требует:", "options": ["von + Dativ", "für + Akkusativ", "durch + Akkusativ"], "answer": 0, "topic": "valenz"},
            {"q": "Что проверять перед сдачей B2-текста?", "options": ["Verbposition, Valenz, Kasus, Artikel, Register", "только длину текста", "только перевод слов"], "answer": 0, "topic": "selfcheck"},
        ],
        "deepTheoryRu": "На B2 русскоговорящий часто понимает тему, но теряет качество из-за повторяющихся технических ошибок. Нужен не общий перечит, а диагностика по зонам риска.",
        "russianTrap": "Ловушка: если мысль понятна по-русски, считать немецкую форму готовой. На B2 оценивается форма: управление, падежи, порядок, регистр.",
        "germanLogic": "Качество создаёт контрольная процедура: найти глаголы управления, проверить падежи, затем отредактировать регистр.",
        "formula": "Verbposition -> Valenz -> Kasus -> Artikel -> Register -> Schlusscheck",
        "typicalMistakes": ["interessieren diese Stelle", "verfügen Erfahrung", "Aus diesem Grund die Entscheidung ist...", "разговорный регистр в письменной работе"],
        "grammarTables": [
            table("B2-чеклист", ["Зона", "Вопрос", "Пример"], [
                ["Verbposition", "где спрягаемый глагол?", "Aus diesem Grund halte ich..."],
                ["Valenz", "какой предлог требует глагол?", "sich interessieren für"],
                ["Kasus", "какой падеж после предлога?", "für + Akkusativ"],
                ["Artikel", "род и число проверены?", "der Antrag"],
                ["Register", "стиль подходит?", "es ist zu prüfen"],
            ])
        ],
        "contrastExamples": [
            {"ru": "Я интересуюсь этой вакансией.", "literal": "Не так: Ich interessiere diese Stelle.", "de": "Ich interessiere mich für diese Stelle.", "note": "sich interessieren für + Akkusativ."},
            {"ru": "У меня есть опыт.", "literal": "Слабее: Ich habe Erfahrung.", "de": "Ich verfüge über mehrjährige Erfahrung.", "note": "Для B2-письма verfüge über звучит сильнее."},
        ],
    },
]


B2_VOCAB = [
    ("eine differenzierte Position vertreten", "представлять дифференцированную позицию", "In der Diskussion sollte man eine differenzierte Position vertreten."),
    ("ein Argument sorgfältig abwägen", "тщательно взвешивать аргумент", "Man sollte jedes Argument sorgfältig abwägen."),
    ("ein Gegenargument einräumen", "признавать контраргумент", "Ein Gegenargument sollte man fair einräumen."),
    ("die Vorteile überwiegen", "преимущества преобладают", "In diesem Fall überwiegen die Vorteile."),
    ("die Nachteile berücksichtigen", "учитывать недостатки", "Die Nachteile müssen ebenfalls berücksichtigt werden."),
    ("eine pauschale Bewertung vermeiden", "избегать обобщающей оценки", "Eine pauschale Bewertung sollte vermieden werden."),
    ("eine Schlussfolgerung ziehen", "делать вывод", "Daraus lässt sich eine Schlussfolgerung ziehen."),
    ("sprachlich präzise formulieren", "формулировать языково точно", "Der Text sollte sprachlich präzise formuliert werden."),
    ("inhaltlich nachvollziehbar sein", "быть содержательно понятным/обоснованным", "Die Begründung muss inhaltlich nachvollziehbar sein."),
    ("unter diesen Umständen", "при этих обстоятельствах", "Unter diesen Umständen wäre eine andere Lösung sinnvoll."),
    ("aus diesem Grund", "по этой причине", "Aus diesem Grund sollte die Entscheidung geprüft werden."),
    ("nicht zu unterschätzen sein", "не следует недооценивать", "Nicht zu unterschätzen ist der zeitliche Aufwand."),
    ("zur Klärung offener Fragen", "для прояснения открытых вопросов", "Zur Klärung offener Fragen ist ein Gespräch erforderlich."),
    ("nach sorgfältiger Prüfung", "после тщательной проверки", "Nach sorgfältiger Prüfung wurde der Antrag bewilligt."),
    ("eine Maßnahme kritisch hinterfragen", "критически рассматривать меру", "Diese Maßnahme sollte kritisch hinterfragt werden."),
    ("eine Einschätzung zutreffen", "оценка соответствует действительности", "Es ist zu prüfen, ob diese Einschätzung zutrifft."),
    ("eine Lösung erarbeiten", "разработать решение", "Gemeinsam kann eine tragfähige Lösung erarbeitet werden."),
    ("tragfähig sein", "быть устойчивым/работоспособным", "Die Lösung muss langfristig tragfähig sein."),
    ("sich auf mehrere Faktoren stützen", "опираться на несколько факторов", "Die Entscheidung stützt sich auf mehrere Faktoren."),
    ("von mehreren Faktoren abhängen", "зависеть от нескольких факторов", "Das Ergebnis hängt von mehreren Faktoren ab."),
    ("über Erfahrung verfügen", "располагать опытом", "Ich verfüge über mehrjährige Erfahrung."),
    ("sich für eine Stelle interessieren", "интересоваться вакансией", "Ich interessiere mich für diese Stelle."),
    ("für sinnvoll halten", "считать разумным", "Ich halte den Vorschlag für sinnvoll."),
    ("teilweise berechtigt sein", "быть частично обоснованным", "Die Kritik ist teilweise berechtigt."),
    ("nicht überzeugend wirken", "выглядеть неубедительным", "Diese Begründung wirkt nicht überzeugend."),
    ("eine Einschränkung machen", "сделать оговорку", "An dieser Stelle muss man eine Einschränkung machen."),
    ("sofern dies möglich ist", "если это возможно", "Sofern dies möglich ist, sollte man die Maßnahme umsetzen."),
    ("jedoch nicht unlösbar sein", "однако не быть безвыходным", "Die Situation ist problematisch, jedoch nicht unlösbar."),
    ("eine transparente Begründung liefern", "дать прозрачное обоснование", "Die Verwaltung sollte eine transparente Begründung liefern."),
    ("den roten Faden sichern", "сохранять красную нить текста", "Konnektoren sichern den roten Faden."),
]


def ensure_visual_schemes(data):
    added = 0
    kind_counts = Counter()
    for lesson in data.get("lessons", []):
        if lesson.get("visualSchemes"):
            continue
        kind = classify_lesson(lesson)
        scheme = SCHEMES.get(kind) or SCHEMES["default"]
        lesson["visualSchemes"] = [scheme]
        kind_counts[kind] += 1
        added += 1
    return {"added": added, "byKind": dict(kind_counts)}


def ensure_level_guides(data):
    data["levelGuides"] = LEVEL_GUIDES
    return len(LEVEL_GUIDES)


def next_order(data, level):
    orders = [int(l.get("order") or 0) for l in data.get("lessons", []) if l.get("level") == level]
    return max(orders or [0]) + 1


def add_b2_lessons(data):
    existing = {lesson.get("id") for lesson in data.get("lessons", [])}
    added = 0
    for lesson in B2_LESSONS:
        if lesson["id"] in existing:
            continue
        item = json.loads(json.dumps(lesson, ensure_ascii=False))
        item["order"] = next_order(data, "B2")
        item["tags"] = ["b2-quality", "russian-speakers", "writing", "argumentation"]
        item["whyForRussian"] = "B2-блок усилен специально для русскоговорящего ученика: сначала убираем русскую кальку, затем выбираем точную немецкую конструкцию и редактируем регистр."
        item["visualSchemes"] = [
            {
                "title": "B2-процесс качества",
                "steps": [
                    {"label": "1", "title": "Смысл", "text": "Формулирую мысль без дословного перевода."},
                    {"label": "2", "title": "Структура", "text": "Выбираю B2-блок.", "de": item["formula"]},
                    {"label": "3", "title": "Форма", "text": "Проверяю Verbposition, Kasus, Valenz."},
                    {"label": "4", "title": "Регистр", "text": "Редактирую под официальную или экзаменационную ситуацию."},
                ],
                "bars": [
                    {"label": "структура", "value": 95},
                    {"label": "точность", "value": 90},
                    {"label": "регистр", "value": 90},
                ],
            }
        ]
        data.setdefault("lessons", []).append(item)
        existing.add(item["id"])
        added += 1
    return added


def add_b2_vocab(data):
    vocab = data.setdefault("vocab", [])
    existing = {clean(item.get("de")).lower() for item in vocab if isinstance(item, dict)}
    ids = {item.get("id") for item in vocab if isinstance(item, dict)}
    added = 0
    for de, ru, example in B2_VOCAB:
        if de.lower() in existing:
            continue
        base = "b2-quality-" + re.sub(
            r"[^a-z0-9]+",
            "-",
            de.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"),
        ).strip("-")
        item_id = base[:100]
        n = 2
        while item_id in ids:
            item_id = f"{base[:92]}-{n}"
            n += 1
        vocab.append(
            {
                "id": item_id,
                "level": "B2",
                "topic": "B2 Qualität und Stil",
                "de": de,
                "ru": ru,
                "example": example,
                "pos": "phrase",
            }
        )
        ids.add(item_id)
        existing.add(de.lower())
        added += 1
    return added


CSS = r'''
/* v156-systematic-theory-css */
.level-guide{border:1px solid var(--line);border-radius:16px;background:rgba(96,165,250,.08);padding:14px;margin:14px 0;display:grid;gap:12px}
.guide-columns{display:grid;grid-template-columns:1.1fr .9fr;gap:12px}
.guide-flow,.scheme-flow{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
.guide-step,.scheme-step{border:1px solid var(--line);border-radius:14px;background:rgba(2,6,23,.34);padding:10px}
.step-label{display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:26px;border-radius:999px;background:rgba(52,211,153,.18);border:1px solid rgba(52,211,153,.45);font-weight:800;margin-bottom:6px}
.guide-bars,.scheme-bars{display:grid;gap:8px}
.bar-line{display:grid;grid-template-columns:minmax(100px,160px) 1fr 44px;gap:8px;align-items:center}
.bar-track{height:10px;border-radius:999px;background:rgba(255,255,255,.08);overflow:hidden;border:1px solid var(--line)}
.bar-fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent-2));border-radius:999px}
.scheme-panel{border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.035);padding:12px;margin-top:10px}
.scheme-panel h4{margin:0 0 8px}
@media (max-width: 780px){.guide-columns{grid-template-columns:1fr}.bar-line{grid-template-columns:96px 1fr 38px}}
'''


HELPERS = r'''
    // v156-systematic-theory-render
    function renderBarsV156(bars){
      if (!Array.isArray(bars) || !bars.length) return '';
      return `<div class="scheme-bars">${bars.map(b => {
        const value = Math.max(0, Math.min(100, Number(b.value) || 0));
        return `<div class="bar-line"><span>${esc(b.label || '')}</span><span class="bar-track"><span class="bar-fill" style="width:${value}%"></span></span><span>${value}%</span></div>`;
      }).join('')}</div>`;
    }

    function renderFlowV156(steps, cls='scheme-flow'){
      if (!Array.isArray(steps) || !steps.length) return '';
      return `<div class="${cls}">${steps.map((s,i) => {
        if (typeof s === 'string') return `<div class="scheme-step"><span class="step-label">${i+1}</span><p>${esc(s)}</p></div>`;
        return `<div class="scheme-step">
          <span class="step-label">${esc(s.label || String(i+1))}</span>
          <h4>${esc(s.title || '')}</h4>
          <p>${esc(s.text || '')}</p>
          ${s.de ? `<p class="de"><b>${esc(s.de)}</b> <button class="speak" data-speak="${esc(s.de)}">🔊</button></p>` : ''}
        </div>`;
      }).join('')}</div>`;
    }

    function renderVisualSchemes(l){
      const schemes = Array.isArray(l.visualSchemes) ? l.visualSchemes : [];
      if (!schemes.length) return '';
      return `<details open>
        <summary>Схемы и мини-графики</summary>
        ${schemes.map(s => `<div class="scheme-panel">
          <h4>${esc(s.title || 'Схема')}</h4>
          ${s.subtitle ? `<p class="muted">${esc(s.subtitle)}</p>` : ''}
          ${renderFlowV156(s.steps)}
          ${renderBarsV156(s.bars)}
        </div>`).join('')}
      </details>`;
    }

    function renderLevelGuide(level){
      const guide = DATA.levelGuides && DATA.levelGuides[level];
      if (!guide) return '';
      return `<div class="level-guide">
        <div>
          <h3>${esc(guide.title || level)}</h3>
          <p class="muted">${esc(guide.focus || '')}</p>
        </div>
        <div class="guide-columns">
          <div>
            <h4>Что должно быть сильным</h4>
            <ul class="mistake-list">${(guide.blocks || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul>
          </div>
          <div>
            <h4>Граф качества уровня</h4>
            ${renderBarsV156(guide.bars)}
          </div>
        </div>
        <div>
          <h4>Маршрут мышления</h4>
          ${renderFlowV156(guide.flow || [], 'guide-flow')}
        </div>
      </div>`;
    }

'''


def patch_rendering(index):
    text = index.read_text(encoding="utf-8")
    if "v156-systematic-theory-css" not in text:
        text = text.replace("</style>", CSS + "\n</style>", 1)
    if "v156-systematic-theory-render" not in text:
        marker = "    function renderGrammarTableV153(t){"
        pos = text.find(marker)
        if pos < 0:
            raise RuntimeError("render helper insertion marker not found")
        text = text[:pos] + HELPERS + "\n" + text[pos:]
    text = text.replace(
        "          ${levelTabs(level,'path')}\n          <div class=\"toolbar\">",
        "          ${levelTabs(level,'path')}\n          ${renderLevelGuide(level)}\n          <div class=\"toolbar\">",
        1,
    )
    text = text.replace(
        "          ${levelTabs(level,'grammar')}\n          <div class=\"grid\">",
        "          ${levelTabs(level,'grammar')}\n          ${level !== 'Alle' ? renderLevelGuide(level) : ''}\n          <div class=\"grid\">",
        1,
    )
    text = text.replace(
        "      if (!l.deepTheoryRu && !l.russianTrap && !l.germanLogic && !l.formula && !tables.length && !mistakes.length) return '';",
        "      const schemes = Array.isArray(l.visualSchemes) ? l.visualSchemes : [];\n      if (!l.deepTheoryRu && !l.russianTrap && !l.germanLogic && !l.formula && !tables.length && !mistakes.length && !schemes.length) return '';",
        1,
    )
    text = text.replace(
        "        ${renderRussianBridge(l)}\n\n        ${tables.length ? `<details open>",
        "        ${renderRussianBridge(l)}\n\n        ${renderVisualSchemes(l)}\n\n        ${tables.length ? `<details open>",
        1,
    )
    text = text.replace("<span class=\"badge\">v15.5</span>", f"<span class=\"badge\">{VERSION}</span>")
    text = re.sub(r"<b>Версия v\d+\.\d+\.</b>", f"<b>Версия {VERSION}.</b>", text)
    text = text.replace(
        "В версии v15.5 немецкий объясняется через типичные русские переносы: артикли, падежи, рамку, порядок слов и официальный стиль.",
        "В версии v15.6 добавлены карты уровней, схемы внутри уроков и усиленный B2: аргументация, Nominalstil, Passiv, регистр и редактура.",
    )
    text = text.replace(
        "Прямой вход без маршрута, аудио-панелей и профессиональных блоков.",
        "Прямой вход в усиленный B2: аргументация, точный Satzbau, Nominalstil, Passiv, регистр и самопроверка.",
    )
    index.write_text(text, encoding="utf-8")


def collect_stats(data):
    lessons = data.get("lessons", [])
    return {
        "lessons": len(lessons),
        "byLevel": dict(Counter(l.get("level") for l in lessons)),
        "vocab": len(data.get("vocab", [])),
        "visualSchemes": sum(len(l.get("visualSchemes") or []) for l in lessons),
        "b2Lessons": sum(1 for l in lessons if l.get("level") == "B2"),
        "b2Vocab": sum(1 for v in data.get("vocab", []) if v.get("level") == "B2"),
        "levelGuides": len(data.get("levelGuides") or {}),
    }


def write_reports(root, before, after, scheme_stats, b2_lessons, b2_vocab):
    data_dir = root / "data"
    docs_dir = root / "docs" / "diagnostics"
    data_dir.mkdir(exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "version": VERSION,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "purpose": "Systematic level quality pass: level maps, lesson schemes, B2 expansion and Russian-speaker theory.",
        "before": before,
        "after": after,
        "actions": {
            "levelGuides": len(LEVEL_GUIDES),
            "lessonVisualSchemes": scheme_stats,
            "b2LessonsAdded": b2_lessons,
            "b2VocabularyAdded": b2_vocab,
        },
        "b2QualityFocus": [
            "argumentation architecture",
            "Vorfeld/Mittelfeld/Nachfeld and information structure",
            "Nominalstil, Passiv and zu-Infinitiv as deliberate tools",
            "register and redaction",
            "Russian-speaker B2 error diagnosis: Verbposition, Valenz, Kasus, Artikel, Register",
        ],
    }
    (data_dir / "systematic_quality_v15_6.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md = f"""# Systematic quality pass {VERSION}

Дата: {DATE}

## Что добрали системно

- Для A0, A1, A2, B1 и B2 добавлены карты уровня: фокус, маршрут мышления и граф качества.
- Для уроков добавлены визуальные схемы и мини-графики, чтобы теория не была только текстом.
- B2 расширен отдельными уроками по аргументации, Satzbau, Nominalstil/Passiv/zu-Infinitiv, регистру и диагностике ошибок.
- Добавлен словарь `B2 Qualität und Stil`: {b2_vocab} новых B2-формул и выражений.

## Контроль качества B2

B2 теперь проверяется по пяти зонам: `Argumentation`, `Satzbau`, `Nominalstil/Passiv`, `Register`, `Fehlerdiagnose`.

До: {before['b2Lessons']} B2-уроков, после: {after['b2Lessons']} B2-уроков.
Всего схем в уроках: {after['visualSchemes']}.
"""
    (docs_dir / "systematic_quality_v15_6.md").write_text(md, encoding="utf-8")


def update_project_files(root):
    package_path = root / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = "15.6.0"
    package["description"] = "Deutsch A0-B2 Tutor v15.6 with systematic level maps, visual schemes and expanded B2 theory"
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readme = root / "README.md"
    readme_text = readme.read_text(encoding="utf-8")
    if "v15.6 systematic quality" not in readme_text:
        readme_text += (
            "\n\n## v15.6 systematic quality\n\n"
            "- Added level maps for A0, A1, A2, B1 and B2.\n"
            "- Added visual schemes and mini quality graphs inside lessons.\n"
            "- Expanded B2 with dedicated quality lessons: argumentation, Satzbau, Nominalstil/Passiv/zu-Infinitiv, register and error diagnosis.\n"
            "- Added B2 vocabulary topic `B2 Qualität und Stil` and generated MP3 for new German material.\n"
            "- Added diagnostic report: `data/systematic_quality_v15_6.json` and `docs/diagnostics/systematic_quality_v15_6.md`.\n"
        )
        readme.write_text(readme_text, encoding="utf-8")

    worklog = root / "WORKLOG.md"
    worklog_text = worklog.read_text(encoding="utf-8")
    if "v15.6 systematic quality" not in worklog_text:
        worklog_text += (
            "\n\n## v15.6 systematic quality\n\n"
            "- Added systematic level maps for every level so no level lags behind structurally.\n"
            "- Added visual theory schemes and quality graphs to lessons.\n"
            "- Expanded B2 quality with five new lessons and focused B2 style vocabulary.\n"
            "- Added reports for the systematic quality pass.\n"
        )
        worklog.write_text(worklog_text, encoding="utf-8")


def main():
    root = Path(__file__).resolve().parents[1]
    index, text, match, data = load_app(root)
    before = collect_stats(data)
    data["version"] = VERSION
    data["date"] = DATE
    ensure_level_guides(data)
    b2_lessons = add_b2_lessons(data)
    scheme_stats = ensure_visual_schemes(data)
    b2_vocab = add_b2_vocab(data)
    after = collect_stats(data)
    save_app(index, text, match, data)
    patch_rendering(index)
    write_reports(root, before, after, scheme_stats, b2_lessons, b2_vocab)
    update_project_files(root)
    print(json.dumps({
        "version": VERSION,
        "before": before,
        "after": after,
        "schemes": scheme_stats,
        "b2LessonsAdded": b2_lessons,
        "b2VocabAdded": b2_vocab,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
