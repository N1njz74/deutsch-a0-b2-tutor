import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import argparse

def esc_repl_version(text, version):
    text = re.sub(r'("version"\s*:\s*")v\d+\.\d+(")', rf'\1{version}\2', text, count=1)
    text = re.sub(r'<b>Версия v\d+\.\d+\.</b>', f'<b>Версия {version}.</b>', text)
    return text

def classify(lesson):
    tags = set(lesson.get("tags") or [])
    title = (lesson.get("title") or "").lower()
    rule = (lesson.get("rule") or "").lower()
    module = (lesson.get("module") or "").lower()
    blob = " ".join([title, rule, module, " ".join(tags)])

    def has(*words):
        return any(w in blob for w in words)

    if has("pronunciation", "произнош", "алфавит", "умлаут", "ß"):
        return "pronunciation"
    if has("word-order", "порядок", "v2", "verbposition", "рамка"):
        return "word_order"
    if has("question", "вопрос", "ja/nein", "w-вопрос", "indirekte"):
        return "questions"
    if has("article", "артик", "nominativ", "der/die/das"):
        return "articles"
    if has("case", "akkusativ", "dativ", "genitiv", "падеж"):
        return "cases"
    if has("negation", "nicht", "kein", "отриц"):
        return "negation"
    if has("modal", "модаль", "müssen", "können", "möchten", "dürfen", "sollen"):
        return "modal"
    if has("separable", "отделяем", "trennbare", "anrufen", "aufstehen"):
        return "separable"
    if has("imperative", "imperativ", "императив"):
        return "imperative"
    if has("past", "perfekt", "präteritum", "praeteritum", "plusquamperfekt", "времена"):
        return "past"
    if has("clause", "clauses", "придат", "weil", "dass", "wenn", "obwohl", "damit", "um…zu", "um...zu"):
        return "clauses"
    if has("adjective", "adjektiv", "прилагательн", "окончан"):
        return "adjectives"
    if has("pronoun", "местоим", "da-/wo", "darauf", "womit"):
        return "pronouns"
    if has("passive", "passiv", "пассив", "werden + partizip"):
        return "passive"
    if has("konjunktiv", "kii", "ki", "косвенная речь"):
        return "konjunktiv"
    if has("preposition", "предлог", "управление", "collocation", "коллокац"):
        return "prepositions"
    if has("connector", "связк", "argumentation", "аргументац", "kohärenz"):
        return "connectors"
    if has("writing", "письмо", "formal", "официаль", "register", "style", "стиль", "жалоба", "bewerbung"):
        return "writing"
    if has("nominal", "nominalstil", "номинал"):
        return "nominal"
    if has("medical", "medizin", "медицин", "клиник", "patient", "aufklärung"):
        return "medical"
    if has("swiss", "schweiz", "швейцар", "krankenkasse", "spital"):
        return "swiss"
    if has("surgery", "chirurgie", "пластическ", "эстетическ"):
        return "surgery"
    if has("строительство", "акз", "beschichtung", "korrosionsschutz", "baustelle"):
        return "akz"
    if has("speaking", "говорение", "mündlich", "muendlich"):
        return "speaking"
    return "default"

TEMPLATES = {}

TEMPLATES["pronunciation"] = {
    "theory": "Русскоговорящему важно сразу отделить немецкое чтение от английского и русского. Немецкий в основном читается стабильнее английского, но есть группы букв, которые нельзя читать по-русски: ei = ай, ie = долгое и, sch = ш, sp/st в начале часто шп/шт.",
    "trap": "Ловушка: видеть латинские буквы и читать их как английские или русские. Например mein — не «меин», а примерно «майн».",
    "logic": "Немецкая логика: сначала выучи устойчивые буквосочетания, потом слово читается почти механически.",
    "formula": "буква/сочетание → звук → пример: ei → ай → mein; sch → ш → Deutsch",
    "mistakes": ["читать ei как «еи»", "произносить sch как «сх»", "игнорировать умлауты ä/ö/ü"],
    "tables": [
        ["Главные сочетания", ["Сочетание", "Звук", "Пример"], [
            ["ei", "ай", "mein, nein"],
            ["ie", "долгое и", "Liebe, sie"],
            ["sch", "ш", "Deutsch, sprechen"],
            ["sp/st в начале", "шп/шт", "sprechen, stehen"]
        ]],
        ["Умлауты", ["Буква", "Ориентир для русского", "Пример"], [
            ["ä", "между э/е", "spät"],
            ["ö", "округлённый э", "schön"],
            ["ü", "округлённый и", "Tür"],
            ["ß", "долгое/глухое с", "Straße"]
        ]]
    ]
}

TEMPLATES["word_order"] = {
    "theory": "Русский порядок слов свободнее: «Сегодня я учу немецкий» и «Я сегодня учу немецкий» звучат нормально. В немецком спрягаемый глагол — якорь предложения. В обычном утверждении он стоит на позиции 2, даже если первым стоит время, место или причина.",
    "trap": "Ловушка: переносить русский порядок напрямую: Heute ich lerne Deutsch. Немцу это ломает грамматику, потому что после Heute должен идти глагол.",
    "logic": "Немецкая логика: первое поле можно менять для акцента, но второе место закреплено за спрягаемым глаголом.",
    "formula": "Поле 1 + Verb 2 + субъект + остальное: Heute lerne ich Deutsch.",
    "mistakes": ["Heute ich lerne Deutsch", "Weil ich habe Zeit", "ставить два элемента перед глаголом"],
    "tables": [
        ["V2 в главном предложении", ["Тип", "Правильно", "Почему"], [
            ["Обычно", "Ich lerne Deutsch.", "глагол lerne на позиции 2"],
            ["Время первым", "Heute lerne ich Deutsch.", "Heute = поле 1, lerne = V2"],
            ["Место первым", "In Frankfurt wohne ich.", "место в поле 1, глагол остаётся вторым"]
        ]],
        ["Где стоит глагол", ["Конструкция", "Позиция глагола", "Пример"], [
            ["Главное предложение", "2", "Ich lerne Deutsch."],
            ["Ja/Nein-вопрос", "1", "Haben Sie Zeit?"],
            ["W-вопрос", "2", "Wo wohnen Sie?"],
            ["Придаточное", "в конце", "..., weil ich Zeit habe."]
        ]]
    ]
}

TEMPLATES["questions"] = {
    "theory": "В русском вопрос часто делается интонацией: «У вас есть время?» В немецком порядок слов показывает тип вопроса. Если вопрос без вопросительного слова, глагол идёт первым. Если есть W-слово, оно первое, глагол второй.",
    "trap": "Ловушка: говорить Sie haben Zeit? как основной учебный вариант. Это возможно интонационно, но стандартный грамматический вопрос: Haben Sie Zeit?",
    "logic": "Немецкий вопрос строится через позицию глагола, а не только через интонацию.",
    "formula": "Ja/Nein: Verb + Subjekt + ...? W-Frage: W-Wort + Verb + Subjekt + ...?",
    "mistakes": ["Sie haben Zeit? вместо Haben Sie Zeit?", "Wo Sie wohnen?", "Wann der Termin ist? как прямой вопрос"],
    "tables": [
        ["Типы вопросов", ["Тип", "Шаблон", "Пример"], [
            ["Ja/Nein", "Verb + Subjekt", "Haben Sie Zeit?"],
            ["W-Frage", "Wort + Verb + Subjekt", "Wo wohnen Sie?"],
            ["Косвенный вопрос", "..., W/ob + ... + Verb", "Können Sie sagen, wann der Termin ist?"]
        ]]
    ]
}

TEMPLATES["articles"] = {
    "theory": "В русском нет артиклей, поэтому русскоговорящий часто хочет учить только слово. В немецком это ошибка: существительное надо учить вместе с der/die/das, потому что род влияет на Akkusativ, Dativ, Genitiv и окончания прилагательных.",
    "trap": "Ловушка: учить Termin без der. Потом сложно понять, почему einen Termin, mit dem Termin, wegen des Termins.",
    "logic": "Артикль — это не украшение, а грамматическая метка рода, числа и падежа.",
    "formula": "слово = артикль + существительное + пример: der Termin — Ich habe einen Termin.",
    "mistakes": ["учить слово без артикля", "путать der/die/das", "не менять мужской род в Akkusativ"],
    "tables": [
        ["Артикли в Nominativ", ["Род/число", "Определённый", "Неопределённый", "Пример"], [
            ["мужской", "der", "ein", "der Termin / ein Termin"],
            ["женский", "die", "eine", "die Frage / eine Frage"],
            ["средний", "das", "ein", "das Formular / ein Formular"],
            ["множественное", "die", "-", "die Unterlagen"]
        ]],
        ["Мини-логика артикля", ["Функция", "Что показывает", "Почему важно"], [
            ["род", "der/die/das", "влияет на падеж"],
            ["падеж", "den/dem/des...", "показывает роль слова"],
            ["число", "die Plural", "множественное часто отличается"]
        ]]
    ]
}

TEMPLATES["cases"] = {
    "theory": "В русском падежи часто видны по окончанию слова. В немецком главную работу часто делает артикль: der Mann, den Mann, dem Mann, des Mannes. Поэтому нельзя переводить только по смыслу — нужно видеть роль слова в предложении.",
    "trap": "Ловушка: думать «мужчина — der Mann всегда». Но после sehen будет Ich sehe den Mann, а после mit — mit dem Mann.",
    "logic": "Немецкий падеж отвечает на роль: кто действует, кого/что затронули, кому/где/с кем, чей/из-за чего.",
    "formula": "Nominativ = кто? Akkusativ = кого/что? Dativ = кому/где/с кем? Genitiv = чей/из-за чего?",
    "mistakes": ["der Mann после sehen", "mit den Bus вместо mit dem Bus", "wegen dem Problem в формальном письме"],
    "tables": [
        ["Артикли по падежам", ["Падеж", "муж.", "жен.", "сред.", "мн."], [
            ["Nominativ", "der/ein", "die/eine", "das/ein", "die/-"],
            ["Akkusativ", "den/einen", "die/eine", "das/ein", "die/-"],
            ["Dativ", "dem/einem", "der/einer", "dem/einem", "den + -n"],
            ["Genitiv", "des/eines", "der/einer", "des/eines", "der/-"]
        ]],
        ["Роль падежа", ["Падеж", "Вопрос", "Пример"], [
            ["Nominativ", "кто/что?", "Der Arzt hilft."],
            ["Akkusativ", "кого/что?", "Ich sehe den Arzt."],
            ["Dativ", "кому/с кем/где?", "Ich helfe dem Patienten."],
            ["Genitiv", "чей/из-за чего?", "wegen des Problems"]
        ]]
    ]
}

TEMPLATES["negation"] = {
    "theory": "Русское «не/нет» часто переводится двумя немецкими инструментами: nicht и kein. Kein отрицает существительное с неопределённым артиклем или без артикля. Nicht отрицает глагол, прилагательное, обстоятельство или всю мысль.",
    "trap": "Ловушка: говорить Ich habe nicht Termin. Если имеется в виду «нет записи», нужно keinen Termin.",
    "logic": "Немецкий выбирает отрицание по тому, что именно отрицается: предмет или действие/качество.",
    "formula": "kein + существительное; nicht + глагол/прилагательное/фраза.",
    "mistakes": ["Ich habe nicht Termin", "Ich verstehe kein", "Das ist kein teuer"],
    "tables": [
        ["nicht или kein", ["Что отрицаем", "Немецкий", "Пример"], [
            ["существительное", "kein", "Ich habe keinen Termin."],
            ["глагол", "nicht", "Ich komme nicht."],
            ["прилагательное", "nicht", "Das ist nicht teuer."],
            ["вся мысль", "nicht", "Ich verstehe das nicht."]
        ]]
    ]
}

TEMPLATES["verbs"] = {
    "theory": "В немецком личная форма глагола обязательна. Русский часто позволяет опускать или свободно менять форму, но немецкий требует точного окончания: ich lerne, du lernst, er lernt.",
    "trap": "Ловушка: говорить du lernen или ich wohnen. В немецком окончание показывает лицо.",
    "logic": "Глагол согласуется с подлежащим и держит структуру предложения.",
    "formula": "основа + окончание: lern- + e/st/t/en/t/en",
    "mistakes": ["du lernen", "ich wohnt", "wir macht"],
    "tables": [
        ["Präsens регулярного глагола", ["Лицо", "lernen", "окончание"], [
            ["ich", "lerne", "-e"],
            ["du", "lernst", "-st"],
            ["er/sie/es", "lernt", "-t"],
            ["wir", "lernen", "-en"],
            ["ihr", "lernt", "-t"],
            ["sie/Sie", "lernen", "-en"]
        ]]
    ]
}

TEMPLATES["modal"] = {
    "theory": "Модальный глагол в немецком занимает место спрягаемого глагола, а смысловой глагол уходит в конец в инфинитиве. Для русского это непривычно: «я должен сегодня работать» → Ich muss heute arbeiten.",
    "trap": "Ловушка: Ich muss heute arbeite. После модального нужен инфинитив arbeiten.",
    "logic": "Модальный глагол открывает рамку, инфинитив закрывает рамку.",
    "formula": "Subjekt + Modalverb + ... + Infinitiv",
    "mistakes": ["Ich muss arbeite", "Ich heute muss arbeiten", "Ich möchte einen Termin vereinbare"],
    "tables": [
        ["Модальные глаголы", ["Глагол", "Смысл", "Пример"], [
            ["können", "мочь/уметь", "Ich kann kommen."],
            ["müssen", "должен", "Ich muss arbeiten."],
            ["wollen", "хотеть", "Ich will lernen."],
            ["möchten", "хотел бы", "Ich möchte einen Termin."],
            ["dürfen", "можно/иметь разрешение", "Darf ich fragen?"],
            ["sollen", "следует/должен по поручению", "Sie sollen warten."]
        ]]
    ]
}

TEMPLATES["separable"] = {
    "theory": "Отделяемые глаголы — типичная немецкая рамка. В словаре глагол пишется вместе: anrufen. В обычной фразе приставка уходит в конец: Ich rufe dich an.",
    "trap": "Ловушка: Ich anrufe dich. В главном предложении приставка отделяется.",
    "logic": "Спрягается основная часть, приставка закрывает смысл в конце.",
    "formula": "anrufen → Ich rufe ... an",
    "mistakes": ["Ich anrufe dich", "Ich rufe dich auf вместо an", "zu anrufen вместо anzurufen"],
    "tables": [
        ["Отделяемый глагол", ["Форма", "Пример", "Комментарий"], [
            ["Infinitiv", "anrufen", "словарная форма"],
            ["Präsens", "Ich rufe dich an.", "приставка в конце"],
            ["Perfekt", "Ich habe angerufen.", "ge между приставкой и основой"],
            ["zu + Infinitiv", "anzurufen", "zu внутри"]
        ]]
    ]
}

TEMPLATES["imperative"] = {
    "theory": "Императив в немецком зависит от того, к кому обращаются. Для незнакомого человека безопаснее форма с Sie: Kommen Sie bitte. Для du — Komm bitte.",
    "trap": "Ловушка: использовать грубую команду без bitte или путать du/Sie.",
    "logic": "Форма императива показывает дистанцию и вежливость.",
    "formula": "Sie: Verb + Sie + bitte. Du: Verbstamm + bitte.",
    "mistakes": ["Komm Sie", "Sie kommen bitte как команда", "Mach sofort в официальной ситуации"],
    "tables": [
        ["Императив", ["Адресат", "Форма", "Пример"], [
            ["Sie", "Verb + Sie", "Warten Sie bitte."],
            ["du", "основа", "Komm bitte."],
            ["ihr", "-t", "Macht bitte die Übung."]
        ]]
    ]
}

TEMPLATES["past"] = {
    "theory": "Русский прошедшее время часто проще: сделал/был/ходил. В немецком нужно выбрать конструкцию: Perfekt для разговорного прошлого, Präteritum часто для sein/haben/modal и письменного стиля, Plusquamperfekt для более раннего прошлого.",
    "trap": "Ловушка: всегда использовать haben. Движение с изменением места часто требует sein: Ich bin gegangen.",
    "logic": "Немецкое прошедшее выбирается не только по времени, но и по стилю.",
    "formula": "Perfekt = haben/sein + Partizip II",
    "mistakes": ["ich habe gegangen", "ich bin gelernt", "Partizip II не в конце"],
    "tables": [
        ["Прошедшие формы", ["Форма", "Когда", "Пример"], [
            ["Perfekt", "разговорное прошлое", "Ich habe gelernt."],
            ["Perfekt с sein", "движение/изменение состояния", "Ich bin gekommen."],
            ["Präteritum", "sein/haben/modal, письменный стиль", "Ich war krank."],
            ["Plusquamperfekt", "раньше другого прошлого", "Nachdem ich gekommen war..."]
        ]]
    ]
}

TEMPLATES["clauses"] = {
    "theory": "Русский часто сохраняет привычный порядок слов после «потому что/что/если». В немецком подчинительный союз отправляет спрягаемый глагол в конец: weil ich Zeit habe.",
    "trap": "Ловушка: weil ich habe Zeit. Это русская логика порядка слов, но не немецкая.",
    "logic": "Придаточное предложение в немецком закрывается глаголом.",
    "formula": "weil/dass/wenn/obwohl + подлежащее + ... + Verb",
    "mistakes": ["weil ich habe Zeit", "dass er kommt heute", "wenn ich habe Zeit"],
    "tables": [
        ["Союзы и порядок слов", ["Союз", "Смысл", "Порядок"], [
            ["weil", "потому что", "глагол в конце"],
            ["dass", "что", "глагол в конце"],
            ["wenn", "если/когда", "глагол в конце"],
            ["obwohl", "хотя", "глагол в конце"],
            ["ob", "ли", "глагол в конце"]
        ]],
        ["Цель", ["Конструкция", "Когда", "Пример"], [
            ["um ... zu", "один субъект", "Ich lerne, um besser zu sprechen."],
            ["damit", "разные субъекты", "Ich erkläre es, damit du es verstehst."]
        ]]
    ]
}

TEMPLATES["adjectives"] = {
    "theory": "Окончания прилагательных — одна из главных зон риска для русскоговорящих. В немецком окончание зависит от рода, числа, падежа и артикля. Не нужно угадывать — нужно видеть систему.",
    "trap": "Ловушка: везде ставить gute/guten. Например ein guter Plan, eine gute Idee, ein gutes Beispiel.",
    "logic": "Если артикль уже показывает род/падеж, прилагательное несёт меньше информации. Если артикль слабый или его нет, прилагательное несёт больше.",
    "formula": "артикль + прилагательное + существительное; окончание зависит от грамматической информации.",
    "mistakes": ["ein gute Plan", "mit gutem Grund забывать Dativ", "die langfristige Folgen вместо langfristigen"],
    "tables": [
        ["После ein-слов", ["Род/падеж", "Пример", "Почему"], [
            ["муж. Nom.", "ein guter Plan", "прилагательное показывает мужской род"],
            ["жен. Nom.", "eine gute Idee", "женский род уже виден"],
            ["сред. Nom.", "ein gutes Beispiel", "прилагательное показывает средний род"],
            ["Dativ", "mit einem guten Arzt", "после Dativ часто -en"]
        ]],
        ["После der-слов", ["Форма", "Пример", "Комментарий"], [
            ["der", "der gute Plan", "слабое окончание"],
            ["die", "die gute Idee", "слабое окончание"],
            ["das", "das gute Beispiel", "слабое окончание"],
            ["Plural", "die guten Beispiele", "часто -en"]
        ]]
    ]
}

TEMPLATES["pronouns"] = {
    "theory": "Местоимения в немецком меняются по падежам. Русскому это знакомо по смыслу: я/меня/мне. Но формы нужно автоматизировать: ich/mich/mir, er/ihn/ihm.",
    "trap": "Ловушка: использовать ich вместо mich/mir после глагола или предлога.",
    "logic": "Местоимение показывает роль человека или предмета в предложении.",
    "formula": "Nominativ: ich; Akkusativ: mich; Dativ: mir",
    "mistakes": ["Ich sehe er", "Hilfst du ich?", "mit sie вместо mit ihr"],
    "tables": [
        ["Личные местоимения", ["Nominativ", "Akkusativ", "Dativ"], [
            ["ich", "mich", "mir"],
            ["du", "dich", "dir"],
            ["er", "ihn", "ihm"],
            ["sie", "sie", "ihr"],
            ["wir", "uns", "uns"]
        ]],
        ["da-/wo-композиты", ["Предлог + вещь", "Форма", "Пример"], [
            ["auf + das", "darauf", "Ich warte darauf."],
            ["über + das", "darüber", "Wir sprechen darüber."],
            ["mit + was", "womit", "Womit lässt sich das erklären?"]
        ]]
    ]
}

TEMPLATES["passive"] = {
    "theory": "В русском можно сказать «заявление проверяют» без указания исполнителя. В немецком для этого часто используется Passiv: Der Antrag wird geprüft. Это особенно важно в официальном стиле.",
    "trap": "Ловушка: пытаться всегда переводить через man. Man prüft den Antrag возможно, но Passiv звучит официальнее и нейтральнее.",
    "logic": "Passiv ставит действие в центр, а исполнителя убирает или делает второстепенным.",
    "formula": "werden + Partizip II: wird geprüft; wurde geprüft; ist geprüft worden",
    "mistakes": ["Der Antrag ist prüfen", "wurde gepruft без Partizip II", "путать Zustandspassiv и Vorgangspassiv"],
    "tables": [
        ["Passiv", ["Время/тип", "Форма", "Пример"], [
            ["Präsens", "wird + Partizip II", "Der Antrag wird geprüft."],
            ["Präteritum", "wurde + Partizip II", "Der Antrag wurde geprüft."],
            ["Perfekt", "ist + Partizip II + worden", "Der Antrag ist geprüft worden."],
            ["Zustand", "sein + Partizip II", "Die Praxis ist geschlossen."]
        ]],
        ["Замены Passiv", ["Конструкция", "Смысл", "Пример"], [
            ["man", "кто-то делает", "Man prüft den Antrag."],
            ["sich lassen", "можно сделать", "Das lässt sich lösen."],
            ["sein + zu", "нужно сделать", "Der Antrag ist zu prüfen."],
            ["-bar", "возможно", "verständlich, lösbar"]
        ]]
    ]
}

TEMPLATES["konjunktiv"] = {
    "theory": "Konjunktiv — это не просто «сослагательное наклонение». Для B1/B2 важны две функции: Konjunktiv II для вежливости/условности и Konjunktiv I для косвенной речи.",
    "trap": "Ловушка: переводить würde как отдельное слово «бы» и забывать инфинитив в конце.",
    "logic": "Konjunktiv меняет дистанцию: делает высказывание вежливым, гипотетическим или переданным со слов другого человека.",
    "formula": "KII: würde + Infinitiv / hätte / wäre / könnte. KI: er habe, sie sei.",
    "mistakes": ["ich würde gemacht", "er hat gesagt, er hat... вместо er habe", "Können Sie sofort! вместо Könnten Sie..."],
    "tables": [
        ["Konjunktiv II", ["Функция", "Форма", "Пример"], [
            ["вежливость", "könnte", "Könnten Sie mir helfen?"],
            ["условие", "wäre/hätte", "Wenn ich Zeit hätte..."],
            ["предложение", "würde + Infinitiv", "Ich würde mehr üben."]
        ]],
        ["Konjunktiv I", ["Обычная форма", "Косвенная речь", "Пример"], [
            ["er hat", "er habe", "Er sagte, er habe keine Zeit."],
            ["sie ist", "sie sei", "Sie erklärte, die Maßnahme sei notwendig."],
            ["sie müssen", "sie müssten", "если KI совпадает, часто KII"]
        ]]
    ]
}

TEMPLATES["prepositions"] = {
    "theory": "Предлоги в немецком жёстко управляют падежом. Русский перевод часто не помогает. Нужно учить блок: mit + Dativ, für + Akkusativ, aufgrund + Genitiv.",
    "trap": "Ловушка: выбирать падеж по русскому переводу. Например «с автобусом» не помогает — mit всегда требует Dativ.",
    "logic": "Предлог заранее задаёт форму артикля и местоимения.",
    "formula": "предлог + падеж: mit dem Bus, für den Termin, wegen des Problems",
    "mistakes": ["mit den Bus", "für dem Termin", "aufgrund die Kosten"],
    "tables": [
        ["Предлоги по падежам", ["Akkusativ", "Dativ", "Genitiv"], [
            ["durch", "aus", "aufgrund"],
            ["für", "bei", "wegen"],
            ["gegen", "mit", "trotz"],
            ["ohne", "nach", "während"],
            ["um", "zu", "hinsichtlich"]
        ]]
    ]
}

TEMPLATES["connectors"] = {
    "theory": "Связки в немецком опасны тем, что меняют порядок слов. Русскоговорящий часто переводит связку и сохраняет русский порядок. В немецком важно знать: связка занимает позицию или нет.",
    "trap": "Ловушка: Deshalb ich lerne Deutsch. После deshalb сразу глагол: Deshalb lerne ich Deutsch.",
    "logic": "Связки делятся на 0-позицию, 1-позицию и подчинительные союзы.",
    "formula": "deshalb/trotzdem/dennoch + Verb + Subjekt; weil/dass/obwohl + ... + Verb",
    "mistakes": ["Deshalb ich lerne", "Obwohl es ist schwierig", "Denn требует глагол в конец"],
    "tables": [
        ["Связки и позиция", ["Тип", "Связки", "Порядок"], [
            ["0-позиция", "und, aber, denn, sondern, oder", "после них обычный порядок"],
            ["1-позиция", "deshalb, trotzdem, dennoch, folglich", "сразу V2"],
            ["подчинительные", "weil, dass, obwohl, während, sofern", "глагол в конце"]
        ]]
    ]
}

TEMPLATES["writing"] = {
    "theory": "Для русскоговорящего письмо на немецком сложно не только грамматикой, но и регистром. Немецкое официальное письмо требует ясной структуры, нейтрального тона и точных просьб.",
    "trap": "Ловушка: писать слишком эмоционально или слишком прямо, как в устном русском. В немецком официальном стиле лучше спокойная формула.",
    "logic": "Официальное письмо — это не художественный текст, а управляемая структура: причина, факт, просьба, срок, финал.",
    "formula": "Anrede → Grund → Details → Bitte/Forderung → Frist → Schlussformel",
    "mistakes": ["Hallo в официальном письме", "Mach schnell", "слишком длинное предложение без структуры"],
    "tables": [
        ["Официальное письмо", ["Часть", "Фраза", "Задача"], [
            ["Обращение", "Sehr geehrte Damen und Herren,", "безопасный старт"],
            ["Причина", "Ich wende mich an Sie, weil...", "объяснить цель"],
            ["Просьба", "Ich bitte um Rückmeldung.", "сказать, что нужно"],
            ["Срок", "bis zum 15. August", "дать рамку"],
            ["Финал", "Mit freundlichen Grüßen", "официально закрыть"]
        ]]
    ]
}

TEMPLATES["nominal"] = {
    "theory": "Nominalstil делает немецкий текст официальнее: глагольное действие превращается в существительное. Русскому ученику важно не перегрузить текст: официальность не должна убивать ясность.",
    "trap": "Ловушка: превращать всё в тяжёлые существительные. На B2 достаточно использовать Nominalstil точечно.",
    "logic": "Nominalstil сжимает информацию и подходит для документов, писем, отчётов.",
    "formula": "weil wir prüfen → nach Prüfung; damit wir klären → zur Klärung",
    "mistakes": ["слишком много существительных подряд", "потеря падежа после nominal phrase", "непонятный стиль"],
    "tables": [
        ["Nominalstil", ["Глагольный стиль", "Nominalstil", "Комментарий"], [
            ["wenn wir die Unterlagen prüfen", "nach Prüfung der Unterlagen", "официальнее"],
            ["damit wir die Kosten klären", "zur Klärung der Kosten", "компактнее"],
            ["bevor man den Eingriff durchführt", "vor Durchführung des Eingriffs", "Genitiv"],
            ["wenn Sie Fragen haben", "bei Rückfragen", "канцелярский стиль"]
        ]]
    ]
}

TEMPLATES["medical"] = {
    "theory": "Медицинский немецкий требует нейтральности и точности. Нельзя звучать рекламно или давить на пациента. Важны цель, риск, альтернатива, согласие и Nachsorge.",
    "trap": "Ловушка: переводить медицинские фразы буквально с русского и терять нейтральный тон.",
    "logic": "В медицине грамматика служит ясности: кто информирует, о чём, какие риски, какое согласие.",
    "formula": "über Risiken aufklären → Einwilligung einholen → Nachsorge planen",
    "mistakes": ["рекламный стиль вместо нейтрального", "не различать Aufklärung и Einwilligung", "не указывать риски"],
    "tables": [
        ["Медицинская консультация", ["Этап", "Немецкая формула", "Смысл"], [
            ["Анамнез", "die Anamnese erheben", "собрать историю"],
            ["Объяснение", "über Risiken aufklären", "информировать о рисках"],
            ["Согласие", "eine Einwilligung einholen", "получить согласие"],
            ["Контроль", "die Nachsorge planen", "спланировать наблюдение"]
        ]]
    ]
}

TEMPLATES["swiss"] = {
    "theory": "Швейцарский немецкий в официальных текстах часто использует слова, отличающиеся от Германии: Spital, Offerte, Entscheid, parkieren. При этом грамматика официального письма остаётся стандартной.",
    "trap": "Ловушка: думать, что все слова как в Германии. В Швейцарии часть административной и медицинской лексики другая.",
    "logic": "Для Швейцарии нужно узнавать региональные слова, но писать нейтральным стандартным немецким.",
    "formula": "Termin bestätigen → Offerte prüfen → Kostenübernahme klären",
    "mistakes": ["не узнавать Spital", "путать Franchise и Prämie", "писать слишком разговорно"],
    "tables": [
        ["Швейцарские слова", ["Швейцария", "Германия/смысл", "Комментарий"], [
            ["das Spital", "das Krankenhaus", "больница"],
            ["die Offerte", "das Angebot", "смета/предложение"],
            ["der Entscheid", "die Entscheidung", "решение"],
            ["parkieren", "parken", "парковать"]
        ]]
    ]
}

TEMPLATES["surgery"] = {
    "theory": "В теме пластической хирургии важно говорить нейтрально: не обещать результат, не рекламировать, не давить. Для B2 нужны слова риска, ожиданий, согласия и послеоперационного ухода.",
    "trap": "Ловушка: использовать рекламный стиль вместо медицински нейтрального.",
    "logic": "Немецкий формальный стиль здесь защищает ясность: риски, ограничения, реалистичные ожидания.",
    "formula": "Risiken erläutern → Erwartungen klären → Einwilligung unterschreiben → Nachbehandlung planen",
    "mistakes": ["гарантировать результат", "игнорировать Risiken", "смешивать Beratung и Werbung"],
    "tables": [
        ["Пластическая хирургия", ["Тема", "Немецкий термин", "Смысл"], [
            ["Риск", "mögliche Komplikationen", "возможные осложнения"],
            ["Ожидания", "realistische Erwartungen", "реалистичные ожидания"],
            ["Согласие", "die Einwilligung", "согласие"],
            ["После", "die Nachbehandlung", "послеоперационное лечение"]
        ]]
    ]
}

TEMPLATES["akz"] = {
    "theory": "В строительстве и АКЗ нужна точная предметная лексика: подготовка поверхности, толщина слоя, адгезия, дефект, протокол. Для B2 важно уметь описать проблему нейтрально и документально.",
    "trap": "Ловушка: говорить общими словами «плохо сделано». В немецком рабочем отчёте нужны измеримые факты.",
    "logic": "Технический немецкий строится вокруг объекта, дефекта, причины, меры и документации.",
    "formula": "Mangel feststellen → Ursache beschreiben → Nachbesserung fordern → Prüfprotokoll erstellen",
    "mistakes": ["без точных терминов", "нет причины дефекта", "нет требования Nachbesserung"],
    "tables": [
        ["АКЗ/строительство", ["Русский смысл", "Немецкий термин", "Пример"], [
            ["металлоконструкция", "die Stahlkonstruktion", "die Stahlkonstruktion prüfen"],
            ["антикоррозионная защита", "der Korrosionsschutz", "Korrosionsschutz auftragen"],
            ["толщина слоя", "die Schichtdicke", "Schichtdicke messen"],
            ["исправление", "die Nachbesserung", "Nachbesserung verlangen"]
        ]]
    ]
}

TEMPLATES["speaking"] = {
    "theory": "Говорение на B1/B2 требует не скорости, а структуры. Русскоговорящий часто пытается сразу сказать всё. Лучше говорить блоками: тема, мнение, причина, пример, вывод.",
    "trap": "Ловушка: хаотично перечислять мысли без связок.",
    "logic": "Немецкий экзаменационный ответ оценивает структуру, ясность и реакцию на партнёра.",
    "formula": "Thema → Meinung → Grund → Beispiel → Fazit",
    "mistakes": ["нет структуры", "слишком длинные фразы", "нет вывода"],
    "tables": [
        ["Устный ответ", ["Шаг", "Фраза", "Задача"], [
            ["Тема", "Es geht um...", "назвать тему"],
            ["Мнение", "Meiner Meinung nach...", "дать позицию"],
            ["Причина", "Der Grund dafür ist...", "обосновать"],
            ["Пример", "Zum Beispiel...", "конкретизировать"],
            ["Вывод", "Zusammenfassend...", "закрыть ответ"]
        ]]
    ]
}

TEMPLATES["default"] = {
    "theory": "Для русскоговорящего ученика важно не просто перевести фразу, а понять немецкий механизм: где глагол, какой падеж, какой артикль, какой стиль и почему выбран именно этот вариант.",
    "trap": "Ловушка: переводить слово в слово с русского и сохранять русский порядок слов.",
    "logic": "Немецкий строит смысл через форму: позицию глагола, артикль, падеж, предлог и рамку.",
    "formula": "смысл → грамматическая роль → немецкая форма → пример",
    "mistakes": ["дословный перевод", "пропуск артикля", "русский порядок слов"],
    "tables": [
        ["Мини-чеклист", ["Что проверить", "Вопрос", "Пример"], [
            ["глагол", "где стоит?", "V2 или конец придаточного"],
            ["артикль", "какой род?", "der/die/das"],
            ["падеж", "какая роль?", "Akkusativ/Dativ/Genitiv"],
            ["стиль", "официально или разговорно?", "Sie / du"]
        ]]
    ]
}

# Алиасы
for alias in ["verbs"]:
    TEMPLATES.setdefault(alias, TEMPLATES["default"])

def template_for(lesson):
    key = classify(lesson)
    return TEMPLATES.get(key, TEMPLATES["default"]), key

def ensure_lesson_fields(data):
    stats = {"lessons": 0, "tables": 0, "mistakes": 0, "types": {}}

    for lesson in data.get("lessons", []):
        if not isinstance(lesson, dict):
            continue

        tpl, kind = template_for(lesson)
        stats["types"][kind] = stats["types"].get(kind, 0) + 1

        lesson["deepTheoryRu"] = tpl["theory"]
        lesson["russianTrap"] = tpl["trap"]
        lesson["germanLogic"] = tpl["logic"]
        lesson["formula"] = tpl["formula"]
        lesson["typicalMistakes"] = tpl["mistakes"]

        tables = []
        for title, headers, rows in tpl["tables"]:
            tables.append({"title": title, "headers": headers, "rows": rows})
        lesson["grammarTables"] = tables

        lesson["whyForRussian"] = (
            "Этот блок добавлен специально для русскоговорящего ученика: сначала сравниваем с русской логикой, "
            "потом показываем немецкий механизм и только после этого тренируем форму."
        )

        stats["lessons"] += 1
        stats["tables"] += len(tables)
        stats["mistakes"] += len(tpl["mistakes"])

    return stats

CSS = r'''
/* v153-lesson-theory-css */
.deep-theory{margin:16px 0;display:grid;gap:12px}
.deep-theory details{border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.035);padding:12px}
.deep-theory summary{cursor:pointer;font-weight:800}
.theory-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin-top:10px}
.theory-box{border:1px solid var(--line);border-radius:14px;padding:12px;background:rgba(2,6,23,.32)}
.theory-box h4{margin:0 0 6px}
.formula-line{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;border:1px dashed var(--line);border-radius:12px;padding:9px;background:rgba(96,165,250,.08)}
.grammar-table-wrap{overflow:auto;margin-top:10px;border:1px solid var(--line);border-radius:14px}
.grammar-table{width:100%;border-collapse:collapse;font-size:.93rem}
.grammar-table th,.grammar-table td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
.grammar-table th{background:rgba(96,165,250,.12)}
.mistake-list{margin:8px 0 0;padding-left:20px}
.lesson-nav-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
'''

HELPERS = r'''
    // v153-lesson-deep-theory-render
    function renderGrammarTableV153(t){
      if (!t || !Array.isArray(t.headers) || !Array.isArray(t.rows)) return '';
      return `<div class="grammar-table-wrap">
        <table class="grammar-table">
          <thead><tr>${t.headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead>
          <tbody>${t.rows.map(row => `<tr>${row.map(cell => `<td>${esc(cell)}</td>`).join('')}</tr>`).join('')}</tbody>
        </table>
      </div>`;
    }

    function renderLessonDeepTheory(l){
      const tables = Array.isArray(l.grammarTables) ? l.grammarTables : [];
      const mistakes = Array.isArray(l.typicalMistakes) ? l.typicalMistakes : [];
      if (!l.deepTheoryRu && !l.russianTrap && !l.germanLogic && !l.formula && !tables.length && !mistakes.length) return '';

      return `<div class="deep-theory">
        <details open>
          <summary>Подробно для русскоговорящего</summary>
          <div class="theory-grid">
            <div class="theory-box">
              <h4>Что происходит</h4>
              <p>${esc(l.deepTheoryRu || '')}</p>
            </div>
            <div class="theory-box">
              <h4>Русская ловушка</h4>
              <p>${esc(l.russianTrap || '')}</p>
            </div>
            <div class="theory-box">
              <h4>Немецкая логика</h4>
              <p>${esc(l.germanLogic || '')}</p>
            </div>
          </div>
          ${l.formula ? `<p class="formula-line">${esc(l.formula)}</p>` : ''}
          ${l.whyForRussian ? `<p class="muted">${esc(l.whyForRussian)}</p>` : ''}
        </details>

        ${tables.length ? `<details open>
          <summary>Грамматические таблицы</summary>
          ${tables.map(t => `<h4>${esc(t.title || 'Таблица')}</h4>${renderGrammarTableV153(t)}`).join('')}
        </details>` : ''}

        ${mistakes.length ? `<details>
          <summary>Типичные ошибки</summary>
          <ul class="mistake-list">${mistakes.map(m => `<li>${esc(m)}</li>`).join('')}</ul>
        </details>` : ''}
      </div>`;
    }

'''

NEW_RENDER_LESSON = r'''
    function renderLesson(id){
      const l = DATA.lessons.find(x => x.id === id) || nextLesson() || DATA.lessons[0];
      if (!l) return `<section class="panel"><h2>Урок не найден</h2><button class="btn" data-route="path">Вернуться к пути</button></section>`;

      const st = statusOf(l.id);
      const sameLevel = DATA.lessons
        .filter(x => x.level === l.level)
        .sort((a,b) => (a.order || 0) - (b.order || 0));

      const pos = sameLevel.findIndex(x => x.id === l.id);
      const prev = pos > 0 ? sameLevel[pos - 1] : null;
      const next = pos >= 0 && pos < sameLevel.length - 1 ? sameLevel[pos + 1] : null;

      const examples = Array.isArray(l.examples) ? l.examples : [];
      const drills = Array.isArray(l.drills) ? l.drills : [];

      return `<section class="panel lesson-page">
        <div class="section-title">
          <div>
            <div class="badge-row">
              <span class="badge">${esc(l.level)}</span>
              <span class="badge">${esc(l.module || '')}</span>
              ${statusBadge(st)}
            </div>
            <h2>${esc(l.title)}</h2>
            <p class="muted">${esc(l.goal || '')}</p>
          </div>
          <div class="toolbar">
            <button class="btn" data-route="path/${esc(l.level)}">К уровню ${esc(l.level)}</button>
            <button class="btn primary" data-action="mark" data-id="${esc(l.id)}" data-status="learned">✓ изучено</button>
            <button class="btn" data-action="mark" data-id="${esc(l.id)}" data-status="review">Повторить</button>
          </div>
        </div>

        <article class="lesson-card">
          <h3>Короткое правило</h3>
          <p>${esc(l.rule || '')}</p>

          ${renderLessonDeepTheory(l)}

          <h3>Примеры</h3>
          <div class="grid two">
            ${examples.map(ex => `<div class="example">
              <p class="de"><b>${esc(ex.de || '')}</b> ${ex.de ? `<button class="speak" data-speak="${esc(ex.de)}">🔊</button>` : ''}</p>
              <p class="ru">${esc(ex.ru || '')}</p>
            </div>`).join('')}
          </div>

          <h3>Тренировка</h3>
          <div class="grid two">
            ${drills.map((d,i) => `<article class="card">${renderDrill(d, `${l.id}-${i}`)}</article>`).join('')}
          </div>

          <div class="lesson-nav-row">
            ${prev ? `<button class="btn" data-route="lesson/${esc(prev.id)}">← ${esc(prev.title)}</button>` : ''}
            ${next ? `<button class="btn primary" data-route="lesson/${esc(next.id)}">${esc(next.title)} →</button>` : ''}
          </div>
        </article>
      </section>`;
    }

'''

def replace_render_lesson(html_text):
    if "v153-lesson-deep-theory-render" not in html_text:
        marker = "    function renderLesson("
        idx = html_text.find(marker)
        if idx < 0:
            raise RuntimeError("function renderLesson not found for helper insert")
        html_text = html_text[:idx] + HELPERS + "\n" + html_text[idx:]

    start = html_text.find("    function renderLesson(")
    if start < 0:
        raise RuntimeError("function renderLesson not found")

    candidates = []
    for needle in [
        "\n    function renderGrammar",
        "\n    function renderB2Short",
        "\n    function renderVocab",
        "\n    function renderDiagnostic",
        "\n    function renderTrainer",
    ]:
        p = html_text.find(needle, start + 1)
        if p > start:
            candidates.append(p)

    if not candidates:
        raise RuntimeError("Cannot find end of renderLesson function")

    end = min(candidates)
    html_text = html_text[:start] + NEW_RENDER_LESSON + "\n" + html_text[end:]
    return html_text

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
    data["version"] = "v15.3"

    stats = ensure_lesson_fields(data)

    new_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html_text = html_text[:m.start(2)] + new_json + html_text[m.end(2):]

    html_text = esc_repl_version(html_text, "v15.3")

    if "v153-lesson-theory-css" not in html_text:
        html_text = html_text.replace("</style>", CSS + "\n</style>", 1)

    html_text = replace_render_lesson(html_text)

    index.write_text(html_text, encoding="utf-8")

    report = {
        "version": "v15.3",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "purpose": "Expanded lesson theory, Russian-speaker explanations, grammar tables and typical mistakes.",
        "stats": stats,
        "lessonStructure": [
            "Короткое правило",
            "Подробно для русскоговорящего",
            "Русская ловушка",
            "Немецкая логика",
            "Формула",
            "Грамматические таблицы",
            "Типичные ошибки",
            "Примеры",
            "Тренировка"
        ]
    }

    (data_dir / "lesson_theory_tables_v15_3.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()