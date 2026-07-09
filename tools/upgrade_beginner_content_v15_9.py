import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


VERSION = "v15.9"
DATE = "2026-07-09"


GERMAN_REPL = str.maketrans({
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "ß": "ss",
    "Ä": "ae",
    "Ö": "oe",
    "Ü": "ue",
})


def slug(value):
    value = str(value or "").translate(GERMAN_REPL).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return re.sub(r"-+", "-", value)[:90] or "item"


def load_app(root):
    index = root / "index.html"
    text = index.read_text(encoding="utf-8")
    match = re.search(r'(<script type="application/json" id="app-data">)(.*?)(</script>)', text, re.S)
    if not match:
        raise RuntimeError("app-data script not found")
    data = json.loads(html.unescape(match.group(2)))
    return index, text, match, data


def save_app(index, text, match, data):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    text = text[:match.start(2)] + payload + text[match.end(2):]
    text = re.sub(r"<b>Версия v\d+\.\d+\.</b>", f"<b>Версия {VERSION}.</b>", text)
    text = text.replace('<span class="badge">v15.8</span>', f'<span class="badge">{VERSION}</span>')
    text = text.replace(
        "В версии v15.8 добавлен учебный центр: отдельные профили, B2-фокус, быстрое пропускание известного материала и продолжение с последнего места.",
        "В версии v15.9 добавлены базовые A0/A1 слова, бытовые уроки, повторения и больше проверок для полного старта с нуля.",
    )
    index.write_text(text, encoding="utf-8")


def existing_ids(items):
    return {x.get("id") for x in items if isinstance(x, dict)}


def existing_de(items):
    return {str(x.get("de", "")).strip().lower() for x in items if isinstance(x, dict)}


def add_vocab_items(data):
    vocab = data.setdefault("vocab", [])
    ids = existing_ids(vocab)
    de_seen = existing_de(vocab)

    rows = [
        # A0: home and objects
        ("A0", "Дом и вещи", "der Tisch", "стол", "Der Tisch ist hier.", "noun"),
        ("A0", "Дом и вещи", "der Stuhl", "стул", "Der Stuhl ist bequem.", "noun"),
        ("A0", "Дом и вещи", "das Bett", "кровать", "Das Bett ist groß.", "noun"),
        ("A0", "Дом и вещи", "die Tür", "дверь", "Die Tür ist offen.", "noun"),
        ("A0", "Дом и вещи", "das Fenster", "окно", "Das Fenster ist zu.", "noun"),
        ("A0", "Дом и вещи", "die Lampe", "лампа", "Die Lampe ist hell.", "noun"),
        ("A0", "Дом и вещи", "der Schlüssel", "ключ", "Der Schlüssel ist in der Tasche.", "noun"),
        ("A0", "Дом и вещи", "die Tasche", "сумка", "Die Tasche ist schwer.", "noun"),
        ("A0", "Дом и вещи", "das Handy", "телефон", "Mein Handy ist neu.", "noun"),
        ("A0", "Дом и вещи", "das Buch", "книга", "Das Buch liegt auf dem Tisch.", "noun"),
        ("A0", "Дом и вещи", "der Kugelschreiber", "ручка", "Der Kugelschreiber schreibt gut.", "noun"),
        ("A0", "Дом и вещи", "das Papier", "бумага", "Ich brauche Papier.", "noun"),
        ("A0", "Дом и вещи", "die Brille", "очки", "Meine Brille ist hier.", "noun"),
        ("A0", "Дом и вещи", "die Uhr", "часы", "Die Uhr ist teuer.", "noun"),
        ("A0", "Дом и вещи", "das Geld", "деньги", "Das Geld ist in der Tasche.", "noun"),
        # A0: people and family
        ("A0", "Люди и семья", "die Mutter", "мама", "Meine Mutter heißt Anna.", "noun"),
        ("A0", "Люди и семья", "der Vater", "папа", "Mein Vater arbeitet heute.", "noun"),
        ("A0", "Люди и семья", "die Schwester", "сестра", "Meine Schwester wohnt in Berlin.", "noun"),
        ("A0", "Люди и семья", "der Bruder", "брат", "Mein Bruder lernt Deutsch.", "noun"),
        ("A0", "Люди и семья", "das Kind", "ребёнок", "Das Kind spielt.", "noun"),
        ("A0", "Люди и семья", "die Familie", "семья", "Meine Familie ist klein.", "noun"),
        ("A0", "Люди и семья", "der Freund", "друг", "Mein Freund kommt morgen.", "noun"),
        ("A0", "Люди и семья", "die Freundin", "подруга", "Meine Freundin kommt heute.", "noun"),
        ("A0", "Люди и семья", "der Mann", "мужчина", "Der Mann ist Arzt.", "noun"),
        ("A0", "Люди и семья", "die Frau", "женщина", "Die Frau ist Lehrerin.", "noun"),
        ("A0", "Люди и семья", "der Mensch", "человек", "Der Mensch braucht Hilfe.", "noun"),
        ("A0", "Люди и семья", "die Leute", "люди", "Die Leute warten.", "noun"),
        # A0: food
        ("A0", "Еда и напитки", "das Wasser", "вода", "Ich trinke Wasser.", "noun"),
        ("A0", "Еда и напитки", "der Kaffee", "кофе", "Der Kaffee ist warm.", "noun"),
        ("A0", "Еда и напитки", "der Tee", "чай", "Ich möchte Tee.", "noun"),
        ("A0", "Еда и напитки", "das Brot", "хлеб", "Das Brot ist frisch.", "noun"),
        ("A0", "Еда и напитки", "die Butter", "масло", "Die Butter ist im Kühlschrank.", "noun"),
        ("A0", "Еда и напитки", "der Käse", "сыр", "Der Käse schmeckt gut.", "noun"),
        ("A0", "Еда и напитки", "das Ei", "яйцо", "Ich esse ein Ei.", "noun"),
        ("A0", "Еда и напитки", "der Apfel", "яблоко", "Der Apfel ist rot.", "noun"),
        ("A0", "Еда и напитки", "die Banane", "банан", "Die Banane ist gelb.", "noun"),
        ("A0", "Еда и напитки", "die Suppe", "суп", "Die Suppe ist heiß.", "noun"),
        ("A0", "Еда и напитки", "der Reis", "рис", "Der Reis ist fertig.", "noun"),
        ("A0", "Еда и напитки", "das Fleisch", "мясо", "Ich esse kein Fleisch.", "noun"),
        ("A0", "Еда и напитки", "der Fisch", "рыба", "Der Fisch ist frisch.", "noun"),
        ("A0", "Еда и напитки", "das Gemüse", "овощи", "Das Gemüse ist gesund.", "noun"),
        ("A0", "Еда и напитки", "das Obst", "фрукты", "Ich kaufe Obst.", "noun"),
        # A0: city and orientation
        ("A0", "Город и дорога", "die Straße", "улица", "Die Straße ist lang.", "noun"),
        ("A0", "Город и дорога", "der Bahnhof", "вокзал", "Der Bahnhof ist links.", "noun"),
        ("A0", "Город и дорога", "die Haltestelle", "остановка", "Die Haltestelle ist dort.", "noun"),
        ("A0", "Город и дорога", "der Bus", "автобус", "Der Bus kommt gleich.", "noun"),
        ("A0", "Город и дорога", "die Bahn", "поезд/электричка", "Die Bahn kommt um acht.", "noun"),
        ("A0", "Город и дорога", "das Auto", "машина", "Das Auto ist schnell.", "noun"),
        ("A0", "Город и дорога", "links", "слева", "Der Bahnhof ist links.", "adverb"),
        ("A0", "Город и дорога", "rechts", "справа", "Die Apotheke ist rechts.", "adverb"),
        ("A0", "Город и дорога", "geradeaus", "прямо", "Gehen Sie geradeaus.", "adverb"),
        ("A0", "Город и дорога", "hier", "здесь", "Ich bin hier.", "adverb"),
        ("A0", "Город и дорога", "dort", "там", "Die Schule ist dort.", "adverb"),
        ("A0", "Город и дорога", "in der Nähe", "рядом", "Die Haltestelle ist in der Nähe.", "phrase"),
        # A0: body and health
        ("A0", "Тело и здоровье", "der Kopf", "голова", "Mein Kopf tut weh.", "noun"),
        ("A0", "Тело и здоровье", "das Auge", "глаз", "Mein Auge ist rot.", "noun"),
        ("A0", "Тело и здоровье", "das Ohr", "ухо", "Mein Ohr tut weh.", "noun"),
        ("A0", "Тело и здоровье", "der Mund", "рот", "Der Mund ist trocken.", "noun"),
        ("A0", "Тело и здоровье", "die Hand", "рука/кисть", "Meine Hand tut weh.", "noun"),
        ("A0", "Тело и здоровье", "der Fuß", "нога/стопа", "Mein Fuß tut weh.", "noun"),
        ("A0", "Тело и здоровье", "der Bauch", "живот", "Mein Bauch tut weh.", "noun"),
        ("A0", "Тело и здоровье", "krank", "больной", "Ich bin krank.", "adjective"),
        ("A0", "Тело и здоровье", "müde", "усталый", "Ich bin müde.", "adjective"),
        ("A0", "Тело и здоровье", "besser", "лучше", "Es geht mir besser.", "adjective"),
        # A0: verbs and adjectives
        ("A0", "Частые глаголы", "kommen", "приходить/приезжать", "Ich komme aus Russland.", "verb"),
        ("A0", "Частые глаголы", "gehen", "идти", "Ich gehe nach Hause.", "verb"),
        ("A0", "Частые глаголы", "machen", "делать", "Was machst du?", "verb"),
        ("A0", "Частые глаголы", "lernen", "учить", "Ich lerne Deutsch.", "verb"),
        ("A0", "Частые глаголы", "sprechen", "говорить", "Ich spreche ein bisschen Deutsch.", "verb"),
        ("A0", "Частые глаголы", "fragen", "спрашивать", "Ich frage den Lehrer.", "verb"),
        ("A0", "Частые глаголы", "antworten", "отвечать", "Ich antworte kurz.", "verb"),
        ("A0", "Частые глаголы", "brauchen", "нуждаться", "Ich brauche Hilfe.", "verb"),
        ("A0", "Частые глаголы", "möchten", "хотеть вежливо", "Ich möchte Wasser.", "verb"),
        ("A0", "Частые глаголы", "kaufen", "покупать", "Ich kaufe Brot.", "verb"),
        ("A0", "Частые признаки", "gut", "хороший", "Das ist gut.", "adjective"),
        ("A0", "Частые признаки", "schlecht", "плохой", "Das ist schlecht.", "adjective"),
        ("A0", "Частые признаки", "groß", "большой", "Das Zimmer ist groß.", "adjective"),
        ("A0", "Частые признаки", "klein", "маленький", "Das Zimmer ist klein.", "adjective"),
        ("A0", "Частые признаки", "neu", "новый", "Mein Handy ist neu.", "adjective"),
        ("A0", "Частые признаки", "alt", "старый", "Das Haus ist alt.", "adjective"),
        ("A0", "Частые признаки", "warm", "тёплый", "Der Kaffee ist warm.", "adjective"),
        ("A0", "Частые признаки", "kalt", "холодный", "Das Wasser ist kalt.", "adjective"),
        ("A0", "Частые признаки", "teuer", "дорогой", "Das ist teuer.", "adjective"),
        ("A0", "Частые признаки", "billig", "дешёвый", "Das ist billig.", "adjective"),
        # A0: survival phrases
        ("A0", "A0 фразы выживания", "Ich verstehe nicht.", "Я не понимаю.", "Ich verstehe nicht.", "phrase"),
        ("A0", "A0 фразы выживания", "Noch einmal, bitte.", "Ещё раз, пожалуйста.", "Noch einmal, bitte.", "phrase"),
        ("A0", "A0 фразы выживания", "Langsam, bitte.", "Медленно, пожалуйста.", "Langsam, bitte.", "phrase"),
        ("A0", "A0 фразы выживания", "Ich weiß nicht.", "Я не знаю.", "Ich weiß nicht.", "phrase"),
        ("A0", "A0 фразы выживания", "Ich habe eine Frage.", "У меня вопрос.", "Ich habe eine Frage.", "phrase"),
        ("A0", "A0 фразы выживания", "Wie heißt das auf Deutsch?", "Как это называется по-немецки?", "Wie heißt das auf Deutsch?", "phrase"),
        ("A0", "A0 фразы выживания", "Was bedeutet das?", "Что это значит?", "Was bedeutet das?", "phrase"),
        ("A0", "A0 фразы выживания", "Können Sie mir helfen?", "Вы можете мне помочь?", "Können Sie mir helfen?", "phrase"),
        ("A0", "A0 фразы выживания", "Ich brauche bitte Hilfe.", "Мне нужна помощь.", "Ich brauche bitte Hilfe.", "phrase"),
        ("A0", "A0 фразы выживания", "Wo ist die Toilette?", "Где туалет?", "Wo ist die Toilette?", "phrase"),
        # A1 reinforcement
        ("A1", "Покупки и цены", "Wie viel kostet das?", "Сколько это стоит?", "Wie viel kostet das?", "phrase"),
        ("A1", "Покупки и цены", "Das ist zu teuer.", "Это слишком дорого.", "Das ist zu teuer.", "phrase"),
        ("A1", "Покупки и цены", "Ich nehme das.", "Я это беру.", "Ich nehme das.", "phrase"),
        ("A1", "Покупки и цены", "Kann ich mit Karte bezahlen?", "Можно оплатить картой?", "Kann ich mit Karte bezahlen?", "phrase"),
        ("A1", "Покупки и цены", "Ich suche Brot.", "Я ищу хлеб.", "Ich suche Brot.", "phrase"),
        ("A1", "Покупки и цены", "Haben Sie Milch?", "У вас есть молоко?", "Haben Sie Milch?", "phrase"),
        ("A1", "Покупки и цены", "die Rechnung", "счёт", "Die Rechnung ist richtig.", "noun"),
        ("A1", "Покупки и цены", "der Preis", "цена", "Der Preis ist hoch.", "noun"),
        ("A1", "Покупки и цены", "der Supermarkt", "супермаркет", "Der Supermarkt ist offen.", "noun"),
        ("A1", "Покупки и цены", "die Kasse", "касса", "Die Kasse ist dort.", "noun"),
        ("A1", "Повседневная рутина", "aufstehen", "вставать", "Ich stehe um sieben Uhr auf.", "verb"),
        ("A1", "Повседневная рутина", "frühstücken", "завтракать", "Ich frühstücke um acht Uhr.", "verb"),
        ("A1", "Повседневная рутина", "arbeiten", "работать", "Ich arbeite heute.", "verb"),
        ("A1", "Повседневная рутина", "einkaufen", "делать покупки", "Ich kaufe am Abend ein.", "verb"),
        ("A1", "Повседневная рутина", "kochen", "готовить", "Ich koche Suppe.", "verb"),
        ("A1", "Повседневная рутина", "schlafen", "спать", "Ich schlafe gut.", "verb"),
        ("A1", "Повседневная рутина", "der Morgen", "утро", "Am Morgen trinke ich Kaffee.", "noun"),
        ("A1", "Повседневная рутина", "der Abend", "вечер", "Am Abend lerne ich Deutsch.", "noun"),
        ("A1", "Связная речь", "zuerst", "сначала", "Zuerst frühstücke ich.", "adverb"),
        ("A1", "Связная речь", "dann", "потом", "Dann gehe ich zur Arbeit.", "adverb"),
        ("A1", "Связная речь", "danach", "после этого", "Danach kaufe ich ein.", "adverb"),
        ("A1", "Связная речь", "später", "позже", "Später rufe ich an.", "adverb"),
        ("A1", "Связная речь", "jeden Tag", "каждый день", "Ich lerne jeden Tag Deutsch.", "phrase"),
        ("A1", "Связная речь", "am Wochenende", "на выходных", "Am Wochenende habe ich Zeit.", "phrase"),
    ]

    added = 0
    for level, topic, de, ru, example, pos in rows:
        key = de.strip().lower()
        if key in de_seen:
            continue
        base = f"{level.lower()}-{slug(topic)}-{slug(de)}"
        item_id = base
        n = 2
        while item_id in ids:
            item_id = f"{base}-{n}"
            n += 1
        vocab.append({
            "id": item_id,
            "level": level,
            "topic": topic,
            "de": de,
            "ru": ru,
            "example": example,
            "pos": pos,
        })
        ids.add(item_id)
        de_seen.add(key)
        added += 1
    return added


def lesson(level, order, module, lesson_id, title, goal, rule, examples, drills, tags, theory, trap, logic, formula, table_rows):
    return {
        "id": lesson_id,
        "level": level,
        "order": order,
        "module": module,
        "title": title,
        "goal": goal,
        "rule": rule,
        "examples": examples,
        "drills": drills,
        "tags": tags,
        "deepTheoryRu": theory,
        "russianTrap": trap,
        "germanLogic": logic,
        "formula": formula,
        "typicalMistakes": [
            "учить слово без артикля",
            "переводить русский порядок слов напрямую",
            "не проговаривать немецкую фразу вслух",
        ],
        "grammarTables": [{
            "title": "Мини-шаблоны",
            "headers": ["Ситуация", "Немецкая форма", "Что проверить"],
            "rows": table_rows,
        }],
        "whyForRussian": "Блок добавлен для полного старта с нуля: сначала простые слова, потом готовая фраза, затем проверка формы и произношение.",
        "visualSchemes": [{
            "title": "Как учить блок",
            "steps": [
                {"label": "1", "title": "Слово", "text": "Сразу с артиклем и переводом.", "de": examples[0]["de"] if examples else ""},
                {"label": "2", "title": "Фраза", "text": "Вставить слово в короткое предложение.", "de": examples[1]["de"] if len(examples) > 1 else ""},
                {"label": "3", "title": "Повтор", "text": "Сказать вслух и закрыть русский перевод."},
            ],
            "bars": [
                {"label": "словарь", "value": 90},
                {"label": "фраза", "value": 75},
                {"label": "произношение", "value": 80},
            ],
        }],
    }


def add_lessons(data):
    lessons = data.setdefault("lessons", [])
    ids = existing_ids(lessons)
    added = 0

    candidates = [
        lesson(
            "A0", 16, "Базовый словарь", "a0-16-objects-around-me",
            "Вещи вокруг: стол, дверь, телефон, книга",
            "Научиться называть простые предметы вокруг себя и строить фразы Das ist...",
            "На A0 существительное нужно учить сразу с артиклем: der Tisch, die Tür, das Buch. Шаблон Das ist ... помогает быстро говорить без сложной грамматики.",
            [
                {"de": "Das ist der Tisch.", "ru": "Это стол."},
                {"de": "Das ist die Tür.", "ru": "Это дверь."},
                {"de": "Das ist das Buch.", "ru": "Это книга."},
                {"de": "Mein Handy ist hier.", "ru": "Мой телефон здесь."},
                {"de": "Der Schlüssel ist in der Tasche.", "ru": "Ключ в сумке."},
                {"de": "Die Lampe ist hell.", "ru": "Лампа яркая."},
            ],
            [
                {"q": "Как правильно: стол?", "options": ["der Tisch", "die Tisch", "das Tisch"], "answer": 0, "topic": "articles", "explanation": "Правильно: der Tisch. На A0 слово учится вместе с артиклем, иначе позже трудно выбрать падеж."},
                {"q": "Что значит Das ist die Tür?", "options": ["Это дверь.", "Это стол.", "Это телефон."], "answer": 0, "topic": "basic-nouns", "explanation": "Das ist ... = Это ...; die Tür = дверь."},
                {"q": "Где правильная фраза?", "options": ["Mein Handy ist hier.", "Mein Handy hier ist.", "Handy mein ist hier."], "answer": 0, "topic": "word-order", "explanation": "В утверждении спрягаемый глагол ist стоит на позиции 2."},
                {"q": "Ключ по-немецки:", "options": ["der Schlüssel", "die Lampe", "das Papier"], "answer": 0, "topic": "basic-nouns", "explanation": "der Schlüssel = ключ. Учим: der Schlüssel ist hier."},
                {"q": "Как сказать «книга»?", "options": ["das Buch", "der Bus", "die Brille"], "answer": 0, "topic": "basic-nouns", "explanation": "das Buch = книга; das сразу запоминается вместе со словом."},
                {"q": "Какой шаблон безопасен для A0?", "options": ["Das ist ...", "Weil ich ...", "Trotzdem ..."], "answer": 0, "topic": "phrases", "explanation": "Das ist ... позволяет быстро назвать предмет без сложного порядка слов."},
            ],
            ["objects", "articles", "pronunciation"],
            "Русскоговорящему хочется сначала выучить перевод: стол, дверь, книга. В немецком этого мало: нужно сразу хранить в памяти der/die/das.",
            "Ловушка: сказать просто Tisch и потом не знать, почему в упражнениях появляется den Tisch или dem Tisch.",
            "Немецкая логика: существительное почти всегда живёт вместе с артиклем и формой.",
            "Das ist + der/die/das + слово: Das ist der Tisch.",
            [["назвать предмет", "Das ist der Tisch.", "артикль"], ["сказать где", "Mein Handy ist hier.", "V2"], ["повторить вслух", "der Tisch, die Tür, das Buch", "произношение"]],
        ),
        lesson(
            "A0", 17, "Базовый словарь", "a0-17-family-people",
            "Люди и семья",
            "Называть близких людей и задавать вопрос Wer ist das?",
            "Вопрос Wer ist das? значит «Кто это?». Ответ строится просто: Das ist mein Vater. Das ist meine Mutter.",
            [
                {"de": "Wer ist das?", "ru": "Кто это?"},
                {"de": "Das ist meine Mutter.", "ru": "Это моя мама."},
                {"de": "Das ist mein Vater.", "ru": "Это мой папа."},
                {"de": "Mein Bruder lernt Deutsch.", "ru": "Мой брат учит немецкий."},
                {"de": "Meine Schwester wohnt in Berlin.", "ru": "Моя сестра живёт в Берлине."},
                {"de": "Meine Familie ist klein.", "ru": "Моя семья маленькая."},
            ],
            [
                {"q": "Как спросить «Кто это?»", "options": ["Wer ist das?", "Wo ist das?", "Was kostet das?"], "answer": 0, "topic": "questions", "explanation": "Wer = кто. Вопрос Wer ist das? — базовый вопрос про человека."},
                {"q": "Мама по-немецки:", "options": ["die Mutter", "der Vater", "das Kind"], "answer": 0, "topic": "family", "explanation": "die Mutter = мама. В ответе: Das ist meine Mutter."},
                {"q": "Папа по-немецки:", "options": ["der Vater", "die Schwester", "die Leute"], "answer": 0, "topic": "family", "explanation": "der Vater = папа. Артикль der важен."},
                {"q": "Что значит Meine Familie ist klein?", "options": ["Моя семья маленькая.", "Моя семья дорогая.", "Моя семья здесь."], "answer": 0, "topic": "family", "explanation": "meine Familie = моя семья, ist klein = маленькая."},
                {"q": "Где правильный порядок?", "options": ["Mein Bruder lernt Deutsch.", "Mein Bruder Deutsch lernt.", "Lernt mein Bruder Deutsch."], "answer": 0, "topic": "word-order", "explanation": "В утверждении глагол lernt стоит вторым."},
                {"q": "Что выбрать для Schwester?", "options": ["meine Schwester", "mein Schwester", "meiner Schwester всегда"], "answer": 0, "topic": "possessive", "explanation": "die Schwester, поэтому в Nominativ: meine Schwester."},
            ],
            ["family", "questions", "possessive"],
            "Для русского «мой/моя» звучит естественно, но в немецком форма зависит от рода слова: mein Vater, meine Mutter.",
            "Ловушка: говорить mein Mutter, потому что по-русски «моя» кажется отдельным словом без немецкого рода.",
            "Немецкая логика: притяжательное слово согласуется с существительным.",
            "Wer ist das? -> Das ist mein Vater / meine Mutter.",
            [["вопрос", "Wer ist das?", "Wer = кто"], ["мужской род", "mein Vater", "der Vater"], ["женский род", "meine Mutter", "die Mutter"]],
        ),
        lesson(
            "A0", 18, "Базовый словарь", "a0-18-food-drinks",
            "Еда и напитки",
            "Попросить воду, чай, хлеб и понять простые слова в магазине или кафе.",
            "Вежливый A0-шаблон: Ich möchte ... = Я хотел бы/хотела бы. Для отрицания: Ich esse kein Fleisch.",
            [
                {"de": "Ich möchte Wasser.", "ru": "Я хотел бы воды."},
                {"de": "Ich trinke Kaffee.", "ru": "Я пью кофе."},
                {"de": "Das Brot ist frisch.", "ru": "Хлеб свежий."},
                {"de": "Ich kaufe Obst.", "ru": "Я покупаю фрукты."},
                {"de": "Ich esse kein Fleisch.", "ru": "Я не ем мясо."},
                {"de": "Die Suppe ist heiß.", "ru": "Суп горячий."},
            ],
            [
                {"q": "Как вежливо сказать «я хочу воды»?", "options": ["Ich möchte Wasser.", "Ich Wasser.", "Ich bin Wasser."], "answer": 0, "topic": "food", "explanation": "Ich möchte ... — безопасный вежливый шаблон для заказа."},
                {"q": "Хлеб по-немецки:", "options": ["das Brot", "der Kaffee", "die Suppe"], "answer": 0, "topic": "food", "explanation": "das Brot = хлеб. Пример: Das Brot ist frisch."},
                {"q": "Что значит Ich esse kein Fleisch?", "options": ["Я не ем мясо.", "Я ем рыбу.", "Я покупаю мясо."], "answer": 0, "topic": "negation", "explanation": "kein отрицает существительное: kein Fleisch = никакого мяса."},
                {"q": "Фрукты по-немецки:", "options": ["das Obst", "das Gemüse", "das Wasser"], "answer": 0, "topic": "food", "explanation": "das Obst = фрукты; das Gemüse = овощи."},
                {"q": "Где правильный глагол?", "options": ["Ich trinke Kaffee.", "Ich Kaffee trinke.", "Ich bin Kaffee."], "answer": 0, "topic": "word-order", "explanation": "trinke стоит на позиции 2: Ich trinke Kaffee."},
                {"q": "Что значит Die Suppe ist heiß?", "options": ["Суп горячий.", "Суп холодный.", "Суп дорогой."], "answer": 0, "topic": "adjectives", "explanation": "heiß = горячий; kalt = холодный."},
            ],
            ["food", "phrases", "negation"],
            "На старте важно не перечислять еду списком, а сразу уметь попросить: Ich möchte Wasser.",
            "Ловушка: говорить Ich will ... в любой ситуации. Это не всегда грубо, но Ich möchte безопаснее и вежливее.",
            "Немецкая логика: готовые фразы в кафе и магазине полезнее отдельных слов.",
            "Ich möchte + еда/напиток: Ich möchte Tee.",
            [["заказ", "Ich möchte Wasser.", "вежливый шаблон"], ["отрицание", "kein Fleisch", "kein + существительное"], ["качество", "Die Suppe ist heiß.", "ist + признак"]],
        ),
        lesson(
            "A0", 19, "Ориентация", "a0-19-city-directions",
            "Город: где остановка, вокзал и аптека",
            "Спросить, где находится место, и понять links, rechts, geradeaus.",
            "Вопрос Wo ist ...? значит «Где ...?». Ответы для A0: hier, dort, links, rechts, geradeaus, in der Nähe.",
            [
                {"de": "Wo ist der Bahnhof?", "ru": "Где вокзал?"},
                {"de": "Die Haltestelle ist dort.", "ru": "Остановка там."},
                {"de": "Gehen Sie geradeaus.", "ru": "Идите прямо."},
                {"de": "Die Apotheke ist rechts.", "ru": "Аптека справа."},
                {"de": "Der Bus kommt gleich.", "ru": "Автобус скоро придёт."},
                {"de": "Die Schule ist in der Nähe.", "ru": "Школа рядом."},
            ],
            [
                {"q": "Как спросить «Где вокзал?»", "options": ["Wo ist der Bahnhof?", "Wer ist der Bahnhof?", "Was ist Bahnhof?"], "answer": 0, "topic": "city", "explanation": "Wo = где. Wo ist der Bahnhof? — базовый вопрос ориентации."},
                {"q": "Что значит geradeaus?", "options": ["прямо", "слева", "дорого"], "answer": 0, "topic": "directions", "explanation": "geradeaus = прямо. Частая инструкция: Gehen Sie geradeaus."},
                {"q": "Остановка:", "options": ["die Haltestelle", "der Schlüssel", "das Bett"], "answer": 0, "topic": "city", "explanation": "die Haltestelle = остановка."},
                {"q": "rechts значит:", "options": ["справа", "слева", "рядом"], "answer": 0, "topic": "directions", "explanation": "rechts = справа, links = слева."},
                {"q": "Как сказать «рядом»?", "options": ["in der Nähe", "um acht Uhr", "kein Fleisch"], "answer": 0, "topic": "directions", "explanation": "in der Nähe = рядом, поблизости."},
                {"q": "Где правильный порядок?", "options": ["Der Bus kommt gleich.", "Der Bus gleich kommt.", "Kommt der Bus gleich."], "answer": 0, "topic": "word-order", "explanation": "В утверждении kommt стоит вторым."},
            ],
            ["city", "directions", "questions"],
            "Русскоговорящему легко выучить слова «лево/право», но в реальной ситуации нужна готовая фраза вопроса.",
            "Ловушка: путать wo и wohin. На A0 пока держим простой вопрос Wo ist ...?",
            "Немецкая логика: место часто выражается короткими устойчивыми словами.",
            "Wo ist + место? -> Wo ist der Bahnhof?",
            [["вопрос", "Wo ist der Bahnhof?", "Wo = где"], ["ответ", "Die Haltestelle ist dort.", "dort = там"], ["инструкция", "Gehen Sie geradeaus.", "Imperativ Sie"]],
        ),
        lesson(
            "A0", 20, "Повторение", "a0-20-basic-review-1",
            "A0 повторение: 50 базовых слов в простых фразах",
            "Проверить артикли, простые предметы, еду, семью и город.",
            "Повторение на A0 должно быть коротким и частым: слово -> артикль -> фраза -> вопрос. Не надо ждать, пока накопится много грамматики.",
            [
                {"de": "Das ist mein Buch.", "ru": "Это моя книга."},
                {"de": "Meine Mutter trinkt Tee.", "ru": "Моя мама пьёт чай."},
                {"de": "Ich brauche den Schlüssel.", "ru": "Мне нужен ключ."},
                {"de": "Der Bahnhof ist in der Nähe.", "ru": "Вокзал рядом."},
                {"de": "Ich möchte Brot und Käse.", "ru": "Я хотел бы хлеб и сыр."},
                {"de": "Ich verstehe nicht.", "ru": "Я не понимаю."},
            ],
            [
                {"q": "Что учим вместе со словом?", "options": ["артикль", "только перевод", "только русский пример"], "answer": 0, "topic": "articles", "explanation": "Немецкое существительное нужно учить с артиклем: der Tisch, die Tür, das Buch."},
                {"q": "Выберите фразу для просьбы:", "options": ["Ich möchte Brot.", "Ich Brot möchte.", "Brot ich."], "answer": 0, "topic": "phrases", "explanation": "Ich möchte ... — вежливый и простой шаблон."},
                {"q": "Что значит Ich verstehe nicht?", "options": ["Я не понимаю.", "Я не покупаю.", "Я не иду."], "answer": 0, "topic": "survival", "explanation": "Это ключевая фраза выживания в разговоре."},
                {"q": "Какой вариант с артиклем правильный?", "options": ["das Buch", "die Buch", "der Buch"], "answer": 0, "topic": "articles", "explanation": "Buch среднего рода: das Buch."},
                {"q": "Что значит in der Nähe?", "options": ["рядом", "вчера", "дорого"], "answer": 0, "topic": "directions", "explanation": "in der Nähe = рядом, поблизости."},
                {"q": "Что делать, если не понял?", "options": ["Noch einmal, bitte.", "Ich bin Brot.", "Der Bus ist Käse."], "answer": 0, "topic": "survival", "explanation": "Noch einmal, bitte. = Ещё раз, пожалуйста."},
            ],
            ["review", "articles", "survival"],
            "Повторение должно связывать словарь с микрофразой. Тогда слово не лежит отдельно, а сразу используется.",
            "Ловушка: узнавать слово в списке, но не суметь произнести простую фразу с ним.",
            "Немецкая логика: минимальная единица обучения — не слово, а слово в коротком предложении.",
            "артикль -> слово -> фраза -> вопрос",
            [["предмет", "das Buch", "артикль"], ["фраза", "Das ist mein Buch.", "V2"], ["выживание", "Noch einmal, bitte.", "готовый блок"]],
        ),
        lesson(
            "A1", 19, "Повседневность", "a1-19-shopping-prices",
            "Покупки, цены и касса",
            "Спросить цену, оплатить картой и сказать, что нужно.",
            "В магазине нужны готовые формулы: Wie viel kostet das? Ich nehme das. Kann ich mit Karte bezahlen?",
            [
                {"de": "Wie viel kostet das?", "ru": "Сколько это стоит?"},
                {"de": "Ich nehme das.", "ru": "Я это беру."},
                {"de": "Kann ich mit Karte bezahlen?", "ru": "Можно оплатить картой?"},
                {"de": "Das ist zu teuer.", "ru": "Это слишком дорого."},
                {"de": "Ich suche Brot.", "ru": "Я ищу хлеб."},
                {"de": "Haben Sie Milch?", "ru": "У вас есть молоко?"},
            ],
            [
                {"q": "Как спросить цену?", "options": ["Wie viel kostet das?", "Wo ist das?", "Wer ist das?"], "answer": 0, "topic": "shopping", "explanation": "Wie viel kostet das? — базовый вопрос о цене."},
                {"q": "Как сказать «Я это беру»?", "options": ["Ich nehme das.", "Ich bin das.", "Ich habe teuer."], "answer": 0, "topic": "shopping", "explanation": "nehmen = брать; Ich nehme das. — готовая магазинная фраза."},
                {"q": "Оплатить картой:", "options": ["mit Karte bezahlen", "mit Brot bezahlen", "nach Karte gehen"], "answer": 0, "topic": "shopping", "explanation": "mit + Dativ: mit Karte bezahlen."},
                {"q": "Das ist zu teuer значит:", "options": ["Это слишком дорого.", "Это слишком холодно.", "Это рядом."], "answer": 0, "topic": "adjectives", "explanation": "zu teuer = слишком дорого."},
                {"q": "Где правильный вопрос?", "options": ["Haben Sie Milch?", "Sie haben Milch?", "Milch haben Sie?"], "answer": 0, "topic": "questions", "explanation": "В Ja/Nein-вопросе глагол стоит первым: Haben Sie ...?"},
                {"q": "Ich suche Brot значит:", "options": ["Я ищу хлеб.", "Я покупаю билет.", "Я пью чай."], "answer": 0, "topic": "shopping", "explanation": "suchen = искать; Brot = хлеб."},
            ],
            ["shopping", "questions", "dativ"],
            "Покупки — хороший A1-тренажёр, потому что сразу проверяются вопрос, Akkusativ, mit + Dativ и вежливость.",
            "Ловушка: переводить «можно картой?» без глагола. В немецком нужна форма bezahlen.",
            "Немецкая логика: даже короткая бытовая фраза держит порядок слов и управление.",
            "Kann ich + Infinitiv? -> Kann ich mit Karte bezahlen?",
            [["цена", "Wie viel kostet das?", "вопрос"], ["выбор", "Ich nehme das.", "V2"], ["оплата", "mit Karte bezahlen", "mit + Dativ"]],
        ),
        lesson(
            "A1", 20, "Повторение", "a1-20-daily-routine-review",
            "Распорядок дня: связать 6 коротких предложений",
            "Рассказать простой день через zuerst, dann, danach, später.",
            "На A1 важно начать связывать предложения. Слова zuerst, dann, danach, später помогают строить мини-рассказ.",
            [
                {"de": "Zuerst frühstücke ich.", "ru": "Сначала я завтракаю."},
                {"de": "Dann gehe ich zur Arbeit.", "ru": "Потом я иду на работу."},
                {"de": "Danach kaufe ich ein.", "ru": "После этого я делаю покупки."},
                {"de": "Später koche ich Suppe.", "ru": "Позже я готовлю суп."},
                {"de": "Am Abend lerne ich Deutsch.", "ru": "Вечером я учу немецкий."},
                {"de": "Ich schlafe um elf Uhr.", "ru": "Я сплю в одиннадцать."},
            ],
            [
                {"q": "Что значит zuerst?", "options": ["сначала", "позже", "вчера"], "answer": 0, "topic": "connectors", "explanation": "zuerst = сначала. Если оно стоит в первом поле, глагол идёт вторым: Zuerst frühstücke ich."},
                {"q": "Где правильный порядок?", "options": ["Dann gehe ich zur Arbeit.", "Dann ich gehe zur Arbeit.", "Ich dann gehe zur Arbeit."], "answer": 0, "topic": "word-order", "explanation": "Dann занимает первое поле, поэтому gehe стоит сразу после него."},
                {"q": "einkaufen в предложении:", "options": ["Ich kaufe ein.", "Ich einkaufe.", "Ich kaufe aus."], "answer": 0, "topic": "separable", "explanation": "einkaufen отделяется: Ich kaufe ein."},
                {"q": "Am Abend значит:", "options": ["вечером", "утром", "сейчас"], "answer": 0, "topic": "time", "explanation": "am Abend = вечером; am Morgen = утром."},
                {"q": "Как сказать «я завтракаю»?", "options": ["Ich frühstücke.", "Ich Frühstück.", "Ich bin Frühstück."], "answer": 0, "topic": "verbs", "explanation": "frühstücken — глагол; ich frühstücke."},
                {"q": "Später koche ich Suppe значит:", "options": ["Позже я готовлю суп.", "Сначала я сплю.", "Потом я еду на автобусе."], "answer": 0, "topic": "routine", "explanation": "später = позже, koche = готовлю, Suppe = суп."},
            ],
            ["routine", "connectors", "separable"],
            "Русский рассказ может быть свободным по порядку слов. В немецком связка в начале меняет порядок: Dann gehe ich, а не Dann ich gehe.",
            "Ловушка: ставить субъект сразу после dann/zuerst. Немецкому нужен V2.",
            "Немецкая логика: первое поле задаёт рамку, второе место держит глагол.",
            "zuerst/dann/danach/später + Verb + Subjekt",
            [["старт", "Zuerst frühstücke ich.", "V2"], ["следующий шаг", "Dann gehe ich zur Arbeit.", "V2"], ["отделяемый глагол", "Ich kaufe ein.", "приставка в конце"]],
        ),
    ]

    for item in candidates:
        if item["id"] in ids:
            continue
        lessons.append(item)
        ids.add(item["id"])
        added += 1
    return added


def add_diagnostic_questions(data):
    diagnostic = data.setdefault("diagnostic", [])
    existing = {(q.get("level"), q.get("q")) for q in diagnostic if isinstance(q, dict)}
    rows = [
        {"level": "A0", "topic": "basic-nouns", "q": "der Tisch — это...", "options": ["стол", "дверь", "суп"], "answer": 0, "explanation": "der Tisch = стол. Важно запомнить сразу с артиклем der."},
        {"level": "A0", "topic": "food", "q": "Ich möchte Wasser значит...", "options": ["Я хотел бы воды.", "Я не понимаю.", "Где вокзал?"], "answer": 0, "explanation": "Ich möchte ... — вежливая формула просьбы или заказа."},
        {"level": "A0", "topic": "directions", "q": "geradeaus значит...", "options": ["прямо", "слева", "дорого"], "answer": 0, "explanation": "geradeaus = прямо. Частая фраза: Gehen Sie geradeaus."},
        {"level": "A0", "topic": "survival", "q": "Как попросить повторить?", "options": ["Noch einmal, bitte.", "Ich nehme das.", "Der Tisch ist hier."], "answer": 0, "explanation": "Noch einmal, bitte. = Ещё раз, пожалуйста."},
        {"level": "A1", "topic": "shopping", "q": "Как спросить цену?", "options": ["Wie viel kostet das?", "Wer ist das?", "Wo wohnen Sie?"], "answer": 0, "explanation": "Wie viel kostet das? — стандартный вопрос о цене."},
        {"level": "A1", "topic": "connectors", "q": "Правильный порядок после dann:", "options": ["Dann gehe ich.", "Dann ich gehe.", "Dann ich bin gehe."], "answer": 0, "explanation": "Dann занимает первое поле, поэтому глагол стоит вторым: Dann gehe ich."},
    ]
    added = 0
    for row in rows:
        key = (row["level"], row["q"])
        if key in existing:
            continue
        diagnostic.append(row)
        existing.add(key)
        added += 1
    return added


def stats(data):
    lessons = data.get("lessons", [])
    vocab = data.get("vocab", [])
    drills = [d for lesson in lessons for d in lesson.get("drills", [])]
    return {
        "lessons": len(lessons),
        "lessonsByLevel": dict(Counter(l.get("level") for l in lessons)),
        "vocab": len(vocab),
        "vocabByLevel": dict(Counter(v.get("level") for v in vocab)),
        "diagnostic": len(data.get("diagnostic", [])),
        "drills": len(drills),
        "examples": sum(len(l.get("examples") or []) for l in lessons),
        "a0VocabTopics": dict(Counter(v.get("topic") for v in vocab if v.get("level") == "A0")),
        "a1VocabTopics": dict(Counter(v.get("topic") for v in vocab if v.get("level") == "A1")),
    }


def write_reports(root, before, after, added):
    data_dir = root / "data"
    docs_dir = root / "docs" / "diagnostics"
    data_dir.mkdir(exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "version": VERSION,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "purpose": "Beginner content expansion: A0/A1 core vocabulary, practical lessons, review drills and diagnostic checks.",
        "before": before,
        "after": after,
        "added": added,
        "qualityFocus": [
            "A0 learner can start from zero with common objects, family, food, city directions and survival phrases.",
            "A1 learner gets practical shopping and daily routine reinforcement.",
            "Lessons include examples, drills, Russian-speaker traps, mini tables and visual schemes.",
            "New German words and phrases are included in app-data so the neural MP3 generator can cover them.",
        ],
    }
    (data_dir / "beginner_content_v15_9.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    md = f"""# Beginner content expansion {VERSION}

Дата: {DATE}

## Что добавлено

- A0 базовый словарь: предметы, семья, еда, город, тело, частые глаголы, признаки и фразы выживания.
- Новые A0-уроки: вещи вокруг, семья, еда, город и повторение.
- Новые A1-уроки: покупки/цены и распорядок дня.
- Дополнительные диагностические вопросы A0/A1.
- Все новые немецкие слова и фразы находятся в `app-data` и должны попадать в полный neural MP3 generator.

## Количественно

- Уроки: {before['lessons']} -> {after['lessons']}
- Словарь: {before['vocab']} -> {after['vocab']}
- Упражнения: {before['drills']} -> {after['drills']}
- Диагностика: {before['diagnostic']} -> {after['diagnostic']}
"""
    (docs_dir / "beginner_content_v15_9.md").write_text(md, encoding="utf-8")


def update_project_files(root):
    package_path = root / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = "15.9.0"
    package["description"] = "Deutsch A0-B2 Tutor v15.9 with expanded beginner vocabulary, lessons, review and MP3 coverage"
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readme = root / "README.md"
    readme_text = readme.read_text(encoding="utf-8")
    if "v15.9 beginner content expansion" not in readme_text:
        readme_text += (
            "\n\n## v15.9 beginner content expansion\n\n"
            "- Added practical A0 vocabulary for objects, family, food, city directions, body, common verbs, adjectives and survival phrases.\n"
            "- Added new A0/A1 lessons with examples, Russian-speaker traps, mini tables, visual schemes and drills.\n"
            "- Added more A0/A1 diagnostic checks and review material.\n"
            "- Generated neural MP3 coverage for new German words and phrases.\n"
            "- Added diagnostic report: `data/beginner_content_v15_9.json` and `docs/diagnostics/beginner_content_v15_9.md`.\n"
        )
        readme.write_text(readme_text, encoding="utf-8")

    worklog = root / "WORKLOG.md"
    worklog_text = worklog.read_text(encoding="utf-8")
    if "v15.9 beginner content expansion" not in worklog_text:
        worklog_text += (
            "\n\n## v15.9 beginner content expansion\n\n"
            "- Expanded beginner material for a learner starting from zero.\n"
            "- Added common A0/A1 words, phrases, practical lessons, repetitions and diagnostic checks.\n"
            "- Kept the content Russian-speaker oriented: articles, V2, fixed phrases and common transfer traps.\n"
            "- Rebuilt full neural audio manifest after MP3 generation.\n"
        )
        worklog.write_text(worklog_text, encoding="utf-8")


def main():
    root = Path(__file__).resolve().parents[1]
    index, text, match, data = load_app(root)
    before = stats(data)

    data["version"] = VERSION
    data["date"] = DATE
    added = {
        "lessons": add_lessons(data),
        "vocab": add_vocab_items(data),
        "diagnostic": add_diagnostic_questions(data),
    }

    after = stats(data)
    save_app(index, text, match, data)
    write_reports(root, before, after, added)
    update_project_files(root)
    print(json.dumps({"version": VERSION, "before": before, "after": after, "added": added}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
