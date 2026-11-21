#!/usr/bin/env python3
import html, json, re, sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "blog" / "posts"
OUT = ROOT / "blog"
SITE = "https://shetkarisevarth.in"
TEMPLATE = (OUT / "template.html").read_text(encoding="utf-8")

MR = "०१२३४५६७८९"
MONTHS = ["जानेवारी","फेब्रुवारी","मार्च","एप्रिल","मे","जून","जुलै","ऑगस्ट","सप्टेंबर","ऑक्टोबर","नोव्हेंबर","डिसेंबर"]
def mr_date(d):
    s = f"{d.day} {MONTHS[d.month-1]} {d.year}"
    return "".join(MR[int(c)] if c.isdigit() else c for c in s)

def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1" loading="lazy">', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", t)
    return t

def md_to_html(md):
    out, para, items, kind = [], [], [], None
    def flush_p():
        nonlocal para
        if para: out.append("<p>" + inline(" ".join(para)) + "</p>"); para = []
    def flush_l():
        nonlocal items, kind
        if items:
            out.append(f"<{kind}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{kind}>")
            items, kind = [], None
    for line in md.splitlines():
        s = line.strip()
        m = re.match(r"^(#{1,3})\s+(.*)", s)
        if not s: flush_p(); flush_l(); continue
        if m:
            flush_p(); flush_l(); n = max(2, len(m.group(1)))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>"); continue
        if s in ("---", "***"): flush_p(); flush_l(); out.append("<hr>"); continue
        b = re.match(r"^[-*]\s+(.*)", s); o = re.match(r"^\d+[.)]\s+(.*)", s)
        if b or o:
            flush_p(); k = "ul" if b else "ol"
            if kind and kind != k: flush_l()
            kind = k; items.append((b or o).group(1)); continue
        if s.startswith(">"):
            flush_p(); flush_l(); out.append("<blockquote>" + inline(s.lstrip("> ")) + "</blockquote>"); continue
        flush_l(); para.append(s)
    flush_p(); flush_l()
    return "\n".join(out)

def parse(path):
    text = path.read_text(encoding="utf-8").lstrip("\ufeff")
    meta, body = {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if m:
        for l in m.group(1).splitlines():
            if ":" in l:
                k, v = l.split(":", 1); meta[k.strip().lower()] = v.strip().strip('"\'')
        body = m.group(2)
    return meta, body

def fill(tpl, **kw):
    for k, v in kw.items(): tpl = tpl.replace("{{" + k + "}}", v)
    return tpl

def main():
    today = date.today()
    posts = []
    for p in sorted(POSTS.glob("*.md")):
        if p.name.startswith("_"): continue
        meta, body = parse(p)
        try: d = datetime.strptime(meta.get("date", ""), "%Y-%m-%d").date()
        except ValueError: print(f"skip {p.name}: missing/invalid date"); continue
        if d > today: print(f"scheduled {p.name} -> {d}"); continue
        title = meta.get("title") or p.stem
        desc = meta.get("description", "")
        slug = p.stem
        page = fill(TEMPLATE, title=html.escape(title), description=html.escape(desc, quote=True),
                    date=mr_date(d), iso_date=d.isoformat(), content=md_to_html(body),
                    url=f"{SITE}/blog/{slug}.html")
        (OUT / f"{slug}.html").write_text(page, encoding="utf-8")
        posts.append((d, slug, title, desc))
    posts.sort(reverse=True)
    cards = "\n".join(
        f'<a class="card" href="/blog/{s}.html"><span class="d">{mr_date(d)}</span>'
        f'<h2>{html.escape(t)}</h2><p>{html.escape(ds)}</p></a>' for d, s, t, ds in posts) or "<p>लवकरच नवीन माहिती येत आहे.</p>"
    idx = fill(TEMPLATE, title="ब्लॉग", description="शेतकरी सेवार्थ - योजना व शेतीविषयक माहिती",
               date="", iso_date="", content=f'<div class="cards">{cards}</div>', url=f"{SITE}/blog/")
    (OUT / "index.html").write_text(idx, encoding="utf-8")
    (OUT / "posts.json").write_text(json.dumps(
        [{"title": t, "description": ds, "date": d.isoformat(), "date_mr": mr_date(d), "url": f"blog/{s}.html"}
         for d, s, t, ds in posts], ensure_ascii=False, indent=1), encoding="utf-8")
    urls = [f"{SITE}/blog/"] + [f"{SITE}/blog/{s}.html" for _, s, _, _ in posts]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + \
         "".join(f"<url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    (OUT / "sitemap.xml").write_text(sm, encoding="utf-8")
    print(f"published {len(posts)} post(s)")

if __name__ == "__main__":
    sys.exit(main())
