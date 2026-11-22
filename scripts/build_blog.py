#!/usr/bin/env python3
"""
Markdown posts (blog/posts/*.md) -> HTML pages (blog/<name>.html) + blog/index.html.
No extra libraries needed.  A post with a FUTURE date is skipped until that date,
so you can queue posts in advance (the workflow runs every morning).
"""
import html, json, re, sys
from urllib.parse import quote
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "blog" / "posts"
OUT = ROOT / "blog"
SITE = "https://shetkarisevarth.in"

# ---- बदलता येण्यासारख्या गोष्टी ----
CTA_URL  = "/"                                   # लेखाच्या शेवटच्या बटणाची link (अंदाजपत्रक फॉर्मचा पत्ता टाका)
CTA_TEXT = "📄 आपले अंदाजपत्रक तयार करा"
CTA_NOTE = "आपल्या पिकानुसार अंदाजपत्रक मोफत तयार करा"
DEFAULT_EMOJI = "🌾"
DEFAULT_OG_IMAGE = "/share-default.png"      # लेखात चित्र नसेल तर WhatsApp/Google वर हे चित्र दिसते (repository च्या मुख्य जागी ठेवा)
SITE_NAME = "शेतकरी सेवार्थ"
WA_CHANNEL = "https://whatsapp.com/channel/0029VbE0FkvGufIxAZ0NQk2m"   # WhatsApp चॅनेलची link
TEMPLATE = (OUT / "template.html").read_text(encoding="utf-8")

MR = "०१२३४५६७८९"
MONTHS = ["जानेवारी","फेब्रुवारी","मार्च","एप्रिल","मे","जून","जुलै","ऑगस्ट","सप्टेंबर","ऑक्टोबर","नोव्हेंबर","डिसेंबर"]
def mr_date(d):
    s = f"{d.day} {MONTHS[d.month-1]} {d.year}"
    return "".join(MR[int(c)] if c.isdigit() else c for c in s)

def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1" loading="lazy">', t)
    def _link(m):
        txt, href = m.group(1), m.group(2)
        if href.lower().split("?")[0].endswith(".pdf"):
            return f'<a class="pdf-link" href="{href}" target="_blank" rel="noopener">📄 {txt}</a>'
        if href.startswith("http") and not href.startswith(SITE):
            return f'<a href="{href}" target="_blank" rel="noopener">{txt}</a>'
        return f'<a href="{href}">{txt}</a>'
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link, t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", t)
    return t

SEP = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")

def split_row(line):
    line = line.strip()
    if line.startswith("|"): line = line[1:]
    if line.endswith("|"): line = line[:-1]
    return [c.strip() for c in line.split("|")]

def table_html(rows):
    head, aligns, body = split_row(rows[0]), [], rows[2:]
    for c in split_row(rows[1]):
        aligns.append("center" if c.startswith(":") and c.endswith(":") else "right" if c.endswith(":") else "left")
    def cell(tag, txt, i):
        al = aligns[i] if i < len(aligns) else "left"
        return f'<{tag} style="text-align:{al}">{inline(txt)}</{tag}>'
    out = ['<div class="table-wrap"><table><thead><tr>' + "".join(cell("th", c, i) for i, c in enumerate(head)) + "</tr></thead><tbody>"]
    for r in body:
        out.append("<tr>" + "".join(cell("td", c, i) for i, c in enumerate(split_row(r))) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)

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
    lines = md.splitlines(); i = 0
    while i < len(lines):
        s = lines[i].strip(); i += 1
        if not s: flush_p(); flush_l(); continue
        # table: a "|" row followed by a |---|---| separator row
        if s.startswith("|") and i < len(lines) and SEP.match(lines[i].strip()):
            flush_p(); flush_l()
            rows = [s, lines[i].strip()]; i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip()); i += 1
            out.append(table_html(rows)); continue
        m = re.match(r"^(#{1,3})\s+(.*)", s)
        if m:
            flush_p(); flush_l(); n = max(2, len(m.group(1)))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>"); continue
        if s in ("---", "***"): flush_p(); flush_l(); out.append("<hr>"); continue
        bm = re.match(r"^[-*]\s+(.*)", s); om = re.match(r"^\d+[.)]\s+(.*)", s)
        if bm or om:
            flush_p(); k = "ul" if bm else "ol"
            if kind and kind != k: flush_l()
            kind = k; items.append((bm or om).group(1)); continue
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

def mr_num(n):
    return "".join(MR[int(c)] for c in str(n))

def minutes(text):
    return max(1, round(len(re.findall(r"\S+", text)) / 180))

def css_url(u):
    return html.escape(u.replace("'", "%27"), quote=True)

def thumb(post):
    if post["image"]:
        return f'<div class="thumb" style="background-image:url(\'{css_url(post["image"])}\')"></div>'
    return f'<div class="thumb">{post["emoji"]}</div>'

def card(post):
    return (f'<a class="card" href="/blog/{post["slug"]}.html">{thumb(post)}<div class="cbody">'
            f'<span class="d">{post["date_mr"]}</span><h2>{html.escape(post["title"])}</h2>'
            f'<p>{html.escape(post["description"])}</p></div></a>')

def hero(post):
    style = ""
    if post["image"]:
        style = (f' style="background-image:linear-gradient(180deg,rgba(6,78,59,.15) 0%,rgba(6,78,59,.88) 100%),'
                 f'url(\'{css_url(post["image"])}\')"')
    emoji = "" if post["image"] else f'<span class="emoji">{post["emoji"]}</span>'
    tag = f'<span class="tag">{html.escape(post["tag"])}</span><br>' if post["tag"] else ""
    return (f'<section class="hero"{style}><div class="hero-in">{emoji}{tag}'
            f'<h1>{html.escape(post["title"])}</h1>'
            f'<p class="meta">📅 {post["date_mr"]} &nbsp;·&nbsp; ⏱ वाचन वेळ सुमारे {mr_num(post["mins"])} मिनिटे</p>'
            f'</div></section>')

def share(post):
    url = f"{SITE}/blog/{post['slug']}.html"
    wa = "https://wa.me/?text=" + quote(f"{post['title']}\n{url}")
    return ('<div class="share">'
            f'<a class="btn wa" href="{wa}" target="_blank" rel="noopener">💬 WhatsApp वर शेअर करा</a>'
            f'<button class="btn copy" type="button" onclick="navigator.clipboard&&navigator.clipboard.writeText(\'{url}\');this.textContent=\'✔ लिंक कॉपी झाली\'">🔗 लिंक कॉपी करा</button>'
            '</div>')

def wa_card():
    return ('<div class="wa-card"><span class="ic">💬</span><div class="txt">'
            '<p class="t">रोज नवीन शेती माहिती व योजनांचे अपडेट्स मिळवा</p>'
            '<p class="s">आमचे WhatsApp चॅनेल मोफत जॉइन करा</p></div>'
            f'<a class="btn wa" href="{WA_CHANNEL}" target="_blank" rel="noopener">चॅनेल जॉइन करा</a></div>')

def parse_date(v):
    try: return datetime.strptime(v, "%Y-%m-%d").date()
    except (ValueError, TypeError): return None

def info_row(post):
    parts = []
    if post["updated"]:
        parts.append(f'📌 शेवटचे अद्यतन: {mr_date(post["updated"])}')
    if post["source"]:
        src = html.escape(post["source"])
        if post["source_url"]:
            src = f'<a href="{html.escape(post["source_url"], quote=True)}" target="_blank" rel="noopener">{src}</a>'
        parts.append(f'📎 स्रोत: {src}')
    return f'<div class="info-row">{" &nbsp;·&nbsp; ".join(parts)}</div>' if parts else ""

def abs_url(u):
    return u if u.startswith("http") else SITE + (u if u.startswith("/") else "/" + u)

def json_ld(post, url, image):
    data = {"@context": "https://schema.org", "@type": "Article", "headline": post["title"],
            "description": post["description"], "datePublished": post["d"].isoformat(),
            "dateModified": (post["updated"] or post["d"]).isoformat(), "inLanguage": "mr",
            "mainEntityOfPage": url, "image": [abs_url(image)],
            "author": {"@type": "Organization", "name": SITE_NAME},
            "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE}}
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + "</script>"

def cta(post):
    if post["cta_off"]: return ""
    url = post["cta_url"] or CTA_URL
    text = post["cta_text"] or CTA_TEXT
    note = post["cta_note"] or CTA_NOTE
    return (f'<div class="cta"><p>{html.escape(note)}</p>'
            f'<a href="{html.escape(url, quote=True)}">{html.escape(text)}</a></div>')

def main():
    today = date.today()
    posts = []
    for p in sorted(POSTS.glob("*.md")):
        if p.name.startswith("_"): continue                  # _name.md = मसुदा, प्रकाशित होत नाही
        meta, body = parse(p)
        try: d = datetime.strptime(meta.get("date", ""), "%Y-%m-%d").date()
        except ValueError: print(f"skip {p.name}: missing/invalid date (use YYYY-MM-DD)"); continue
        if d > today: print(f"scheduled {p.name} -> {d}"); continue
        posts.append({"slug": p.stem, "d": d, "date_mr": mr_date(d), "title": meta.get("title") or p.stem,
                      "description": meta.get("description", ""), "image": meta.get("image", ""),
                      "alt": meta.get("image_alt", ""), "emoji": meta.get("emoji", DEFAULT_EMOJI),
                      "tag": meta.get("tag", ""), "mins": minutes(body), "body": body,
                      "updated": parse_date(meta.get("updated", "")), "source": meta.get("source", ""), "source_url": meta.get("source_url", ""),
                      "cta_off": meta.get("cta", "").strip().lower() in ("no", "off", "false", "नाही"),
                      "cta_url": meta.get("cta_url", ""), "cta_text": meta.get("cta_text", ""), "cta_note": meta.get("cta_note", "")})
    posts.sort(key=lambda x: (x["d"], x["slug"]), reverse=True)

    for post in posts:
        url = f"{SITE}/blog/{post['slug']}.html"
        others = [x for x in posts if x["slug"] != post["slug"]][:3]
        related = ('<h2 class="sec-title">📚 इतर लेख</h2><div class="cards">' + "".join(card(x) for x in others) + "</div>") if others else ""
        page_body = hero(post) + info_row(post) + f"<article>{md_to_html(post['body'])}</article>" + share(post) + wa_card() + cta(post) + related
        image = post["image"] or DEFAULT_OG_IMAGE
        og = f'<meta property="og:image" content="{html.escape(abs_url(image), quote=True)}">\n<meta name="twitter:card" content="summary_large_image">\n' + json_ld(post, url, image)
        page = fill(TEMPLATE, title=html.escape(post["title"]), description=html.escape(post["description"], quote=True),
                    url=url, og_image_tag=og, body=page_body, wa_channel=WA_CHANNEL)
        (OUT / f"{post['slug']}.html").write_text(page, encoding="utf-8")

    # blog/index.html = सरळ मुख्य पोर्टलच्या "ब्लॉग" tab कडे नेतो (यादी दोन ठिकाणी ठेवावी लागत नाही)
    (OUT / "index.html").write_text(
        '<!DOCTYPE html><html lang="mr"><head><meta charset="UTF-8"><title>ब्लॉग | शेतकरी सेवार्थ</title>'
        '<meta http-equiv="refresh" content="0; url=/#blog"><meta name="robots" content="noindex">'
        '<link rel="canonical" href="' + SITE + '/"><script>location.replace("/#blog")</script></head>'
        '<body><p><a href="/#blog">ब्लॉग पाहण्यासाठी येथे क्लिक करा</a></p></body></html>', encoding="utf-8")
    (OUT / "posts.json").write_text(json.dumps(
        [{"title": x["title"], "description": x["description"], "date": x["d"].isoformat(), "date_mr": x["date_mr"],
          "url": f"blog/{x['slug']}.html", "image": x["image"], "emoji": x["emoji"]} for x in posts],
        ensure_ascii=False, indent=1), encoding="utf-8")        # index.html चा "ब्लॉग" tab हे वाचतो
    urls = [f"{SITE}/blog/{x['slug']}.html" for x in posts]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + \
         "".join(f"<url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    (OUT / "sitemap.xml").write_text(sm, encoding="utf-8")
    print(f"published {len(posts)} post(s)")

if __name__ == "__main__":
    sys.exit(main())
