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
# IndexNow 키 (빙·네이버 등에 새 페이지를 알릴 때 씀. 공개되는 값)
INDEXNOW_KEY = "c572e823172e060b976bb235ecc05f45"
# 검색엔진 소유 확인 코드 (구글 서치 콘솔 / 네이버 서치어드바이저에서 받은 content 값)
SITE_VERIFICATION = {"google-site-verification": "", "naver-site-verification": ""}
SOCIAL = [
    "https://www.youtube.com/@building_runner_official",
    "https://www.instagram.com/building_runner/",
    "https://blog.naver.com/morrison119",
]

ROUTES = [
    # slug, 경로, 이름, 페이지 제목, 설명
    ("home", "/", "홈", "서울 빌딩 시세·실거래가, 꼬마빌딩·상업용 부동산 정보 | CADENCE",
     "서울 빌딩 실거래가와 권역·구·동별 평당가, 은행 대출 금리, 오피스 공실률, 상업용 부동산 뉴스를 3시간마다 모아 보여 주는 빌딩러너의 상업용 부동산 매거진."),
    ("price", "/price/", "시세", "서울 빌딩 시세: 권역·구·동별 평당가 | CADENCE",
     "국토교통부 실거래로 계산한 서울 빌딩 토지·연면적 평당가. CBD·GBD·YBD 권역, 25개 구, 동별, 준공 연도별·용도별 평당가와 월별 거래 건수."),
    ("deal", "/deal/", "실거래", "서울 빌딩 매매 실거래가 검색 | CADENCE",
     "국토교통부 신고 자료로 서울 빌딩·꼬마빌딩 매매 실거래가를 구·용도·금액대·기간별로 검색하고 이번 달 큰 거래와 매매 뉴스를 봅니다."),
    ("report", "/report/", "시장 리포트", "상업용 부동산 시장 리포트: 오피스 공실률·거래액·금리 | CADENCE",
     "한국부동산원·알스퀘어·JLL·CBRE의 분기 오피스 공실률과 거래액, 금리와 은행 대출 금리, 상장 리츠 시세를 한곳에 모았습니다."),
    ("policy", "/guide/", "건물주 가이드", "건물주 가이드: 빌딩 취득세·중개보수·상가임대차보호법·RTI 계산기 | CADENCE",
     "빌딩 취득세 4.6%, 중개보수 0.9% 이내, 건물분 부가세, 상가임대차보호법 환산보증금, 임대업 대출 RTI 기준을 근거 법령과 함께 정리하고 계산기로 확인합니다."),
    ("news", "/news/", "뉴스", "상업용 부동산 뉴스: 오피스·빌딩 매매·리츠·정책 | CADENCE",
     "오피스·상가·빌딩 매매·리츠·정책 등 상업용 부동산 뉴스를 언론사 원문 링크로 모았습니다. 3시간마다 갱신합니다."),
    ("column", "/column/", "칼럼", "빌딩러너 칼럼: 상권과 빌딩 가치 분석 | CADENCE",
     "빌딩러너가 상권과 빌딩 가치를 숫자로 풀어 쓴 칼럼을 모았습니다."),
    ("inquiry", "/inquiry/", "매도·매수 의뢰", "빌딩 매도·매수 의뢰 | CADENCE",
     "팔고 싶은 빌딩, 찾고 있는 빌딩을 남겨 주세요. 빌딩러너가 조건을 검토해 연락드립니다."),
    ("sell", "/sell/", "매도 의뢰", "빌딩 매도 의뢰 | CADENCE",
     "팔고 싶은 빌딩의 지번과 조건을 남겨 주세요. 빌딩러너가 검토해 연락드립니다."),
    ("buy", "/buy/", "매수 의뢰", "빌딩 매수 의뢰 | CADENCE",
     "찾고 있는 빌딩의 지역과 예산을 남겨 주세요. 빌딩러너가 검토해 연락드립니다."),
]
# 예전 주소 → 새 주소
REDIRECTS = {"/market/": "/news/", "/building/": "/news/", "/players/": "/news/", "/data/": "/price/"}
GU_SLUG = {"강남구": "gangnam", "서초구": "seocho", "송파구": "songpa", "강동구": "gangdong", "종로구": "jongno", "중구": "jung",
           "용산구": "yongsan", "성동구": "seongdong", "광진구": "gwangjin", "동대문구": "dongdaemun", "중랑구": "jungnang", "성북구": "seongbuk",
           "강북구": "gangbuk", "도봉구": "dobong", "노원구": "nowon", "은평구": "eunpyeong", "서대문구": "seodaemun", "마포구": "mapo",
           "양천구": "yangcheon", "강서구": "gangseo", "구로구": "guro", "금천구": "geumcheon", "영등포구": "yeongdeungpo", "동작구": "dongjak", "관악구": "gwanak"}
TOPIC = {"market": "시장·임대", "deal": "매매·투자", "building": "개발·리모델링", "policy": "정책·세금·금융", "players": "리츠·운용사"}

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
        f'<li><a href="{e(n["link"])}" rel="noopener" target="_blank"><small>{e(TOPIC.get(n.get("section"), ""))}</small> <b>{e(n["title"])}</b>'
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


def gu_links():
    return "<nav class=\"gu-chips\">" + "".join(f'<a href="/seoul/{v}/">{e(k)} 빌딩 시세</a>' for k, v in GU_SLUG.items()) + "</nav>"


def market_board(market):
    out = []
    for g in market.get("groups", []):
        items = "".join(f"<dt>{e(i['label'])}</dt><dd>{e(i['value'])}</dd>" for i in g["items"])
        links = "".join(f'<li><a href="{e(l["url"])}" rel="noopener" target="_blank">{e(l["title"])}</a></li>' for l in g["links"])
        out.append(f'<article class="mb"><header><b>{e(g["source"])}</b><span>{e(g["kind"])}</span></header><dl>{items}</dl><ul class="mb-links">{links}</ul></article>')
    return f'<div class="board-grid">{"".join(out)}</div><p class="foot-note">{e(market.get("quarter"))} 기준 · {e(market.get("note"))}</p>'


def prerender(slug, name, desc, data, guide, market, gu=None):
    news = data.get("news", [])
    rows = ((data.get("deals") or {}).get("history") or {}).get("rows", [])
    cols = data.get("columns", [])
    if gu:
        rs = [r for r in rows if r["gu"] == gu]
        by = {}
        for r in rs:
            by.setdefault(r["dong"], []).append(r)
        dong = sorted(((d, med([land_py(r) for r in v]), len(v)) for d, v in by.items() if len(v) >= 2), key=lambda x: -x[1])
        dong_rows = "".join(f"<tr><td>{e(d)}</td><td>{l:,.0f}만 원</td><td>{n}</td></tr>" for d, l, n in dong)
        return (f'<section class="cat-head"><div><p class="crumb"><a href="/price/">서울 빌딩 시세</a> › {e(gu)}</p><h1>{e(gu)} 빌딩 시세·실거래가</h1>'
                f'<p>{e(desc)}</p></div></section>'
                + (f'<section><h2>{e(gu)} 빌딩 평당가 요약</h2><ul><li>토지 3.3㎡당 중위값: {med([land_py(r) for r in rs]):,.0f}만 원</li>'
                   f'<li>연면적 3.3㎡당 중위값: {med([gfa_py(r) for r in rs]):,.0f}만 원</li><li>중위 거래금액: {eok(med([r["amount"] for r in rs]))}억 원</li>'
                   f'<li>거래 건수: {len(rs)}건</li></ul></section>' if rs else "")
                + (f'<section><h2>{e(gu)} 동별 평당가</h2><div class="table-scroll"><table class="gustats"><thead><tr><th>동</th><th>토지 3.3㎡당</th><th>거래 건수</th></tr></thead><tbody>{dong_rows}</tbody></table></div></section>' if dong_rows else "")
                + (f'<section><h2>{e(gu)} 최근 실거래</h2>{deals_table(rs, 20)}</section>' if rs else "")
                + f'<section><h2>다른 구 시세</h2>{gu_links()}</section>')
    if slug == "home":
        top = ((data.get("deals") or {}).get("top") or [None])[0]
        land = med([land_py(r) for r in rows]) if rows else 0
        lead = ('<section class="hero"><div class="hero-head"><h1>서울 빌딩 시세와 실거래, 오늘의 숫자</h1>'
                f'<p>{e(desc)}</p></div><ul>'
                + (f"<li>서울 빌딩 토지 3.3㎡당 중위값 {land / 10000:,.2f}억 원 (국토교통부 실거래 {len(rows)}건)</li>" if land else "")
                + (f'<li>이번 달 최대 거래: 서울 {e(top["gu"])} {e(top["dong"])} {e(top.get("use"))} {eok(top["amount"])}억 원 ({e(top["date"])})</li>' if top else "")
                + "</ul></section>")
        return (lead
                + (f'<section><h2>최신 상업용 부동산 뉴스</h2>{news_list(news, 12)}</section>' if news else "")
                + (f'<section><h2>서울 구별 빌딩 평당가</h2>{gu_table(rows)}</section>' if rows else "")
                + f'<section><h2>구별 빌딩 시세 바로 보기</h2>{gu_links()}</section>'
                + (f'<section><h2>빌딩러너 칼럼</h2>{columns_list(cols, 5)}</section>' if cols else "")
                + f'<section><h2>기관별 시장 지표</h2>{market_board(market)}</section>')
    if slug == "price":
        return head(name, desc) + (f'<section><h2>구별 빌딩 평당가</h2>{gu_table(rows)}</section>' if rows else "") + f'<section><h2>구별 상세</h2>{gu_links()}</section>'
    if slug == "deal":
        return (head(name, desc) + (deals_table(rows, 30) if rows else "")
                + news_list([n for n in news if n.get("section") == "deal"], 20))
    if slug == "report":
        rates = data.get("rates", {})
        rate_items = "".join(f'<li>{e(r["name"])}: {r["value"]}{e(r.get("unit"))} ({e(r.get("date"))})</li>' for r in rates.values())
        return (head(name, desc) + f'<section><h2>기관별 시장 지표</h2>{market_board(market)}</section>'
                + (f'<section><h2>금리·환율·은행 대출 금리</h2><ul>{rate_items}</ul><p class="foot-note">출처: 한국은행 경제통계시스템(ECOS)</p></section>' if rates else "")
                + news_list([n for n in news if n.get("section") in ("market", "players")], 20))
    if slug == "policy":
        facts = "".join(
            f'<article class="fact"><h3>{e(f["q"])}</h3><p class="fact-a">{e(f["a"])}</p><p>{e(f["d"])}</p>'
            f'<p class="fact-src">근거: {e(f.get("law") or f.get("src"))}</p></article>' for f in guide.get("facts", []))
        return (head(name, desc) + f'<section><h2>건물주가 가장 많이 묻는 기준</h2><div class="facts">{facts}</div>'
                f'<p class="foot-note">{e(guide.get("checked"))} 기준으로 법령과 공개 자료를 확인해 정리했습니다.</p></section>'
                + news_list([n for n in news if n.get("section") == "policy"], 20))
    if slug == "news":
        return head(name, desc) + news_list(news, 60)
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
    ] + [f'<meta name="{k}" content="{e(v)}">' for k, v in SITE_VERIFICATION.items() if v])


def build() -> None:
    template = (ROOT / "index.html").read_text(encoding="utf-8")
    data_path = ROOT / "data" / "live.json"
    data = json.loads(data_path.read_text(encoding="utf-8")) if data_path.exists() else {}
    guide = json.loads((ROOT / "content" / "guide.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / "content" / "market.json").read_text(encoding="utf-8"))
    guide_js = ("<script>window.GUIDE_DATA = " + json.dumps(guide, ensure_ascii=False).replace("</", "<\\/") + ";\n"
                "window.MARKET_DATA = " + json.dumps(market, ensure_ascii=False).replace("</", "<\\/") + ";</script>")

    a, b = template.index("<!--SEO:start-->"), template.index("<!--SEO:end-->") + len("<!--SEO:end-->")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    def page(slug, path, name, title, desc, noindex=False, gu=None):
        out = template[:a] + seo_head(slug, path, title, desc, data, noindex) + template[b:]
        out = out.replace("<!--DATA-->", guide_js, 1)
        body = prerender(slug, name, desc, data, guide, market, gu) if not noindex else head("찾는 페이지가 없습니다", "주소가 바뀌었거나 없어진 페이지입니다.")
        return out.replace("<!--PRERENDER-->", body, 1)

    rows = ((data.get("deals") or {}).get("history") or {}).get("rows", [])
    months = ((data.get("deals") or {}).get("history") or {}).get("months", [])
    period = f"{months[0][:4]}.{months[0][4:]}~{months[-1][:4]}.{months[-1][4:]}" if months else ""
    for gu, gslug in GU_SLUG.items():
        n = sum(1 for r in rows if r["gu"] == gu)
        path = f"/seoul/{gslug}/"
        title = f"{gu} 빌딩 시세·실거래가 (토지·연면적 평당가) | CADENCE"
        desc = (f"서울 {gu} 빌딩·꼬마빌딩 매매 실거래가와 동별 토지·연면적 평당가. 국토교통부 신고 자료"
                + (f" {period} {n}건" if n else "") + " 기준, 3시간마다 갱신합니다.")
        target = OUT / "seoul" / gslug / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page("gu", path, gu, title, desc, gu=gu), encoding="utf-8")
    for old, new in REDIRECTS.items():
        t = OUT / old.strip("/") / "index.html"
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(f'<!doctype html><meta charset="utf-8"><title>이동합니다</title><link rel="canonical" href="{SITE}{new}">'
                     f'<meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url={new}">'
                     f'<a href="{new}">새 주소로 이동</a>', encoding="utf-8")

    for slug, path, name, title, desc in ROUTES:
        target = OUT / path.strip("/") / "index.html" if path != "/" else OUT / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page(slug, path, name, title, desc), encoding="utf-8")
    (OUT / "404.html").write_text(page("404", "/404.html", "없는 페이지", "찾는 페이지가 없습니다 | CADENCE", "주소가 바뀌었거나 없어진 페이지입니다.", noindex=True), encoding="utf-8")

    for d in ("data", "assets"):
        if (ROOT / d).exists():
            shutil.copytree(ROOT / d, OUT / d, dirs_exist_ok=True)

    lastmod = (data.get("updatedAt") or dt.datetime.now(dt.timezone.utc).isoformat())[:10]
    urls = "".join(f"<url><loc>{SITE}{path}</loc><lastmod>{lastmod}</lastmod><changefreq>{'hourly' if slug in ('home', 'deal', 'price', 'news') else 'daily'}</changefreq></url>"
                   for slug, path, *_ in ROUTES if slug not in ("sell", "buy"))
    urls += "".join(f"<url><loc>{SITE}/seoul/{v}/</loc><lastmod>{lastmod}</lastmod><changefreq>daily</changefreq></url>" for v in GU_SLUG.values())
    (OUT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")
    (OUT / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY, encoding="utf-8")
    (OUT / "indexnow-urls.txt").write_text("\n".join([SITE + p for _, p, *_ in ROUTES if p not in ("/sell/", "/buy/")]
                                                     + [f"{SITE}/seoul/{v}/" for v in GU_SLUG.values()]), encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")
    print(f"빌드 완료: {OUT} (페이지 {len(ROUTES)}개 + 구별 {len(GU_SLUG)}개 + 404, sitemap.xml, robots.txt)")


if __name__ == "__main__":
    build()
