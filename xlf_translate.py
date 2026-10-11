#!/usr/bin/env python3
"""
xlf_translate.py -- создаёт/обновляет языковой пакет src/i18n/messages.<язык>.xlf из src/i18n/messages.xlf.

  python xlf_translate.py ru            # использует glossary.ru.json (английский текст -> перевод)
  python xlf_translate.py de            # для нового языка: создаст messages.de.xlf (без glossary.de.json цели пустые)

Правила:
  * перевод берётся из glossary.<язык>.json (ключ — английский текст, {0}, {1} — позиции <x/>-подстановок);
  * уже существующие переводы в messages.<язык>.xlf сохраняются, если в глоссарии нет нового значения;
  * строки, состоящие только из подстановок (например, AM/PM или значение прогресса в ng-bootstrap), не переводятся;
  * всё непереведённое остаётся английским и перечисляется в xlf-untranslated.<язык>.txt.
Новый язык = один файл messages.<язык>.xlf (его можно просто перевести руками или передать переводчику).
"""
import json, os, re, sys

def ws(s): return ' '.join(s.split())
def keyify(s):
    n = [0]
    def x(m):
        k = '{%d}' % n[0]; n[0] += 1; return k
    return ws(re.sub(r'<x[^>]*/>', x, s))

def main():
    if len(sys.argv) < 2:
        sys.exit('Использование: python xlf_translate.py КОД_ЯЗЫКА (например ru)')
    lang = sys.argv[1]
    base = 'src/i18n/messages.xlf'
    out = 'src/i18n/messages.%s.xlf' % lang
    gl_path = 'glossary.%s.json' % lang
    if not os.path.exists(base):
        sys.exit('Нет %s. Сначала выполните ng extract-i18n.' % base)
    glossary = json.load(open(gl_path, encoding='utf-8')) if os.path.exists(gl_path) else {}
    existing = {}
    if os.path.exists(out):
        for uid, t in re.findall(r'<trans-unit id="([^"]+)"[^>]*>\s*<source>.*?</source>\s*<target[^>]*>(.*?)</target>',
                                 open(out, encoding='utf-8').read(), re.S):
            existing[uid] = t
    data = open(base, encoding='utf-8', newline='').read()
    missing, stats = [], {'из глоссария': 0, 'сохранено': 0}

    def sub(m):
        uid, source = m.group(2), m.group(3)
        if not re.search(r'[^\W\d_]', re.sub(r'<x[^>]*/>', '', source)):
            return m.group(0)             # только подстановки/символы («««, AM/PM, значение): не переводим
        xs = re.findall(r'<x[^>]*/>', source)
        key = keyify(source)
        lead = source[:len(source) - len(source.lstrip())]
        trail = source[len(source.rstrip()):]
        target = None
        if key in glossary:
            t = glossary[key]
            for i, x in enumerate(xs):
                t = t.replace('{%d}' % i, x)
            target = lead + t + trail
            stats['из глоссария'] += 1
        elif uid in existing:
            target = existing[uid]; stats['сохранено'] += 1
        if target is None:
            missing.append('%s | %s' % (uid, key[:100]))
            return m.group(0)
        return m.group(0) + '<target state="translated">' + target + '</target>'

    new = re.sub(r'(<trans-unit id="([^"]+)"[^>]*>\s*<source>(.*?)</source>)', sub, data, flags=re.S)
    new = new.replace('original="ng2.template">', 'original="ng2.template" target-language="%s">' % lang, 1) \
        if 'target-language' not in new else new
    with open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    with open('xlf-untranslated.%s.txt' % lang, 'w', encoding='utf-8') as f:
        f.write('\n'.join(missing))
    print('%s: из глоссария %d, сохранено прежних %d, без перевода %d' % (out, stats['из глоссария'], stats['сохранено'], len(missing)))
    print('Список непереведённого: xlf-untranslated.%s.txt' % lang)

if __name__ == '__main__':
    main()
