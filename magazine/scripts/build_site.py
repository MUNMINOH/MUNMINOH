#!/usr/bin/env python3
"""CADENCE 배포용 사이트를 만듭니다 (검색엔진 최적화).

index.html 하나를 바탕으로 페이지마다 실제 주소(/deal/, /guide/ ...)를 만들고,
각 페이지에 제목·설명·대표 주소·공유 이미지·구조화 데이터와
자바스크립트 없이도 읽히는 본문(뉴스·실거래·평당가·칼럼)을 넣습니다.
sitemap.xml, robots.txt, 404.html도 함께 만듭니다.

  python magazine/scripts/build_site.py   # 결과: _site/
"""
from __future__ import annotations

import datetime as dt
import html
import json
import shutil
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # magazine/
OUT = ROOT.parent / "_site"
SITE = "https://cadence.bldgrunner.com"
PYEONG = 3.3058
SOCIAL = [
    "https://www.youtube.com/@building_runner_official",
    "https://www.instagram.com/building_runner/",
    "https://blog.naver.com/morrison119",
]

ROUTES = [
    # slug, 경로, 이름, 페이지 제목, 설명
    ("home", "/", "홈", "CADENCE 케이던스 | 서울 빌딩 실거래·평당가·상업용 부동산 뉴스",
     "서울 빌딩 실거래와 권역·구·동별 평당가, 금리와 은행 대출 금리, 상장 리츠, 상업용 부동산 뉴스를 3시간마다 모아 보여 주는 빌딩러너의 상업용 부동산 리뷰."),
    ("market", "/market/", "마켓", "상업용 부동산 시장 뉴스: 오피스 공실률·임대료 | CADENCE",
     "오피스 공실률, 임대료, 수요와 공급 등 상업용 부동산 시장 뉴스를 언론사 원문 링크와 함께 모았습니다."),
    ("deal", "/deal/", "클로징", "서울 빌딩 매매 실거래 검색 | CADENCE",
     "국토교통부 신고 자료로 서울 빌딩 매매 실거래를 구·용도·금액대·기간별로 검색하고, 빌딩·물류센터·호텔 매각 뉴스를 봅니다."),
    ("building", "/building/", "빌딩", "빌딩 개발·리모델링·재건축 뉴스 | CADENCE",
     "빌딩 개발, 리모델링, 재건축, 준공 소식을 언론사 원문 링크와 함께 모았습니다."),
    ("policy", "/guide/", "건물주 가이드", "건물주 가이드: 취득세·중개보수·상가임대차보호법·RTI 계산기 | CADENCE",
     "빌딩 취득세 4.6%, 중개보수 0.9% 이내, 건물분 부가세, 상가임대차보호법 환산보증금, 임대업 대출 RTI 기준을 근거 법령과 함께 정리하고 계산기로 확인합니다."),
    ("players", "/players/", "페이스메이커", "리츠·자산운용사 뉴스와 상장 리츠 시세 | CADENCE",
     "리츠, 자산운용사, 기관투자자 소식과 상장 리츠 시세를 모았습니다."),
    ("data", "/data/", "랩타임", "서울 권역·구·동별 빌딩 평당가와 금리 | CADENCE",
     "국토교통부 실거래로 계산한 서울 권역·구·동별 빌딩 토지·연면적 평당가, 연식·용도별 평당가, 금리와 은행 대출 금리, 상장 리츠 시세."),
    ("column", "/column/", "칼럼", "빌딩러너 칼럼 | CADENCE",
     "빌딩러너가 상권과 빌딩 가치를 숫자로 풀어 쓴 칼럼을 모았습니다."),
    ("inquiry", "/inquiry/", "매도·매수 의뢰", "빌딩 매도·매수 의뢰 | CADENCE",
     "팔고 싶은 빌딩, 찾고 있는 빌딩을 남겨 주세요. 빌딩러너가 조건을 검토해 연락드립니다."),
    ("sell", "/sell/", "매도 의뢰", "빌딩 매도 의뢰 | CADENCE",
     "팔고 싶은 빌딩의 위치와 조건을 남겨 주세요. 빌딩러너가 검토해 연락드립니다."),
    ("buy", "/buy/", "매수 의뢰", "빌딩 매수 의뢰 | CADENCE",
     "찾고 있는 빌딩의 지역과 예산을 남겨 주세요. 빌딩러너가 검토해 연락드립니다."),
]
SECTION_NAMES = {"market": "마켓", "deal": "클로징", "building": "빌딩", "policy": "건물주 가이드", "players": "페이스메이커"}

e = lambda s: html.escape(str(s or ""), quote=True)


def eok(manwon: float) -> str:
    return f"{manwon / 10000:,.1f}"


def med(vals):
    vals = [v for v in vals if v and v > 0]
    return statistics.median(vals) if vals else 0


def land_py(r):
    return r["amount"] / (r["landArea"] / PYEONG) if r.get("landArea") else 0


def gfa_py(r):
    return r["amount"] / (r["buildingArea"] / PYEONG) if r.get("buildingArea") else 0


# ---------------------------------------------------------------- 사전 렌더링 본문
def news_list(news, limit=20):
    if not news:
        return ""
    items = "".join(
        f'<li><a href="{e(n["link"])}" rel="noopener" target="_blank"><b>{e(n["title"])}</b>'
        f'<small>{e(n.get("source"))} · {e((n.get("date") or "")[:10])}</small></a></li>' for n in news[:limit])
    return f'<ol class="headlines">{items}</ol>'


def head(title, desc):
    return f'<section class="cat-head"><div><h1>{e(title)}</h1><p>{e(desc)}</p></div></section>'


def gu_table(rows, limit=None):
    by = {}
    for r in rows:
        by.setdefault(r["gu"], []).append(r)
    stats = sorted(((gu, med([land_py(r) for r in rs]), med([gfa_py(r) for r in rs]), len(rs)) for gu, rs in by.items()),
                   key=lambda x: -x[1])
    if limit:
        stats = stats[:limit]
    body = "".join(f"<tr><td>{e(g)}</td><td>{l:,.0f}</td><td>{f:,.0f}</td><td>{n}</td></tr>" for g, l, f, n in stats)
    return ('<div class="table-scroll"><table class="gustats"><caption>서울 구별 빌딩 평당가 (중위값, 만 원)</caption>'
            '<thead><tr><th>구</th><th>토지 3.3㎡당</th><th>연면적 3.3㎡당</th><th>거래 건수</th></tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def deals_table(rows, limit=20):
    rows = sorted(rows, key=lambda r: r["date"], reverse=True)[:limit]
    body = "".join(
        f'<tr><td>{e(r["date"])}</td><td>서울 {e(r["gu"])} {e(r["dong"])}</td><td>{e(r.get("use"))}</td>'
        f'<td>{eok(r["amount"])}억 원</td><td>{land_py(r):,.0f}만 원</td></tr>' for r in rows)
    return ('<div class="table-scroll"><table class="deals"><caption>최근 서울 빌딩 매매 실거래</caption>'
            '<thead><tr><th>계약일</th><th>위치</th><th>용도</th><th>거래금액</th><th>토지 3.3㎡당</th></tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def columns_list(cols, limit=None):
    cols = [c for c in cols if c.get("type") == "blog"][:limit]
    if not cols:
        return ""
    items = "".join(
        f'<li><a href="{e(c["link"])}" rel="noopener" target="_blank"><b>{e(c["title"])}</b>'
        f'<small>빌딩러너 블로그 · {e((c.get("date") or "")[:10])}</small></a>'
        + (f'<p>{e(c.get("summary"))}</p>' if c.get("summary") else "") + "</li>" for c in cols)
    return f'<ol class="headlines">{items}</ol>'


def prerender(slug, name, desc, data, guide):
    news = data.get("news", [])
    rows = ((data.get("deals") or {}).get("history") or {}).get("rows", [])
    cols = data.get("columns", [])
    if slug == "home":
        top = ((data.get("deals") or {}).get("top") or [None])[0]
        lead = ""
        if top:
            lead = (f'<section class="cover-text"><p class="eyebrow">이번 달 서울 최대 빌딩 거래</p>'
                    f'<h1>서울 {e(top["gu"])} {e(top["dong"])} {e(top.get("use"))}, {eok(top["amount"])}억 원에 거래</h1>'
                    f'<p class="dek">{e(top["date"])} 계약 · 출처: 국토교통부 상업업무용 부동산 매매 신고 자료</p></section>')
        else:
            lead = '<h1>CADENCE 케이던스 · 서울 빌딩·상업용 부동산 리뷰</h1>'
        return (lead
                + (f'<section><h2>빌딩러너 칼럼</h2>{columns_list(cols, 5)}</section>' if cols else "")
                + (f'<section><h2>최신 상업용 부동산 뉴스</h2>{news_list(news, 12)}</section>' if news else "")
                + (f'<section><h2>서울 구별 빌딩 평당가</h2>{gu_table(rows, 10)}</section>' if rows else ""))
    if slug in ("market", "building", "players"):
        return head(name, desc) + news_list([n for n in news if n.get("section") == slug], 40)
    if slug == "deal":
        return (head(name, desc) + (deals_table(rows) if rows else "")
                + news_list([n for n in news if n.get("section") == "deal"], 30))
    if slug == "policy":
        facts = "".join(
            f'<article class="fact"><h3>{e(f["q"])}</h3><p class="fact-a">{e(f["a"])}</p><p>{e(f["d"])}</p>'
            f'<p class="fact-src">근거: {e(f.get("law") or f.get("src"))}</p></article>' for f in guide.get("facts", []))
        return (head(name, desc) + f'<section><h2>건물주가 가장 많이 묻는 기준</h2><div class="facts">{facts}</div>'
                f'<p class="foot-note">{e(guide.get("checked"))} 기준으로 법령과 공개 자료를 확인해 정리했습니다.</p></section>'
                + news_list([n for n in news if n.get("section") == "policy"], 20))
    if slug == "data":
        rates = data.get("rates", {})
        rate_items = "".join(f'<li>{e(r["name"])}: {r["value"]}{e(r.get("unit"))} ({e(r.get("date"))})</li>' for r in rates.values())
        return (head(name, desc) + (f'<section><h2>구별 빌딩 평당가</h2>{gu_table(rows)}</section>' if rows else "")
                + (f'<section><h2>금리·환율·은행 대출 금리</h2><ul>{rate_items}</ul><p class="foot-note">출처: 한국은행 경제통계시스템(ECOS)</p></section>' if rates else ""))
    if slug == "column":
        return head(name, desc) + columns_list(cols)
    return head(name, desc)


# ---------------------------------------------------------------- 머리말 (SEO)
def seo_head(slug, path, title, desc, data, noindex=False):
    url = SITE + path
    crumbs = [{"@type": "ListItem", "position": 1, "name": "CADENCE", "item": SITE + "/"}]
    if path != "/":
        crumbs.append({"@type": "ListItem", "position": 2, "name": title.split(" | ")[0], "item": url})
    graph = [
        {"@type": "WebSite", "@id": SITE + "/#website", "url": SITE + "/", "name": "CADENCE", "alternateName": "케이던스",
         "inLanguage": "ko-KR", "publisher": {"@id": SITE + "/#org"}},
        {"@type": "Organization", "@id": SITE + "/#org", "name": "CADENCE by 빌딩러너", "url": SITE + "/",
         "logo": SITE + "/assets/icon.svg", "sameAs": SOCIAL},
        {"@type": "WebPage", "@id": url + "#page", "url": url, "name": title, "description": desc, "inLanguage": "ko-KR",
         "isPartOf": {"@id": SITE + "/#website"}, "dateModified": data.get("updatedAt", "")},
        {"@type": "BreadcrumbList", "itemListElement": crumbs},
    ]
    if slug == "column":
        posts = [c for c in data.get("columns", []) if c.get("type") == "blog"][:20]
        graph.append({"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": c["link"], "name": c["title"]} for i, c in enumerate(posts)]})
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("</", "<\\/")
    img = SITE + "/assets/og-image.png"
    return "\n".join([
        f"<title>{e(title)}</title>",
        f'<meta name="description" content="{e(desc)}">',
        f'<meta name="robots" content="{"noindex,follow" if noindex else "index,follow,max-image-preview:large"}">',
        f'<link rel="canonical" href="{e(url)}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="CADENCE">',
        '<meta property="og:locale" content="ko_KR">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(desc)}">',
        f'<meta property="og:url" content="{e(url)}">',
        f'<meta property="og:image" content="{img}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{e(title)}">',
        f'<meta name="twitter:description" content="{e(desc)}">',
        f'<meta name="twitter:image" content="{img}">',
        f'<script type="application/ld+json">{ld}</script>',
    ])


def build() -> None:
    template = (ROOT / "index.html").read_text(encoding="utf-8")
    data_path = ROOT / "data" / "live.json"
    data = json.loads(data_path.read_text(encoding="utf-8")) if data_path.exists() else {}
    guide = json.loads((ROOT / "content" / "guide.json").read_text(encoding="utf-8"))
    guide_js = "<script>window.GUIDE_DATA = " + json.dumps(guide, ensure_ascii=False).replace("</", "<\\/") + ";</script>"

    a, b = template.index("<!--SEO:start-->"), template.index("<!--SEO:end-->") + len("<!--SEO:end-->")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    def page(slug, path, name, title, desc, noindex=False):
        out = template[:a] + seo_head(slug, path, title, desc, data, noindex) + template[b:]
        out = out.replace("<!--DATA-->", guide_js, 1)
        body = prerender(slug, name, desc, data, guide) if not noindex else head("찾는 페이지가 없습니다", "주소가 바뀌었거나 없어진 페이지입니다.")
        return out.replace("<!--PRERENDER-->", body, 1)

    for slug, path, name, title, desc in ROUTES:
        target = OUT / path.strip("/") / "index.html" if path != "/" else OUT / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page(slug, path, name, title, desc), encoding="utf-8")
    (OUT / "404.html").write_text(page("404", "/404.html", "없는 페이지", "찾는 페이지가 없습니다 | CADENCE", "주소가 바뀌었거나 없어진 페이지입니다.", noindex=True), encoding="utf-8")

    for d in ("data", "assets"):
        if (ROOT / d).exists():
            shutil.copytree(ROOT / d, OUT / d, dirs_exist_ok=True)

    lastmod = (data.get("updatedAt") or dt.datetime.now(dt.timezone.utc).isoformat())[:10]
    urls = "".join(f"<url><loc>{SITE}{path}</loc><lastmod>{lastmod}</lastmod><changefreq>{'hourly' if slug in ('home', 'deal', 'data', 'market') else 'daily'}</changefreq></url>"
                   for slug, path, *_ in ROUTES if slug not in ("sell", "buy"))
    (OUT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")
    print(f"빌드 완료: {OUT} (페이지 {len(ROUTES)}개 + 404, sitemap.xml, robots.txt)")


if __name__ == "__main__":
    build()
