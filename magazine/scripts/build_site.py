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
import re
import shutil
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # magazine/
OUT = ROOT.parent / "_site"
SITE = "https://cadence.bldgrunner.com"
PYEONG = 3.3058
KST = dt.timezone(dt.timedelta(hours=9))
# IndexNow 키 (빙·네이버 등에 새 페이지를 알릴 때 씀. 공개되는 값)
INDEXNOW_KEY = "c572e823172e060b976bb235ecc05f45"
# 검색엔진 소유 확인 코드 (구글 서치 콘솔 / 네이버 서치어드바이저에서 받은 content 값)
# 코드를 받으면 "" 안에 넣고 배포하면 모든 페이지 <head>에 들어갑니다. 비어 있으면 자리 표시 주석만 남습니다.
SITE_VERIFICATION = {
    "naver-site-verification": "",    # 네이버 서치어드바이저 > 사이트 등록 > HTML 태그의 content 값
    "google-site-verification": "",   # 구글 서치 콘솔 > URL 접두어 > HTML 태그의 content 값
}
# Google Analytics 4 측정 ID (예: "G-ABC123XYZ9"). 비어 있으면 분석 코드를 넣지 않습니다.
GA4_ID = ""
SOCIAL = [
    "https://blog.naver.com/morrison119",
    "https://www.youtube.com/@building_runner_official",
    "https://www.threads.net/@building_runner",
    "https://cafe.daangn.com/geonmulju-doego",
]

ROUTES = [
    # slug, 경로, 이름, 페이지 제목, 설명
    ("home", "/", "홈", "서울 빌딩 시세·실거래가 | CADENCE 매거진",
     "서울 25개 구 빌딩 실거래가·평당가, 오피스 공실률, 대출 금리와 상업용 부동산 리포트를 3시간마다 정리하는 빌딩러너의 데이터 매거진."),
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
    ("lookup", "/lookup/", "내 건물 시세 비교", "내 빌딩 시세 비교: 같은 동 실거래·평당가 | CADENCE",
     "구·동·지번을 넣으면 같은 동과 같은 구의 빌딩 매매 실거래, 토지·연면적 평당가 범위를 국토교통부 신고 자료로 바로 비교합니다."),
    ("dealsheet", "/deal-sheet/", "주간 딜 시트", "이번 주 서울 빌딩 딜 시트: 새로 공개된 매매 실거래 | CADENCE",
     "최근 7일 동안 국토교통부 실거래 자료에 새로 공개된 서울 빌딩 매매 거래를 금액 순으로 모았습니다. 매주 자동으로 쌓입니다."),
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
        f'<li><a href="{e(n["link"])}" rel="noopener noreferrer" target="_blank"><small>{e(TOPIC.get(n.get("section"), ""))}</small> <b>{e(n["title"])}</b>'
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
        f'<li><a href="{e(col_path(c))}"><b>{e(c["title"])}</b>'
        f'<small>빌딩러너 칼럼 · {e((c.get("date") or "")[:10])}</small></a>'
        + (f'<p>{e(c.get("summary"))}</p>' if c.get("summary") else "") + "</li>" for c in cols)
    return f'<ol class="headlines">{items}</ol>'


def col_path(c):
    return f"/column/{c['id']}/" if c.get("id") else c["link"]


# 칼럼 제목·요약에 나오는 동네 → 실거래 데이터 연결
AREA_STOP = {"내수", "효자", "신정", "중앙", "대흥", "신원", "사직", "공항", "신문", "원서", "화양", "중림", "본동", "광장", "동작"}
# 실거래 동 이름에 없는 널리 쓰는 지명 → 구
AREA_ALIAS = {"압구정": ("강남구", "압구정동"), "가로수길": ("강남구", "신사동"), "청담": "강남구", "테헤란로": "강남구", "강남역": "강남구",
              "한남": "용산구", "용리단길": "용산구", "신용산": "용산구", "이태원": "용산구", "해방촌": "용산구",
              "성수": "성동구", "을지로": "중구", "명동": "중구", "여의도": "영등포구", "문래": "영등포구",
              "연남": "마포구", "홍대": "마포구", "합정": "마포구", "망원": "마포구", "잠실": "송파구",
              "익선": "종로구", "서촌": "종로구", "북촌": "종로구", "반포": ("서초구", "반포동"), "잠수교": ("서초구", "반포동")}


def area_index(rows):
    """{지명: [(구, 동 또는 None, 거래 건수)]}. 예: '여의도' → [('영등포구', '여의도동', n)]"""
    count = {}
    for r in rows:
        count[(r["gu"], r["dong"])] = count.get((r["gu"], r["dong"]), 0) + 1
    idx = {}
    for (gu, dong), n in count.items():
        base = re.sub(r"\d+가$", "", dong)
        for k in {dong, base, re.sub(r"\d*동$", "", base)}:
            if len(k) >= 2 and k not in AREA_STOP:
                idx.setdefault(k, []).append((gu, dong, n))
    for k, v in AREA_ALIAS.items():
        gu, dong = v if isinstance(v, tuple) else (v, None)
        idx.setdefault(k, []).append((gu, dong, count.get((gu, dong), 0)))
    for gu in GU_SLUG:
        for k in {gu, gu[:-1]}:
            if len(k) >= 2 and k not in AREA_STOP:
                idx.setdefault(k, []).append((gu, None, 0))
    return idx


def _area_hits(text, idx):
    hits, taken = [], [False] * len(text)
    for k in sorted(idx, key=len, reverse=True):
        i = text.find(k)
        if i >= 0 and not any(taken[i:i + len(k)]):
            taken[i:i + len(k)] = [True] * len(k)
            hits.append((i, max(idx[k], key=lambda x: x[2])))
    return [h for _, h in sorted(hits)]


def areas_for(title, summary, idx, limit=2):
    """제목에 나온 지명을 먼저, 모자라면 요약에서. 같은 구는 한 번만."""
    found = {}
    for gu, dong, _ in _area_hits(title, idx) + _area_hits(summary or "", idx):
        if gu not in found:
            found[gu] = dong
        elif not found[gu] and dong:
            found[gu] = dong   # 같은 구면 동까지 알려 주는 쪽을 쓴다
    return list(found.items())[:limit]


def area_block(c, rows, idx):
    out = []
    for gu, dong in areas_for(c["title"], c.get("summary"), idx):
        g = [r for r in rows if r["gu"] == gu]
        d = [r for r in g if dong and r["dong"] == dong]
        line = []
        if len(d) >= 2:
            line.append(f'<li>{e(gu)} {e(dong)}: 최근 12개월 실거래 {len(d)}건, 토지 3.3㎡당 중위 {med([land_py(r) for r in d]):,.0f}만 원</li>')
        if g:
            line.append(f'<li>{e(gu)} 전체: 실거래 {len(g)}건, 토지 3.3㎡당 중위 {med([land_py(r) for r in g]):,.0f}만 원 · '
                        f'<a href="/seoul/{GU_SLUG[gu]}/">{e(gu)} 빌딩 시세 보기</a></li>')
        out += line
    if not out:
        return ""
    return (f'<section><h2>이 글 속 지역의 실거래 데이터</h2><ul>{"".join(out)}</ul>'
            '<p class="foot-note">출처: 국토교통부 상업업무용 부동산 매매 신고 자료 · 서울 건물 단위 거래 · 중위값</p></section>')


def column_page(c, cols, rows, idx):
    others = [x for x in cols if x.get("id") and x["id"] != c["id"]][:6]
    return (f'<article class="col-detail"><p><a href="/column/">빌딩러너 칼럼</a>{" · " + e(c.get("tag")) if c.get("tag") else ""}</p>'
            f'<h1>{e(c["title"])}</h1><p>빌딩러너 · {e((c.get("date") or "")[:10])}</p>'
            + (f'<img src="{e(c["image"])}" alt="{e(c["title"])}" referrerpolicy="no-referrer">' if c.get("image") else "")
            + (f'<p>{e(c.get("summary"))}…</p>' if c.get("summary") else "")
            + f'<p><a href="{e(c["link"])}" rel="noopener noreferrer" target="_blank">네이버 블로그에서 전체 글 읽기</a></p></article>'
            + area_block(c, rows, idx)
            + (f'<section><h2>다른 칼럼</h2>{columns_list(others)}</section>' if others else ""))


# ---------------------------------------------------------------- 월간 거래 리포트 (/report/YYYY-MM/)
BANDS = [("10억 미만", 0, 100000), ("10억~50억", 100000, 500000), ("50억~100억", 500000, 1000000),
         ("100억~300억", 1000000, 3000000), ("300억 이상", 3000000, float("inf"))]


def month_key(r):
    return r["date"][:4] + r["date"][5:7]


def month_label(m):
    return f"{m[:4]}년 {int(m[4:])}월"


def month_slug(m):
    return f"{m[:4]}-{m[4:]}"


def month_settled(m, today):
    """신고 기한(계약 후 30일)이 지나 숫자가 거의 확정된 달인지: 다음 달 말일이 지났으면 확정."""
    y, mo = int(m[:4]), int(m[4:])
    y2, mo2 = (y, mo + 2) if mo <= 10 else (y + 1, mo - 10)
    return today >= dt.date(y2, mo2, 1)


def pct(a, b):
    return f"{(a - b) / b * 100:+.1f}%" if b else "-"


def kpi_html(label, value, unit, sub):
    return (f'<div class="kpi"><span class="kpi-l">{e(label)}</span><strong>{value}<em>{e(unit)}</em></strong>'
            f'<span class="kpi-s">{sub}</span><span class="kpi-src">국토교통부 실거래</span></div>')


def monthly_page(m, months, rows, today):
    rs = [r for r in rows if month_key(r) == m]
    i = months.index(m)
    prev = months[i - 1] if i > 0 else None
    ps = [r for r in rows if prev and month_key(r) == prev]
    total, ptotal = sum(r["amount"] for r in rs), sum(r["amount"] for r in ps)
    settled = month_settled(m, today)
    status = ("확정치에 가까운 숫자입니다 (신고 기한이 지났습니다)." if settled else
              "잠정치입니다. 계약 후 30일 안에 신고되므로 이 달 거래는 앞으로 더 늘어납니다.")
    vs = f"전월 {len(ps)}건" if prev else "전월 자료 없음"
    kpis = (kpi_html("거래 건수", f"{len(rs):,}", "건", f'{e(vs)}{" · " + pct(len(rs), len(ps)) if prev else ""}')
            + kpi_html("거래금액 합계", f"{total / 10000:,.0f}", "억 원", f'{"전월 대비 " + pct(total, ptotal) if prev else ""}')
            + kpi_html("중위 거래금액", eok(med([r["amount"] for r in rs])), "억 원", "건물 단위 매매")
            + kpi_html("토지 3.3㎡당 중위", f"{med([land_py(r) for r in rs]):,.0f}", "만 원", "서울 전체"))
    band_rows = "".join(
        f'<tr><td>{e(n)}</td><td class="r hl">{sum(1 for r in rs if lo <= r["amount"] < hi)}</td>'
        f'<td class="r">{sum(1 for r in ps if lo <= r["amount"] < hi) if prev else "-"}</td>'
        f'<td class="r">{sum(r["amount"] for r in rs if lo <= r["amount"] < hi) / 10000:,.0f}</td></tr>' for n, lo, hi in BANDS)
    by = {}
    for r in rs:
        by.setdefault(r["gu"], []).append(r)
    gu_rows = "".join(
        f'<tr><td><a href="/seoul/{GU_SLUG.get(g, "")}/"><b>{e(g)}</b></a></td><td class="r hl">{len(v)}</td>'
        f'<td class="r">{sum(r["amount"] for r in v) / 10000:,.0f}</td><td class="r">{med([land_py(r) for r in v]):,.0f}</td></tr>'
        for g, v in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0])))
    corp = sum(1 for r in rs if r.get("buyer") == "법인")
    indiv = sum(1 for r in rs if r.get("buyer") == "개인")
    top = sorted(rs, key=lambda r: -r["amount"])[:10]
    top_rows = "".join(
        f'<tr><td class="num">{e(r["date"])}</td><td><b>{e(r["gu"])} {e(r["dong"])}</b></td><td>{e(r.get("use") or "")}</td>'
        f'<td class="r"><b>{eok(r["amount"])}</b></td><td class="r hl">{land_py(r):,.0f}</td></tr>' for r in top)
    nav = " · ".join(f'<a href="/report/{month_slug(x)}/">{month_label(x)}</a>' if x != m else f"<b>{month_label(x)}</b>"
                     for x in reversed(months))
    sec = lambda t: f'<div class="sec-head"><h2>{e(t)}</h2></div>'
    note = '<p class="foot-note">출처: 국토교통부 상업업무용 부동산 매매 신고 자료 · 서울 25개 구 건물 단위(일반) 거래 · 지분 거래 제외 · 건물명과 지번은 공개되지 않습니다.</p>'
    return (f'<section class="cat-head"><div class="big">3F</div><div><h1>{month_label(m)} 서울 빌딩 매매 거래 리포트</h1>'
            f'<p>국토교통부 실거래 신고 자료로 집계한 {month_label(m)} 서울 빌딩(상업·업무용 건물) 매매 거래입니다. {e(status)}</p></div></section>'
            f'<section><div class="kpis four">{kpis}</div>{note}</section>'
            f'<section>{sec("금액대별 거래")}<div class="table-scroll"><table class="gustats"><thead><tr><th>금액대</th><th class="r">거래 건수</th>'
            f'<th class="r">전월</th><th class="r">거래금액 합계 (억 원)</th></tr></thead><tbody>{band_rows}</tbody></table></div></section>'
            f'<section>{sec("매수자")}<p>법인 {corp}건 · 개인 {indiv}건'
            f'{" · 기타·미상 " + str(len(rs) - corp - indiv) + "건" if len(rs) - corp - indiv else ""}</p></section>'
            f'<section>{sec("구별 거래")}<div class="table-scroll"><table class="gustats"><thead><tr><th>구</th><th class="r">거래 건수</th>'
            f'<th class="r">거래금액 합계 (억 원)</th><th class="r">토지 3.3㎡당 중위 (만 원)</th></tr></thead><tbody>{gu_rows}</tbody></table></div></section>'
            f'<section>{sec("금액 상위 거래")}<div class="table-scroll"><table class="deals"><thead><tr><th>계약일</th><th>위치</th><th>용도</th>'
            f'<th class="r">거래금액 (억 원)</th><th class="r">토지 3.3㎡당 (만 원)</th></tr></thead><tbody>{top_rows}</tbody></table></div>{note}</section>'
            f'<section>{sec("다른 달 리포트")}<p>{nav}</p><p><a href="/deal/">서울 빌딩 실거래 검색 →</a></p></section>')


# ---------------------------------------------------------------- 주간 딜 시트 (/deal-sheet/)
def week_of(d: dt.date):
    y, w, _ = d.isocalendar()
    return f"{y}-w{w:02d}"


def week_range(slug):
    y, w = int(slug[:4]), int(slug[6:])
    mon = dt.date.fromisocalendar(y, w, 1)
    return mon, mon + dt.timedelta(days=6)


def week_label(slug):
    a, b = week_range(slug)
    return f"{a.year}년 {a.month}월 {a.day}일~{b.month}월 {b.day}일"


def sheet_rows(rows, start, end):
    return sorted([r for r in rows if r.get("seen") and start.isoformat() <= r["seen"] <= end.isoformat()],
                  key=lambda r: -r["amount"])


def deal_sheet(title, period, rs, weeks, current=None):
    sec = lambda t: f'<div class="sec-head"><h2>{e(t)}</h2></div>'
    note = ('<p class="foot-note">출처: 국토교통부 상업업무용 부동산 매매 신고 자료 · 서울 25개 구 건물 단위 거래 · '
            '"공개일"은 CADENCE가 3시간마다 받는 자료에 이 거래가 처음 나타난 날입니다 (계약 후 30일 안에 신고). 건물명과 지번은 공개되지 않습니다.</p>')
    if rs:
        total = sum(r["amount"] for r in rs)
        by = {}
        for r in rs:
            by[r["gu"]] = by.get(r["gu"], 0) + 1
        kpis = (kpi_html("새로 공개된 거래", f"{len(rs):,}", "건", e(period))
                + kpi_html("거래금액 합계", f"{total / 10000:,.0f}", "억 원", "건물 단위 매매")
                + kpi_html("최대 거래", eok(rs[0]["amount"]), "억 원", f'{e(rs[0]["gu"])} {e(rs[0]["dong"])}')
                + kpi_html("가장 많은 구", e(max(by, key=by.get)), "", f"{max(by.values())}건"))
        body = "".join(
            f'<tr><td class="num">{e(r["seen"][5:].replace("-", "."))}</td><td class="num">{e(r["date"])}</td><td><b>{e(r["gu"])} {e(r["dong"])}</b></td>'
            f'<td>{e(r.get("use") or "")}</td><td class="r">{r["landArea"] / PYEONG:,.1f}</td><td class="r">{r["buildingArea"] / PYEONG:,.1f}</td>'
            f'<td class="r">{e(r.get("built") or "-")}</td><td class="r"><b>{eok(r["amount"])}</b></td><td class="r hl">{land_py(r):,.0f}</td>'
            f'<td>{e(r.get("seller") or "-")}→{e(r.get("buyer") or "-")}</td></tr>' for r in rs)
        main = (f'<section><div class="kpis four">{kpis}</div></section>'
                f'<section>{sec("거래 목록 (금액 순)")}<div class="table-scroll"><table class="deals"><thead><tr><th>공개일</th><th>계약일</th><th>위치</th><th>용도</th>'
                f'<th class="r">대지 (평)</th><th class="r">연면적 (평)</th><th class="r">준공</th><th class="r">거래금액 (억 원)</th>'
                f'<th class="r">토지 3.3㎡당 (만 원)</th><th>매도→매수</th></tr></thead><tbody>{body}</tbody></table></div>{note}</section>')
    else:
        main = (f'<section><p class="empty">이 기간에 새로 공개된 거래가 아직 없습니다. CADENCE는 2026년 11월 23일부터 공개일을 기록하고 있습니다.</p>{note}</section>')
    nav = " · ".join(f'<a href="/deal-sheet/{w}/">{week_label(w)}</a>' if w != current else f"<b>{week_label(w)}</b>" for w in weeks)
    return (f'<section class="cat-head"><div class="big">2F</div><div><h1>{e(title)}</h1>'
            f'<p>{e(period)} 국토교통부 실거래 자료에 새로 공개된 서울 빌딩 매매 거래입니다.</p></div></section>'
            + main
            + (f'<section>{sec("지난 딜 시트")}<p>{nav}</p></section>' if weeks else "")
            + '<section><p><a href="/deal/">서울 빌딩 실거래 검색 →</a> · <a href="/report/">월간 거래 리포트 →</a></p></section>')


def rss_feed(items, built):
    def item(t, link, desc, date):
        return (f"<item><title>{e(t)}</title><link>{e(SITE + link if link.startswith('/') else link)}</link>"
                f"<guid>{e(SITE + link if link.startswith('/') else link)}</guid><description>{e(desc)}</description>"
                f"<pubDate>{date.strftime('%a, %d %b %Y %H:%M:%S +0900')}</pubDate></item>")
    body = "".join(item(*x) for x in sorted(items, key=lambda x: x[3], reverse=True)[:60])
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
            f'<title>CADENCE · 서울 빌딩 시세·실거래</title><link>{SITE}/</link>'
            f'<atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>'
            '<description>서울 빌딩 월간 거래 리포트, 주간 딜 시트, 빌딩러너 칼럼</description><language>ko</language>'
            f"<lastBuildDate>{built.strftime('%a, %d %b %Y %H:%M:%S +0900')}</lastBuildDate>{body}</channel></rss>\n")


def gu_links():
    return "<nav class=\"gu-chips\">" + "".join(f'<a href="/seoul/{v}/">{e(k)} 빌딩 시세</a>' for k, v in GU_SLUG.items()) + "</nav>"


def market_board(market):
    out = []
    for g in market.get("groups", []):
        items = "".join(f"<dt>{e(i['label'])}</dt><dd>{e(i['value'])}</dd>" for i in g["items"])
        links = "".join(f'<li><a href="{e(l["url"])}" rel="noopener noreferrer" target="_blank">{e(l["title"])}</a></li>' for l in g["links"])
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
    if slug == "dealsheet":
        today = dt.datetime.now(KST).date()
        start = today - dt.timedelta(days=6)
        weeks = sorted({week_of(dt.date.fromisoformat(r["seen"])) for r in rows if r.get("seen")}, reverse=True)[:12]
        return deal_sheet("이번 주 서울 빌딩 딜 시트", f"최근 7일({start.month}월 {start.day}일~{today.month}월 {today.day}일)",
                          sheet_rows(rows, start, today), weeks)
    if slug == "lookup":
        return head("내 건물 시세 비교", desc) + f'<section><h2>구별 빌딩 시세</h2>{gu_links()}</section>'
    return head(name, desc)


# ---------------------------------------------------------------- 머리말 (SEO)
def seo_head(slug, path, title, desc, data, noindex=False, post=None):
    url = SITE + path
    crumbs = [{"@type": "ListItem", "position": 1, "name": "CADENCE", "item": SITE + "/"}]
    if post:
        crumbs.append({"@type": "ListItem", "position": 2, "name": "빌딩러너 칼럼", "item": SITE + "/column/"})
        crumbs.append({"@type": "ListItem", "position": 3, "name": post["title"], "item": url})
    elif path != "/":
        crumbs.append({"@type": "ListItem", "position": 2, "name": title.split(" | ")[0], "item": url})
    graph = [
        {"@type": "WebSite", "@id": SITE + "/#website", "url": SITE + "/", "name": "CADENCE", "alternateName": "케이던스 매거진",
         "inLanguage": "ko-KR", "publisher": {"@id": SITE + "/#org"},
         "potentialAction": {"@type": "SearchAction", "target": SITE + "/?q={search_term_string}",
                             "query-input": "required name=search_term_string"}},
        {"@type": "NewsMediaOrganization", "@id": SITE + "/#org", "name": "CADENCE by 빌딩러너", "url": SITE + "/",
         "logo": SITE + "/assets/icon.svg", "sameAs": SOCIAL},
        {"@type": "WebPage", "@id": url + "#page", "url": url, "name": title, "description": desc, "inLanguage": "ko-KR",
         "isPartOf": {"@id": SITE + "/#website"}, "dateModified": data.get("updatedAt", "")},
        {"@type": "BreadcrumbList", "itemListElement": crumbs},
    ]
    if slug == "column":
        posts = [c for c in data.get("columns", []) if c.get("type") == "blog"][:30]
        graph.append({"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": SITE + col_path(c) if c.get("id") else c["link"], "name": c["title"]}
            for i, c in enumerate(posts)]})
    if slug == "policy":   # 건물주 가이드의 질문·답 → FAQ 구조화 데이터
        facts = json.loads((ROOT / "content" / "guide.json").read_text(encoding="utf-8")).get("facts", [])
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f'{f["a"]}. {f["d"]}'}} for f in facts]})
    if post:
        graph.append({"@type": "BlogPosting", "@id": url + "#post", "headline": post["title"][:110], "description": desc,
                      "datePublished": post.get("date", ""), "inLanguage": "ko-KR", "mainEntityOfPage": {"@id": url + "#page"},
                      "author": {"@type": "Person", "name": "빌딩러너", "url": "https://blog.naver.com/morrison119"},
                      "publisher": {"@id": SITE + "/#org"}, "isBasedOn": post["link"],
                      **({"image": post["image"]} if post.get("image") else {}),
                      **({"articleSection": post["tag"]} if post.get("tag") else {})})
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("</", "<\\/")
    img = (post or {}).get("image") or SITE + "/assets/og-image.png"
    return "\n".join([
        f"<title>{e(title)}</title>",
        f'<meta name="description" content="{e(desc)}">',
        f'<meta name="robots" content="{"noindex,follow" if noindex else "index,follow,max-image-preview:large"}">',
        f'<link rel="canonical" href="{e(url)}">',
        f'<link rel="alternate" type="application/rss+xml" title="CADENCE" href="{SITE}/feed.xml">',
        f'<meta property="og:type" content="{"article" if post else "website"}">',
        '<meta property="og:site_name" content="CADENCE">',
        '<meta property="og:locale" content="ko_KR">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(desc)}">',
        f'<meta property="og:url" content="{e(url)}">',
        f'<meta property="og:image" content="{img}">',
    ] + ([] if post and post.get("image") else [
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
    ]) + [
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{e(title)}">',
        f'<meta name="twitter:description" content="{e(desc)}">',
        f'<meta name="twitter:image" content="{img}">',
        f'<script type="application/ld+json">{ld}</script>',
    ] + [f'<meta name="{k}" content="{e(v)}">' if v else f'<!-- {k}: 코드 발급 후 build_site.py SITE_VERIFICATION에 입력 -->'
         for k, v in SITE_VERIFICATION.items()]
      + ([f'<script async src="https://www.googletagmanager.com/gtag/js?id={e(GA4_ID)}"></script>',
          "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
          f"gtag('js',new Date());gtag('config','{e(GA4_ID)}');</script>"] if GA4_ID
         else ["<!-- Google Analytics 4: 측정 ID 발급 후 build_site.py GA4_ID에 입력 -->"]))


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
    cols = [c for c in data.get("columns", []) if c.get("type") == "blog" and c.get("id")]
    idx = area_index(rows)
    for c in cols:
        path = f"/column/{c['id']}/"
        title = f"{c['title']} | 빌딩러너 칼럼"
        desc = (c.get("summary") or c["title"])[:150]
        out = template[:a] + seo_head("post", path, title, desc, data, post=c) + template[b:]
        out = out.replace("<!--DATA-->", guide_js, 1).replace("<!--PRERENDER-->", column_page(c, cols, rows, idx), 1)
        target = OUT / "column" / c["id"] / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out, encoding="utf-8")
    # 월간 거래 리포트
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    report_months = [m for m in months if any(month_key(r) == m for r in rows)]
    for m in report_months:
        path = f"/report/{month_slug(m)}/"
        n = sum(1 for r in rows if month_key(r) == m)
        title = f"{month_label(m)} 서울 빌딩 매매 거래 리포트 | CADENCE"
        desc = (f"{month_label(m)} 서울 빌딩 매매 {n}건: 거래금액, 금액대별·구별 거래, 법인·개인 매수, 금액 상위 거래. "
                "국토교통부 실거래 신고 자료 기준.")
        out = template[:a] + seo_head("monthly", path, title, desc, data) + template[b:]
        out = out.replace("<!--DATA-->", guide_js, 1).replace("<!--PRERENDER-->", monthly_page(m, months, rows, today), 1)
        target = OUT / "report" / month_slug(m) / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out, encoding="utf-8")
    # 주간 딜 시트 지난 주 페이지
    weeks = sorted({week_of(dt.date.fromisoformat(r["seen"])) for r in rows if r.get("seen")}, reverse=True)[:12]
    for w in weeks:
        a_, b_ = week_range(w)
        rs = sheet_rows(rows, a_, b_)
        path = f"/deal-sheet/{w}/"
        title = f"{week_label(w)} 서울 빌딩 딜 시트 | CADENCE"
        desc = f"{week_label(w)} 국토교통부 실거래 자료에 새로 공개된 서울 빌딩 매매 {len(rs)}건을 금액 순으로 정리했습니다."
        out = template[:a] + seo_head("sheetweek", path, title, desc, data) + template[b:]
        out = out.replace("<!--DATA-->", guide_js, 1).replace("<!--PRERENDER-->", deal_sheet(f"{week_label(w)} 서울 빌딩 딜 시트", week_label(w), rs, weeks, w), 1)
        target = OUT / "deal-sheet" / w / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out, encoding="utf-8")
    # RSS (월간 리포트, 주간 딜 시트, 칼럼)
    now = dt.datetime.now(KST)
    feed = []
    for m in report_months:
        y, mo = int(m[:4]), int(m[4:])
        pub = min(dt.datetime(y + (mo == 12), mo % 12 + 1, 1, 9, tzinfo=KST), now)
        n = sum(1 for r in rows if month_key(r) == m)
        feed.append((f"{month_label(m)} 서울 빌딩 매매 거래 리포트", f"/report/{month_slug(m)}/", f"{month_label(m)} 서울 빌딩 매매 {n}건 집계", pub))
    for w in weeks:
        a_, b_ = week_range(w)
        pub = min(dt.datetime(b_.year, b_.month, b_.day, 21, tzinfo=KST), now)
        feed.append((f"{week_label(w)} 서울 빌딩 딜 시트", f"/deal-sheet/{w}/", f"새로 공개된 서울 빌딩 매매 {len(sheet_rows(rows, a_, b_))}건", pub))
    for c in cols:
        try:
            pub = dt.datetime.fromisoformat(c["date"])
        except Exception:
            continue
        feed.append((c["title"], f"/column/{c['id']}/", c.get("summary") or c["title"], pub))
    (OUT / "feed.xml").write_text(rss_feed(feed, now), encoding="utf-8")
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
    urls += "".join(f"<url><loc>{SITE}/deal-sheet/{w}/</loc><lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq></url>" for w in weeks)
    urls += "".join(f"<url><loc>{SITE}/report/{month_slug(m)}/</loc><lastmod>{lastmod}</lastmod><changefreq>{'monthly' if month_settled(m, today) else 'daily'}</changefreq></url>" for m in report_months)
    urls += "".join(f"<url><loc>{SITE}/column/{c['id']}/</loc><lastmod>{(c.get('date') or lastmod)[:10]}</lastmod><changefreq>weekly</changefreq></url>" for c in cols)
    (OUT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")
    (OUT / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY, encoding="utf-8")
    (OUT / "indexnow-urls.txt").write_text("\n".join([SITE + p for _, p, *_ in ROUTES if p not in ("/sell/", "/buy/")]
                                                     + [f"{SITE}/seoul/{v}/" for v in GU_SLUG.values()]
                                                     + [f"{SITE}/column/{c['id']}/" for c in cols]
                                                     + [f"{SITE}/report/{month_slug(m)}/" for m in report_months]
                                                     + [f"{SITE}/deal-sheet/{w}/" for w in weeks]), encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")
    print(f"빌드 완료: {OUT} (페이지 {len(ROUTES)}개 + 구별 {len(GU_SLUG)}개 + 칼럼 {len(cols)}개 + 월간 리포트 {len(report_months)}개 + 404, sitemap.xml, robots.txt)")


if __name__ == "__main__":
    build()
