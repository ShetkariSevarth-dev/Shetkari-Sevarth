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
            flush_p(); flush_l(); n = max(2, len(m.group(1)))   # # and ## -> h2, ### -> h3 (page title is h1)
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

def cta():
    return (f'<div class="cta"><p>{html.escape(CTA_NOTE)}</p>'
            f'<a href="{html.escape(CTA_URL, quote=True)}">{html.escape(CTA_TEXT)}</a></div>')

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
                      "tag": meta.get("tag", ""), "mins": minutes(body), "body": body})
    posts.sort(key=lambda x: (x["d"], x["slug"]), reverse=True)

    for post in posts:
        url = f"{SITE}/blog/{post['slug']}.html"
        others = [x for x in posts if x["slug"] != post["slug"]][:3]
        related = ('<h2 class="sec-title">📚 इतर लेख</h2><div class="cards">' + "".join(card(x) for x in others) + "</div>") if others else ""
        page_body = hero(post) + f"<article>{md_to_html(post['body'])}</article>" + share(post) + wa_card() + cta() + related
        og = f'<meta property="og:image" content="{html.escape(post["image"] if post["image"].startswith("http") else SITE + post["image"], quote=True)}">' if post["image"] else ""
        page = fill(TEMPLATE, title=html.escape(post["title"]), description=html.escape(post["description"], quote=True),
                    url=url, og_image_tag=og, body=page_body, wa_channel=WA_CHANNEL)
        (OUT / f"{post['slug']}.html").write_text(page, encoding="utf-8")

    cards = "".join(card(x) for x in posts) or "<p>लवकरच नवीन माहिती येत आहे.</p>"
    idx_body = ('<div class="listhead"><h1>📝 ब्लॉग</h1><p>शेतीविषयक लेख व माहिती</p></div>'
                f'<div class="cards">{cards}</div>')
    idx = fill(TEMPLATE, title="ब्लॉग", description="शेतकरी सेवार्थ - योजना व शेतीविषयक माहिती",
               url=f"{SITE}/blog/", og_image_tag="", body=idx_body + wa_card(), wa_channel=WA_CHANNEL)
    (OUT / "index.html").write_text(idx, encoding="utf-8")
    (OUT / "posts.json").write_text(json.dumps(
        [{"title": x["title"], "description": x["description"], "date": x["d"].isoformat(), "date_mr": x["date_mr"],
          "url": f"blog/{x['slug']}.html", "image": x["image"], "emoji": x["emoji"]} for x in posts],
        ensure_ascii=False, indent=1), encoding="utf-8")        # index.html चा "ब्लॉग" tab हे वाचतो
    urls = [f"{SITE}/blog/"] + [f"{SITE}/blog/{x['slug']}.html" for x in posts]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + \
         "".join(f"<url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    (OUT / "sitemap.xml").write_text(sm, encoding="utf-8")
    print(f"published {len(posts)} post(s)")

if __name__ == "__main__":
    sys.exit(main())
