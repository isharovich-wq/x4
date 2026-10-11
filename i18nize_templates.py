#!/usr/bin/env python3
"""
i18nize_templates.py -- расставляет в HTML-шаблонах сайта метки перевода Angular (i18n), чтобы ВСЕ видимые
надписи попадали в языковой пакет (src/i18n/messages.<язык>.xlf), а не были вшиты в разметку.

Что делает (для src/app/**/*.html):
  * оборачивает видимые английские фразы в <ng-container i18n="@@id">фраза</ng-container>;
  * для атрибутов caption / title / placeholder / alt / aria-label добавляет i18n-<атрибут>="@@id";
  * исправляет 4 места, где у автора метка i18n указывала на чужой идентификатор.
Оригиналы сохраняются как *.html.orig (скрипт можно запускать повторно, он всегда работает от .orig).
Идентификаторы стабильные: берутся из текущего src/i18n/messages.xlf, а для новых строк строятся из текста.

Запуск из папки проекта x4:
  docker run --rm -v "${PWD}:/app" -w /app python:3.12 python i18nize_templates.py
Дальше: ng extract-i18n (обновит messages.xlf), затем python xlf_translate.py ru
"""
import glob, os, re, sys, json, collections

PHRASES = ["File can be found in Documents\\Egosoft\\X4\\[12345678]\\constructionplans.xml", "Imported plans, but errors occurred trying to import some of them.", "content below. The plans will be added to your saved layout list.", "Headquarters (The HQ needs 200 workers for some reason)", "Resources are provided by other stations", "X4: Foundations Database and Utilities", ". Feel free to fork and contribute.", "Profit per Hour (100% Efficiency)", "Miners provide basic resources", "Successfully imported plans", "Failed to import plans.", "Open source project on", "Price Diff / Volume", "Production Per Hour", "Station Calculator", "Storage Capacity (", "Workforce Capacity", "Additional Shields", "1 x Unknown Module", "Products per Hour", "Profit per Hour (", "Station Resources", "Actual Workforce:", "Explosion Damage", "Workforce Needed", "Autofill Modules", "Needed Workforce", "Resources Price:", "Station Modules", "Missile Storage", "No usage found.", "Station Summary", "Products Price:", "Max Efficiency", "Drone Storage", "% Efficiency)", "Delete Layout", "Station Costs", "Main Shields", "Requirements", "(difference:", "Construction", "Required For", "Import Plans", "Share Layout", "Module Count", "Coming soon", "Description", "Production:", "Load Layout", "Save Layout", "Add Modules", "Production", "Cycle Time", "Batch Size", "Add Module", "( Select )", "efficiency", "Equipment", "Transport", "Min Price", "Avg Price", "Max Price", "Paste the", "Sun Light", "Workforce", "Factions", "Licenses", "Resource", "capacity", "Expenses", "Product", "Shields", "Turrets", "Weapons", "Purpose", "Engines", "Illegal", "Save As", "Average", "Owners", "People", "Volume", "Import", "Cancel", "Amount", "Profit", "Total:", "Module", "Wares", "Ships", "Races", "About", "Class", "Price", "Docks", "Total", "Close", "Share", "Value", "Count", "Name", "Race", "Type", "Size", "Hull", "Time", "Min:", "Avg:", "Max:", "Save", "Copy", "Load", "Auto", "Min", "Max", "Avg", "Yes", "New", "Ok", "No", "at"]
# фразы, которые встречаются только как текст/атрибут и должны попасть в пакет
ATTRS = ('caption', 'title', 'placeholder', 'alt', 'aria-label')

# исправление неверных меток: (файл, было, стало). Лишнюю метку убираем, нужный текст оборачивается заново.
SPECIAL = [
    ('ships.component.html', 'i18n="@@stationModules">', '>'),
    ('load-layout.component.html', 'i18n="@@load" (click)="addLayout($event, entity)">Add Modules</a>',
                                   '(click)="addLayout($event, entity)">Add Modules</a>'),
    ('load-layout.component.html', 'i18n="@@load" (click)="loadLayout($event, entity)">Load Layout</a>',
                                   'i18n="@@loadLayout" (click)="loadLayout($event, entity)">Load Layout</a>'),
    ('station-calculator.component.html', '<span i18n="@@share">Import</span>', '<span>Import</span>'),
]

def ws(s): return ' '.join(s.split())
def phrase_regex(p): return r'\s+'.join(re.escape(w) for w in p.split())

def slug(text):
    t = text.strip()
    suffix = 'Colon' if t.endswith(':') else ('Paren' if t.endswith('(') else '')
    if t.startswith('%'): t = 'percent ' + t
    words = re.findall(r'[A-Za-z0-9]+', t)[:6]
    if not words: return 'text'
    return words[0].lower() + ''.join(w.capitalize() for w in words[1:]) + suffix

class Registry:
    def __init__(self, xlf_path):
        self.text2id, self.id2text = {}, {}
        if os.path.exists(xlf_path):
            data = open(xlf_path, encoding='utf-8').read()
            for uid, src in re.findall(r'<trans-unit id="([^"]+)"[^>]*>\s*<source>(.*?)</source>', data, re.S):
                if uid.startswith('ngb.') or '<x' in src: continue
                t = ws(src)
                if t and uid not in self.id2text and t not in self.text2id:
                    self.text2id[t] = uid; self.id2text[uid] = t
    def get(self, text):
        t = ws(text)
        if t in self.text2id: return self.text2id[t]
        base = slug(t); n = 1; uid = base
        while uid in self.id2text and self.id2text[uid] != t:
            n += 1; uid = '%s%d' % (base, n)
        self.text2id[t] = uid; self.id2text[uid] = t
        return uid

def process(text, fname, reg, counts, problems):
    for f, old, new in SPECIAL:
        if fname.endswith(f):
            if old in text:
                text = text.replace(old, new); counts['исправлена метка'] += 1
            else:
                problems.append('не найден фрагмент для исправления в %s: %s' % (fname, old))
    for eng in PHRASES:
        # 1) текстовые фразы между тегами/интерполяциями
        rx = re.compile(r'(?<=[>};])(\s*)' + phrase_regex(eng) + r'(\s*)(?=[<{])')
        cur = text
        def sub(m):
            before = cur[:m.start()]
            if before.endswith('>') and 'i18n' in before[before.rfind('<'):]:
                return m.group(0)
            counts['текст'] += 1
            return '%s<ng-container i18n="@@%s">%s</ng-container>%s' % (m.group(1), reg.get(eng), eng, m.group(2))
        text = rx.sub(sub, cur)
        # 2) атрибуты
        arx = re.compile(r'\b(%s)="%s"' % ('|'.join(ATTRS), re.escape(eng)))
        cur = text
        def asub(m):
            ts = cur.rfind('<', 0, m.start()); te = cur.find('>', m.end())
            tag = cur[ts:te if te != -1 else len(cur)]
            if 'i18n-' + m.group(1) in tag:
                return m.group(0)
            counts['атрибут'] += 1
            return '%s i18n-%s="@@%s"' % (m.group(0), m.group(1), reg.get(eng))
        text = arx.sub(asub, cur)
    return text

def main():
    if not os.path.isdir('src/app'):
        sys.exit('Запускайте из папки проекта x4 (не найдено src/app)')
    reg = Registry('src/i18n/messages.xlf')
    counts = collections.Counter(); problems = []
    for path in sorted(glob.glob('src/app/**/*.html', recursive=True)):
        orig = path + '.orig'
        if not os.path.exists(orig):
            with open(path, 'rb') as a, open(orig, 'wb') as b:
                b.write(a.read())
        with open(orig, 'r', encoding='utf-8-sig', newline='') as f:
            text = f.read()
        new = process(text, path.replace('\\', '/'), reg, counts, problems)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(new)
    # проверка: один идентификатор не должен означать разные тексты
    seen = collections.defaultdict(set)
    for path in glob.glob('src/app/**/*.html', recursive=True):
        data = open(path, encoding='utf-8').read()
        for m in re.finditer(r'<(?:[^<>]*?\s)?i18n="@@([^"]+)"[^<>]*>([^<{]*)', data):
            t = ws(m.group(2).replace('&nbsp;', ' '))
            if t: seen[m.group(1)].add(t)
    for uid, texts in sorted(seen.items()):
        if len(texts) > 1:
            problems.append('идентификатор @@%s используется для разных текстов: %s' % (uid, ' | '.join(sorted(texts))))
    print('Готово:', dict(counts))
    for p in problems: print('ВНИМАНИЕ:', p)

if __name__ == '__main__':
    main()
