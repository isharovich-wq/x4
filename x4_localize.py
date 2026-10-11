#!/usr/bin/env python3
"""
x4_localize.py  --  берёт официальные русские названия и описания из файлов игры X4: Foundations
и подставляет их в файлы данных сайта (src/app/shared/services/data/*.ts).

Запуск (из папки проекта x4, через Docker; добавьте --diag, чтобы только перечислить текстовые файлы игры):
  docker run --rm -v "ПУТЬ_К_ИГРЕ:/game:ro" -v "${PWD}:/app" -w /app python:3.12 python x4_localize.py /game

Что делает:
  1. Читает из .cat/.dat игры (и DLC из папки extensions) текстовые файлы t/0001-L044.xml (английский)
     и t/0001-L007.xml (русский).
  2. Строит таблицу "английский текст -> русский текст" (по номерам страниц и записей игры).
  3. Заменяет в data/*.ts поля name: '...' и description: '...', если английский текст найден.
  4. Оригиналы сохраняются как *.orig (скрипт можно запускать повторно), отчёт пишется в x4-localize-report.txt.
Ничего не найденное остаётся по-английски (для модулей есть запасной собственный перевод).
"""
import os, re, sys, glob, json, collections
import xml.etree.ElementTree as ET

EN_ID, RU_ID = 44, 7
DATA_DIR = 'src/app/shared/services/data'

FALLBACK = {
 "Argon Base Connection Structure 01": "Аргонская базовая соединительная конструкция 01",
 "Argon Base Connection Structure 02": "Аргонская базовая соединительная конструкция 02",
 "Argon Base Connection Structure 03": "Аргонская базовая соединительная конструкция 03",
 "Argon Cross Connection Structure 01": "Аргонская крестовая соединительная конструкция 01",
 "Argon Vertical Connection Structure 01": "Аргонская вертикальная соединительная конструкция 01",
 "Argon Vertical Connection Structure 02": "Аргонская вертикальная соединительная конструкция 02",
 "Argon Administrative Centre": "Аргонский административный центр",
 "Argon Disc Defence Platform": "Аргонская дисковая оборонительная платформа",
 "Argon Bridge Defence Platform": "Аргонская мостовая оборонительная платформа",
 "1M6S Standard Dock Area": "Стандартная док-зона 1M6S",
 "1M6S Luxury Dock Area": "Роскошная док-зона 1M6S",
 "1M6S Basic Dock Area": "Базовая док-зона 1M6S",
 "3M6S Standard Dock Area": "Стандартная док-зона 3M6S",
 "3M6S Luxury Dock Area": "Роскошная док-зона 3M6S",
 "3M6S Basic Dock Area": "Базовая док-зона 3M6S",
 "8M Standard Dock Area": "Стандартная док-зона 8M",
 "Argon L Habitat": "Аргонский жилой модуль L",
 "Argon M Habitat": "Аргонский жилой модуль M",
 "Argon S Habitat": "Аргонский жилой модуль S",
 "Argon 3-Dock T Pier": "Аргонский пирс T на 3 дока",
 "Argon 1-Dock Pier": "Аргонский пирс на 1 док",
 "Argon 3-Dock E Pier": "Аргонский пирс E на 3 дока",
 "Food Ration Production": "Производство пайков",
 "Meat Production": "Производство мяса",
 "Argon Medical Supply Production": "Аргонское производство медикаментов",
 "Spacefuel Production": "Производство космотоплива",
 "Wheat Production": "Производство пшеницы",
 "Argon L Container Storage": "Аргонское контейнерное хранилище L",
 "Argon M Container Storage": "Аргонское контейнерное хранилище M",
 "Argon S Container Storage": "Аргонское контейнерное хранилище S",
 "Argon L Liquid Storage": "Аргонское хранилище жидкостей L",
 "Argon M Liquid Storage": "Аргонское хранилище жидкостей M",
 "Argon S Liquid Storage": "Аргонское хранилище жидкостей S",
 "Argon L Solid Storage": "Аргонское хранилище твёрдых грузов L",
 "Argon M Solid Storage": "Аргонское хранилище твёрдых грузов M",
 "Argon S Solid Storage": "Аргонское хранилище твёрдых грузов S",
 "S/M Ship Fabrication Bay": "Сборочный ангар для кораблей S/M",
 "L Ship Fabrication Bay": "Сборочный ангар для кораблей L",
 "XL Ship Fabrication Bay": "Сборочный ангар для кораблей XL",
 "S/M Ship Maintenance Bay": "Ремонтный ангар для кораблей S/M",
 "L Ship Maintenance Bay": "Ремонтный ангар для кораблей L",
 "XL Ship Maintenance Bay": "Ремонтный ангар для кораблей XL",
 "Scrap Processor": "Переработчик металлолома",
 "Advanced Composite Production": "Производство улучшенных композитов",
 "Advanced Electronics Production": "Производство улучшенной электроники",
 "Antimatter Cell Production": "Производство антиматерийных ячеек",
 "Antimatter Converter Production": "Производство антиматерийных преобразователей",
 "Claytronics Production": "Производство клейтроники",
 "Drone Component Production": "Производство компонентов дронов",
 "Energy Cell Production": "Производство энергоячеек",
 "Engine Part Production": "Производство деталей двигателей",
 "Field Coil Production": "Производство катушек поля",
 "Graphene Production": "Производство графена",
 "Hull Part Production": "Производство деталей корпуса",
 "Microchip Production": "Производство микросхем",
 "Missile Component Production": "Производство компонентов ракет",
 "Plasma Conductor Production": "Производство плазменных проводников",
 "Quantum Tube Production": "Производство квантовых трубок",
 "Refined Metal Production": "Производство очищенных металлов",
 "Scanning Array Production": "Производство сканирующих массивов",
 "Scrap Recycler": "Утилизатор металлолома",
 "Shield Component Production": "Производство компонентов щитов",
 "Silicon Wafer Production": "Производство кремниевых пластин",
 "Smart Chip Production": "Производство умных чипов",
 "Spice Production": "Производство специй",
 "Superfluid Coolant Production": "Производство сверхтекучего хладагента",
 "Turret Component Production": "Производство компонентов турелей",
 "Water Production": "Производство воды",
 "Weapon Component Production": "Производство компонентов оружия",
 "Paranid Base Connection Structure 01": "Паранидская базовая соединительная конструкция 01",
 "Paranid Base Connection Structure 02": "Паранидская базовая соединительная конструкция 02",
 "Paranid Base Connection Structure 03": "Паранидская базовая соединительная конструкция 03",
 "Paranid Cross Connection Structure 01": "Паранидская крестовая соединительная конструкция 01",
 "Paranid Cross Connection Structure 02": "Паранидская крестовая соединительная конструкция 02",
 "Paranid Cross Connection Structure 03": "Паранидская крестовая соединительная конструкция 03",
 "Paranid Vertical Connection Structure 01": "Паранидская вертикальная соединительная конструкция 01",
 "Paranid Vertical Connection Structure 02": "Паранидская вертикальная соединительная конструкция 02",
 "Paranid Administrative Centre": "Паранидский административный центр",
 "Paranid Disc Defence Platform": "Паранидская дисковая оборонительная платформа",
 "Paranid Bridge Defence Platform": "Паранидская мостовая оборонительная платформа",
 "Paranid L Dome": "Паранидский купол L",
 "Paranid M Dome": "Паранидский купол M",
 "Paranid S Dome": "Паранидский купол S",
 "Paranid 3-Dock T Pier": "Паранидский пирс T на 3 дока",
 "Paranid 1-Dock Pier": "Паранидский пирс на 1 док",
 "Paranid 3-Dock E Pier": "Паранидский пирс E на 3 дока",
 "Maja Dust Production": "Производство пыли маджа",
 "Maja Snail Production": "Производство улиток маджа",
 "Paranid Medical Supply Production": "Паранидское производство медикаментов",
 "Soja Bean Production": "Производство бобов соджа",
 "Soja Husk Production": "Производство шелухи соджа",
 "Paranid L Container Storage": "Паранидское контейнерное хранилище L",
 "Paranid M Container Storage": "Паранидское контейнерное хранилище M",
 "Paranid S Container Storage": "Паранидское контейнерное хранилище S",
 "Paranid L Liquid Storage": "Паранидское хранилище жидкостей L",
 "Paranid M Liquid Storage": "Паранидское хранилище жидкостей M",
 "Paranid S Liquid Storage": "Паранидское хранилище жидкостей S",
 "Paranid L Solid Storage": "Паранидское хранилище твёрдых грузов L",
 "Paranid M Solid Storage": "Паранидское хранилище твёрдых грузов M",
 "Paranid S Solid Storage": "Паранидское хранилище твёрдых грузов S",
 "Teladi Base Connection Structure 01": "Теладийская базовая соединительная конструкция 01",
 "Teladi Base Connection Structure 02": "Теладийская базовая соединительная конструкция 02",
 "Teladi Base Connection Structure 03": "Теладийская базовая соединительная конструкция 03",
 "Teladi Cross Connection Structure 01": "Теладийская крестовая соединительная конструкция 01",
 "Teladi Vertical Connection Structure 01": "Теладийская вертикальная соединительная конструкция 01",
 "Teladi Vertical Connection Structure 02": "Теладийская вертикальная соединительная конструкция 02",
 "Teladi Administrative Centre": "Теладийский административный центр",
 "Teladi Disc Defence Platform": "Теладийская дисковая оборонительная платформа",
 "Teladi Bridge Defence Platform": "Теладийская мостовая оборонительная платформа",
 "Teladi L Biome": "Теладийский биом L",
 "Teladi M Biome": "Теладийский биом M",
 "Teladi S Biome": "Теладийский биом S",
 "Teladi 3-Dock T Pier": "Теладийский пирс T на 3 дока",
 "Teladi 1-Dock Pier": "Теладийский пирс на 1 док",
 "Teladi 3-Dock E Pier": "Теладийский пирс E на 3 дока",
 "Teladi Advanced Composite Production": "Теладийское производство улучшенных композитов",
 "Teladi Engine Part Production": "Теладийское производство деталей двигателей",
 "Teladi Hull Part Production": "Теладийское производство деталей корпуса",
 "Teladi Medical Supply Production": "Теладийское производство медикаментов",
 "Nostrop Oil Production": "Производство нострокского масла",
 "Teladi Scanning Array Production": "Теладийское производство сканирующих массивов",
 "Spaceweed Production": "Производство космической травы",
 "Sunrise Flower Production": "Производство цветов рассвета",
 "Swamp Plant Production": "Производство болотных растений",
 "Teladianium Production": "Производство теладианиума",
 "Teladi L Container Storage": "Теладийское контейнерное хранилище L",
 "Teladi M Container Storage": "Теладийское контейнерное хранилище M",
 "Teladi S Container Storage": "Теладийское контейнерное хранилище S",
 "Teladi L Liquid Storage": "Теладийское хранилище жидкостей L",
 "Teladi M Liquid Storage": "Теладийское хранилище жидкостей M",
 "Teladi S Liquid Storage": "Теладийское хранилище жидкостей S",
 "Teladi L Solid Storage": "Теладийское хранилище твёрдых грузов L",
 "Teladi M Solid Storage": "Теладийское хранилище твёрдых грузов M",
 "Teladi S Solid Storage": "Теладийское хранилище твёрдых грузов S",
 "Split Base Connection Structure 01": "Сплитская базовая соединительная конструкция 01",
 "Split Base Connection Structure 02": "Сплитская базовая соединительная конструкция 02",
 "Split Base Connection Structure 03": "Сплитская базовая соединительная конструкция 03",
 "Split Cross Connection Structure 01": "Сплитская крестовая соединительная конструкция 01",
 "Split Vertical Connection Structure 01": "Сплитская вертикальная соединительная конструкция 01",
 "Split Vertical Connection Structure 02": "Сплитская вертикальная соединительная конструкция 02",
 "Split Administrative Centre": "Сплитский административный центр",
 "Split Disc Defence Platform": "Сплитская дисковая оборонительная платформа",
 "Split Bridge Defence Platform": "Сплитская мостовая оборонительная платформа",
 "Split L Parlour": "Сплитский салон L",
 "Split M Parlour": "Сплитский салон M",
 "Split S Parlour": "Сплитский салон S",
 "Split 4-Dock T Pier": "Сплитский пирс T на 4 дока",
 "Split 1-Dock Pier": "Сплитский пирс на 1 док",
 "Split 3-Dock E Pier": "Сплитский пирс E на 3 дока",
 "Chelt Production": "Производство челта",
 "Split Medical Supply Production": "Сплитское производство медикаментов",
 "Scruffin Production": "Производство скраффина",
 "Split L Container Storage": "Сплитское контейнерное хранилище L",
 "Split M Container Storage": "Сплитское контейнерное хранилище M",
 "Split S Container Storage": "Сплитское контейнерное хранилище S",
 "Split L Liquid Storage": "Сплитское хранилище жидкостей L",
 "Split M Liquid Storage": "Сплитское хранилище жидкостей M",
 "Split S Liquid Storage": "Сплитское хранилище жидкостей S",
 "Split L Solid Storage": "Сплитское хранилище твёрдых грузов L",
 "Split M Solid Storage": "Сплитское хранилище твёрдых грузов M",
 "Split S Solid Storage": "Сплитское хранилище твёрдых грузов S",
 "Terran S/M Ship Fabrication Bay": "Терранский сборочный ангар для кораблей S/M",
 "Terran L Ship Fabrication Bay": "Терранский сборочный ангар для кораблей L",
 "Terran XL Ship Fabrication Bay": "Терранский сборочный ангар для кораблей XL",
 "Terran Base Connection Structure 01": "Терранская базовая соединительная конструкция 01",
 "Terran Base Connection Structure 02": "Терранская базовая соединительная конструкция 02",
 "Terran Base Connection Structure 03": "Терранская базовая соединительная конструкция 03",
 "Terran Cross Connection Structure 01": "Терранская крестовая соединительная конструкция 01",
 "Terran Vertical Connection Structure 01": "Терранская вертикальная соединительная конструкция 01",
 "Terran Vertical Connection Structure 02": "Терранская вертикальная соединительная конструкция 02",
 "Terran Administrative Centre": "Терранский административный центр",
 "Terran Disc Defence Platform": "Терранская дисковая оборонительная платформа",
 "Terran Bridge Defence Platform": "Терранская мостовая оборонительная платформа",
 "Terran 4M10S Luxury Dock Area": "Терранская роскошная док-зона 4M10S",
 "Terran S/M Ship Maintenance Bay": "Терранский ремонтный ангар для кораблей S/M",
 "Terran L Ship Maintenance Bay": "Терранский ремонтный ангар для кораблей L",
 "Terran XL Ship Maintenance Bay": "Терранский ремонтный ангар для кораблей XL",
 "Terran L Living Quarters": "Терранские жилые помещения L",
 "Terran M Living Quarters": "Терранские жилые помещения M",
 "Terran S Living Quarters": "Терранские жилые помещения S",
 "Terran 3-Dock T Pier": "Терранский пирс T на 3 дока",
 "Terran 1-Dock Pier": "Терранский пирс на 1 док",
 "Terran 3-Dock E Pier": "Терранский пирс E на 3 дока",
 "Terran 4-Dock T Pier": "Терранский пирс T на 4 дока",
 "Terran Trading Station Hexa-Dock Pier": "Терранский торговый пирс на 6 доков",
 "Computronic Substrate Production": "Производство компьютронной подложки",
 "Terran Energy Cell Production": "Терранское производство энергоячеек",
 "Terran Medical Supply Production": "Терранское производство медикаментов",
 "Metallic Microlattice Production": "Производство металлической микрорешётки",
 "Protein Paste Production": "Производство белковой пасты",
 "Terran Scrap Recycler": "Терранский утилизатор металлолома",
 "Silicon Carbide Production": "Производство карбида кремния",
 "Stimulant Production": "Производство стимуляторов",
 "Terran MRE Production": "Терранское производство сухпайков MRE",
 "Terran L Container Storage": "Терранское контейнерное хранилище L",
 "Terran M Container Storage": "Терранское контейнерное хранилище M",
 "Terran S Container Storage": "Терранское контейнерное хранилище S",
 "Terran L Liquid Storage": "Терранское хранилище жидкостей L",
 "Terran M Liquid Storage": "Терранское хранилище жидкостей M",
 "Terran S Liquid Storage": "Терранское хранилище жидкостей S",
 "Terran L Solid Storage": "Терранское хранилище твёрдых грузов L",
 "Terran M Solid Storage": "Терранское хранилище твёрдых грузов M",
 "Terran S Solid Storage": "Терранское хранилище твёрдых грузов S",
 "Argon L Dormitory": "Аргонское общежитие L",
 "Argon M Dormitory": "Аргонское общежитие M",
 "Argon S Dormitory": "Аргонское общежитие S",
 "Protectyon Shield Generator": "Генератор щита «Протектион»",
 "Boron S/M Ship Fabrication Bay": "Боронский сборочный ангар для кораблей S/M",
 "Boron L Ship Fabrication Bay": "Боронский сборочный ангар для кораблей L",
 "Boron XL Ship Fabrication Bay": "Боронский сборочный ангар для кораблей XL",
 "Boron Base Connection Structure 01": "Боронская базовая соединительная конструкция 01",
 "Boron Base Connection Structure 02": "Боронская базовая соединительная конструкция 02",
 "Boron Base Connection Structure 03": "Боронская базовая соединительная конструкция 03",
 "Boron Base Connection Structure 04": "Боронская базовая соединительная конструкция 04",
 "Boron Base Connection Structure 05": "Боронская базовая соединительная конструкция 05",
 "Boron Cross Connection Structure 01": "Боронская крестовая соединительная конструкция 01",
 "Boron Cross Connection Structure 02": "Боронская крестовая соединительная конструкция 02",
 "Boron Vertical Connection Structure 01": "Боронская вертикальная соединительная конструкция 01",
 "Boron Vertical Connection Structure 02": "Боронская вертикальная соединительная конструкция 02",
 "Boron Administrative Centre": "Боронский административный центр",
 "Boron Disc Defence Platform": "Боронская дисковая оборонительная платформа",
 "Boron Bridge Defence Platform": "Боронская мостовая оборонительная платформа",
 "Boron 4M14S Luxury Dock Area": "Боронская роскошная док-зона 4M14S",
 "Boron S/M Ship Maintenance Bay": "Боронский ремонтный ангар для кораблей S/M",
 "Boron L Ship Maintenance Bay": "Боронский ремонтный ангар для кораблей L",
 "Boron XL Ship Maintenance Bay": "Боронский ремонтный ангар для кораблей XL",
 "Boron L Oasis": "Боронский оазис L",
 "Boron M Oasis": "Боронский оазис M",
 "Boron S Oasis": "Боронский оазис S",
 "Boron 4-Dock T Pier": "Боронский пирс T на 4 дока",
 "Boron 1-Dock Pier": "Боронский пирс на 1 док",
 "Boron 3-Dock E Pier": "Боронский пирс E на 3 дока",
 "Boron Trading Station 4-Dock Pier": "Боронский торговый пирс на 4 дока",
 "Boron Trading Station Hexa-Dock Pier": "Боронский торговый пирс на 6 доков",
 "BoFu Production": "Производство БоФу",
 "BoGas Production": "Производство БоГаза",
 "Boron Medical Supply Production": "Боронское производство медикаментов",
 "Plankton Production": "Производство планктона",
 "Boron L Container Storage": "Боронское контейнерное хранилище L",
 "Boron M Container Storage": "Боронское контейнерное хранилище M",
 "Boron S Container Storage": "Боронское контейнерное хранилище S",
 "Boron L Liquid Storage": "Боронское хранилище жидкостей L",
 "Boron M Liquid Storage": "Боронское хранилище жидкостей M",
 "Boron S Liquid Storage": "Боронское хранилище жидкостей S",
 "Boron L Solid Storage": "Боронское хранилище твёрдых грузов L",
 "Boron M Solid Storage": "Боронское хранилище твёрдых грузов M",
 "Boron S Solid Storage": "Боронское хранилище твёрдых грузов S"
}

# ---------------------------------------------------------------- чтение .cat/.dat
def cat_sources(game):
    """Список (cat, dat) в порядке приоритета: базовая игра по номерам, затем расширения (DLC)."""
    def num(p):
        m = re.search(r'(\d+)\.cat$', p, re.I)
        return int(m.group(1)) if m else 0
    base = sorted([p for p in glob.glob(os.path.join(game, '*.cat')) if re.fullmatch(r'\d+\.cat', os.path.basename(p), re.I)], key=num)
    ext = []
    for d in sorted(glob.glob(os.path.join(game, 'extensions', 'ego_dlc_*'))):  # только официальные DLC, без модов
        cats = [p for p in glob.glob(os.path.join(d, '*.cat')) if re.fullmatch(r'(ext|subst)_\d+\.cat', os.path.basename(p), re.I)]
        ext += sorted(cats, key=lambda p: (os.path.basename(p).lower().startswith('subst'), num(p)))
    return [(c, c[:-4] + '.dat') for c in base + ext]

def read_from_cat(cat, dat, wanted):
    """wanted: функция(путь_в_нижнем_регистре) -> bool. Возвращает {путь: байты}."""
    out, offset = {}, 0
    with open(cat, 'r', encoding='utf-8', errors='replace') as f, open(dat, 'rb') as d:
        for line in f:
            line = line.rstrip('\r\n')
            if not line:
                continue
            parts = line.rsplit(' ', 3)
            if len(parts) != 4:
                continue
            path, size = parts[0], int(parts[1])
            if wanted(path.lower()):
                d.seek(offset)
                out[path] = d.read(size)
            offset += size
    return out

def parse_texts(blob, label, texts):
    try:
        root = ET.fromstring(blob)
    except ET.ParseError as e:
        print('  не удалось разобрать %s: %s' % (label, e))
        return
    n = 0
    for page in root.iter('page'):
        pid = page.get('id')
        for t in page.findall('t'):
            texts[(pid, t.get('id'))] = ''.join(t.itertext())
            n += 1
    print('  %s -> %d записей' % (label, n))

def load_language(game, lang_id):
    """Собирает {(page, id): текст} для языка: из cat-файлов, затем из обычных файлов (t/ и extensions/*/t/)."""
    want = re.compile(r'(^|/)t/0001-l0*%d\.xml$' % lang_id)
    texts = {}
    for cat, dat in cat_sources(game):
        if not (os.path.exists(cat) and os.path.exists(dat)):
            continue
        for path, blob in read_from_cat(cat, dat, lambda p: bool(want.search(p))).items():
            parse_texts(blob, '%s: %s' % (os.path.basename(cat), path), texts)
    loose = glob.glob(os.path.join(game, 't', '*')) + glob.glob(os.path.join(game, 'extensions', 'ego_dlc_*', 't', '*'))
    for path in sorted(loose):
        if re.search(r'0001-l0*%d\.xml$' % lang_id, path, re.I):
            try:
                with open(path, 'rb') as f:
                    parse_texts(f.read(), path, texts)
            except OSError as e:
                print('  пропускаю %s: %s' % (path, e))
    return texts

def diagnose(game):
    """Показывает, какие текстовые файлы t/*.xml лежат в каждом архиве и в папках расширений."""
    for cat, dat in cat_sources(game):
        if os.path.exists(cat) and os.path.exists(dat):
            for line in open(cat, 'r', encoding='utf-8', errors='replace'):
                parts = line.rstrip('\r\n').rsplit(' ', 3)
                if len(parts) == 4 and re.search(r'(^|/)t/[^/]*\.xml$', parts[0], re.I):
                    print('%s: %s (%s байт)' % (os.path.relpath(cat, game), parts[0], parts[1]))
    for path in sorted(glob.glob(os.path.join(game, 'extensions', 'ego_dlc_*', 't', '*')) + glob.glob(os.path.join(game, 't', '*'))):
        try:
            print('файл: %s (%d байт)' % (os.path.relpath(path, game), os.path.getsize(path)))
        except OSError as e:
            print('файл: %s (недоступен: %s)' % (os.path.relpath(path, game), e))

# ---------------------------------------------------------------- очистка текстов игры
REF = re.compile(r'\{(\d+),\s*(\d+)\}')
def resolve(texts, key, depth=0):
    s = texts.get(key, '')
    if depth > 8:
        return s
    return REF.sub(lambda m: resolve(texts, (m.group(1), m.group(2)), depth + 1) if (m.group(1), m.group(2)) in texts else m.group(0), s)

def strip_comments(s):
    # в игре текст в круглых скобках не показывается; \( - экранированная скобка
    s = re.sub(r'(?<!\\)\([^()]*\)', '', s)
    return s.replace('\\(', '(').replace('\\)', ')')

def norm(s):
    return re.sub(r'\s+', ' ', s).strip()

_FIX = str.maketrans({'\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"', '\u2013': '-', '\u2014': '-', '\u00a0': ' '})
def knorm(s):
    """Ключ для сравнения английских текстов: без различий в типографских кавычках и тире."""
    return norm(s.translate(_FIX))

# ---------------------------------------------------------------- построение таблицы
def build_map(game):
    print('Читаю английские тексты...')
    en = load_language(game, EN_ID)
    print('Читаю русские тексты...')
    ru = load_language(game, RU_ID)
    if not en or not ru:
        sys.exit('Не нашёл текстовые файлы игры (en=%d, ru=%d). Проверьте путь к игре.' % (len(en), len(ru)))
    votes = collections.defaultdict(collections.Counter)
    for key in en:
        if key not in ru:
            continue
        e_raw, r_raw = resolve(en, key), resolve(ru, key)
        for e in {knorm(e_raw), knorm(strip_comments(e_raw))}:
            r = norm(strip_comments(r_raw))
            if e and r:
                votes[e][r] += 1
    mapping, ambiguous = {}, {}
    for e, c in votes.items():
        best = c.most_common()
        mapping[e] = best[0][0]
        if len(best) > 1:
            ambiguous[e] = best
    print('Таблица: %d английских текстов, неоднозначных: %d' % (len(mapping), len(ambiguous)))
    return mapping, ambiguous

# ---------------------------------------------------------------- замена в данных сайта
FIELD = re.compile(r"(\b(?:name|description)\s*:\s*)'((?:[^'\\\n]|\\.)*)'")
def unescape(s):
    return re.sub(r'\\(.)', lambda m: ' ' if m.group(1) == 'n' else m.group(1), s)
def escape(s):
    return s.replace('\\', '\\\\').replace("'", "\\'")

PREFIX = 90
def apply(mapping, report):
    fb = {knorm(k): v for k, v in FALLBACK.items()}
    stats = collections.Counter()
    by_prefix = collections.defaultdict(set)
    for k in mapping:
        if len(k) >= PREFIX:
            by_prefix[k[:PREFIX]].add(k)
    for path in sorted(glob.glob(os.path.join(DATA_DIR, '*.ts'))):
        orig = path + '.orig'
        if not os.path.exists(orig):
            with open(path, 'rb') as a, open(orig, 'wb') as b:
                b.write(a.read())
        with open(orig, 'r', encoding='utf-8', newline='') as f:
            text = f.read()
        missing = []
        def sub(m):
            eng = knorm(unescape(m.group(2)))
            if not eng:
                return m.group(0)
            if eng in mapping:
                stats['официальный'] += 1
                return m.group(1) + "'" + escape(mapping[eng]) + "'"
            if len(eng) >= PREFIX and len(by_prefix.get(eng[:PREFIX], ())) == 1:
                stats['по началу текста'] += 1
                return m.group(1) + "'" + escape(mapping[next(iter(by_prefix[eng[:PREFIX]]))]) + "'"
            if eng in fb:
                stats['запасной (мой)'] += 1
                return m.group(1) + "'" + escape(fb[eng]) + "'"
            stats['без перевода'] += 1
            missing.append(eng)
            return m.group(0)
        new = FIELD.sub(sub, text)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(new)
        report.append('== %s: без перевода %d' % (os.path.basename(path), len(missing)))
        report.extend('   ' + x[:150] for x in missing[:400])
    return stats

def main():
    if len(sys.argv) < 2:
        sys.exit('Использование: python x4_localize.py ПУТЬ_К_ПАПКЕ_ИГРЫ')
    game = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == '--diag':
        diagnose(game)
        return
    if not os.path.isdir(DATA_DIR):
        sys.exit('Запускайте из папки проекта x4 (не найдено %s)' % DATA_DIR)
    mapping, ambiguous = build_map(game)
    report = []
    stats = apply(mapping, report)
    report.append('')
    report.append('== Неоднозначные переводы (выбран самый частый), первые 300')
    for e, c in list(ambiguous.items())[:300]:
        report.append('   %s -> %s' % (e[:80], ' | '.join('%s x%d' % (r[:60], n) for r, n in c[:3])))
    with open('x4-localize-report.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    print('Готово:', dict(stats))
    print('Подробности: x4-localize-report.txt')

if __name__ == '__main__':
    main()
