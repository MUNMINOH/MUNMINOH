#!/usr/bin/env python3
"""CADENCE (빌딩러너) 실시간 지표 수집기.

공개 API에서 시장 지표를 받아 magazine/data/live.json 으로 저장합니다.
표준 라이브러리만 사용하므로 별도 설치가 필요 없습니다.

  python magazine/scripts/fetch_live.py

환경 변수 (모두 선택)
  ECOS_API_KEY    한국은행 ECOS 인증키. 없으면 공개 샘플키(sample)로 최근 값만 받습니다.
  DATA_GO_KR_KEY  공공데이터포털 서비스키 (국토교통부 상업업무용 부동산 매매 신고 자료).
                  없으면 서울 빌딩 실거래 수집을 건너뜁니다.
"""
from __future__ import annotations

import datetime as dt
import email.utils
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
OUT = Path(__file__).resolve().parent.parent / "data" / "live.json"
UA = "Mozilla/5.0 (compatible; buildingrunner-bot/1.0)"
PUBLISHED_URL = "https://cadence.bldgrunner.com/data/live.json"

# ---------------------------------------------------------------- 공통
START = time.time()
BUDGET_DEALS = 6 * 60      # 실거래 예전 달 채우기는 시작 후 6분까지만
BUDGET_TOTAL = 11 * 60     # 그 뒤 선택 작업(뉴스 검색 일부, 이미지)은 건너뜀


def elapsed() -> float:
    return time.time() - START


def get(url: str, timeout: int = 15) -> bytes:
    last = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # 네트워크 오류는 두 번 더 시도
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last  # type: ignore[misc]


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------- 한국은행 ECOS
ECOS_KEY = os.environ.get("ECOS_API_KEY") or "sample"
ECOS_SERIES = [
    # id, 표시 이름, 통계표, 주기, 항목코드, 단위
    ("base",  "한국은행 기준금리",   "722Y001", "D", "0101000",   "%"),
    ("ktb3",  "국고채 3년",          "817Y002", "D", "010200000", "%"),
    ("ktb10", "국고채 10년",         "817Y002", "D", "010210000", "%"),
    ("corp",  "회사채 3년 (AA-)",    "817Y002", "D", "010300000", "%"),
    ("cd91",  "CD 91일",             "817Y002", "D", "010502000", "%"),
    ("usd",   "원/달러 환율",        "731Y001", "D", "0000001",   "원"),
    ("loan_corp", "은행 기업대출 금리",    "121Y006", "M", "BECBLA02",   "%"),
    ("loan_sme",  "은행 중소기업대출 금리", "121Y006", "M", "BECBLA0202", "%"),
]


def ecos_rows(stat: str, cycle: str, item: str, start: str, end: str, a: int, b: int):
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}/json/kr/{a}/{b}/"
           f"{stat}/{cycle}/{start}/{end}/{item}")
    d = json.loads(get(url))
    body = d.get("StatisticSearch")
    if not body:
        raise RuntimeError(d.get("RESULT", d))
    return body["list_total_count"], body.get("row", [])


def fetch_ecos(today: dt.date) -> dict:
    out = {}
    for sid, name, stat, cycle, item, unit in ECOS_SERIES:
        if cycle == "M":  # 월별 통계: 최근 2년
            start, end = (today - dt.timedelta(days=730)).strftime("%Y%m"), today.strftime("%Y%m")
        else:
            start, end = (today - dt.timedelta(days=75)).strftime("%Y%m%d"), today.strftime("%Y%m%d")
        try:
            total, _ = ecos_rows(stat, cycle, item, start, end, 1, 1)
            # 샘플키는 한 번에 10행까지만 주므로 끝에서부터 여러 번 나눠 받는다
            rows = []
            hi = total
            while hi > 0 and len(rows) < 40:
                lo = max(1, hi - 9)
                _, part = ecos_rows(stat, cycle, item, start, end, lo, hi)
                rows = part + rows
                hi = lo - 1
            pts = [[r["TIME"], float(r["DATA_VALUE"])] for r in rows if r.get("DATA_VALUE") not in (None, "")]
            if not pts:
                continue
            out[sid] = {
                "name": name, "unit": unit, "source": "한국은행 ECOS",
                "date": pts[-1][0], "value": pts[-1][1],
                "prev": pts[-2][1] if len(pts) > 1 else None,
                "series": pts[-30:],
            }
            log(f"ECOS {name}: {pts[-1]}")
        except Exception as e:
            log(f"ECOS {name} 실패: {e}")
    return out


# ---------------------------------------------------------------- 상장 리츠 (Yahoo Finance)
REITS = [
    ("330590.KS", "롯데리츠", "리테일"),
    ("395400.KS", "SK리츠", "오피스·주유소"),
    ("365550.KS", "ESR켄달스퀘어리츠", "물류"),
    ("293940.KS", "신한알파리츠", "오피스"),
    ("348950.KS", "제이알글로벌리츠", "해외 오피스"),
    ("334890.KS", "이지스밸류플러스리츠", "오피스"),
    ("088260.KS", "이리츠코크렙", "리테일"),
    ("357120.KS", "코람코라이프인프라리츠", "주유소·물류"),
]


def fetch_reits(today: dt.date) -> list:
    out = []
    stale = (today - dt.timedelta(days=14)).strftime("%Y%m%d")
    for sym, name, sector in REITS:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=3mo&interval=1d"
            res = json.loads(get(url))["chart"]["result"][0]
            meta = res["meta"]
            closes = res["indicators"]["quote"][0]["close"]
            ts = res["timestamp"]
            pts = [[dt.datetime.fromtimestamp(t, KST).strftime("%Y%m%d"), round(c, 2)]
                   for t, c in zip(ts, closes) if c is not None]
            price = meta.get("regularMarketPrice") or pts[-1][1]
            prev = pts[-2][1] if len(pts) > 1 else None
            last = dt.datetime.fromtimestamp(meta.get("regularMarketTime", ts[-1]), KST).strftime("%Y%m%d")
            if last < stale:  # 거래정지 등으로 2주 넘게 시세가 없으면 제외
                log(f"REIT {name}: {last} 이후 시세 없음, 제외")
                continue
            out.append({
                "symbol": sym, "name": name, "sector": sector,
                "price": price, "prev": prev,
                "high52": meta.get("fiftyTwoWeekHigh"), "low52": meta.get("fiftyTwoWeekLow"),
                "date": last,
                "series": pts[-60:],
            })
            log(f"REIT {name}: {price}")
        except Exception as e:
            log(f"REIT {name} 실패: {e}")
    return out


# ---------------------------------------------------------------- 국토부 상업업무용 실거래 (서울)
SEOUL_GU = {
    "11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구", "11215": "광진구",
    "11230": "동대문구", "11260": "중랑구", "11290": "성북구", "11305": "강북구", "11320": "도봉구",
    "11350": "노원구", "11380": "은평구", "11410": "서대문구", "11440": "마포구", "11470": "양천구",
    "11500": "강서구", "11530": "구로구", "11545": "금천구", "11560": "영등포구", "11590": "동작구",
    "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구", "11740": "강동구",
}
# 응답 필드명이 영문(신규)과 한글(구버전) 두 가지라 둘 다 받는다
FIELD = {
    "amount": ["dealAmount", "거래금액"], "year": ["dealYear", "년"], "month": ["dealMonth", "월"],
    "day": ["dealDay", "일"], "dong": ["umdNm", "법정동"], "use": ["buildingUse", "건물주용도"],
    "btype": ["buildingType", "유형"], "bar": ["buildingAr", "건물면적"], "par": ["plottageAr", "대지면적"],
    "built": ["buildYear", "건축년도"], "floor": ["floor", "층"], "zone": ["landUse", "용도지역"],
    "buyer": ["buyerGbn", "매수자"], "seller": ["slerGbn", "매도자"], "cancel": ["cdealType", "해제여부"],
}


def pick(item: dict, key: str) -> str:
    for k in FIELD[key]:
        v = item.get(k)
        if v not in (None, ""):
            return v.strip()
    return ""


def num(s: str) -> float:
    try:
        return float(s.replace(",", "").strip())
    except Exception:
        return 0.0


def _fetch_month(key: str, ymd: str):
    """한 달치 서울 25개 구 상업업무용 매매 신고. 실패한 구가 있으면 None."""
    rows, errors = [], 0
    for code, gu in SEOUL_GU.items():
        q = urllib.parse.urlencode({"serviceKey": key, "LAWD_CD": code, "DEAL_YMD": ymd, "numOfRows": 1000, "pageNo": 1}, safe="%")
        url = f"https://apis.data.go.kr/1613000/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade?{q}"
        try:
            root = ET.fromstring(get(url))
            code_el = root.find(".//resultCode")
            if code_el is not None and code_el.text not in ("00", "000"):
                raise RuntimeError(root.findtext(".//resultMsg"))
            for it in root.iter("item"):
                item = {c.tag: (c.text or "") for c in it}
                if pick(item, "cancel") == "O":
                    continue  # 해제된 거래
                if pick(item, "btype") not in ("일반", ""):
                    continue  # 집합(구분상가 호실)은 빼고 건물 단위 거래만
                amount = num(pick(item, "amount"))  # 만 원
                if amount <= 0:
                    continue
                rows.append({
                    "gu": gu, "dong": pick(item, "dong"), "use": pick(item, "use"), "zone": pick(item, "zone"),
                    "buildingArea": num(pick(item, "bar")), "landArea": num(pick(item, "par")),
                    "built": pick(item, "built"), "amount": amount, "buyer": pick(item, "buyer"), "seller": pick(item, "seller"),
                    "date": f"{pick(item, 'year')}.{pick(item, 'month').zfill(2)}.{pick(item, 'day').zfill(2)}",
                })
        except Exception as e:
            errors += 1
            log(f"실거래 {gu} {ymd} 실패: {e}")
        time.sleep(0.12)
    log(f"실거래 {ymd}: 건물 단위 {len(rows)}건 (실패 구 {errors}곳)")
    return rows if errors < 5 else None


def _months_back(today: dt.date, n: int) -> list:
    out, d = [], today.replace(day=1)
    for _ in range(n):
        out.append(d.strftime("%Y%m"))
        d = (d - dt.timedelta(days=1)).replace(day=1)
    return out


def fetch_deals(key: str, today: dt.date, cache: dict) -> dict | None:
    """최근 12개월치를 월별로 쌓는다. 매번 이번 달·지난달은 새로 받고(신고 기한 30일),
    비어 있는 예전 달은 한 번에 2개월씩 채운다 (API 호출량 제한 때문)."""
    want = _months_back(today, 12)
    months = {m: v for m, v in (cache or {}).items() if m in want}
    refresh = want[:2]
    missing = [m for m in want[2:] if m not in months][:2]
    for m in refresh + missing:
        if m in missing and elapsed() > BUDGET_DEALS:
            log(f"실거래 {m}: 시간 제한으로 다음 실행에 채움")
            continue
        rows = _fetch_month(key, m)
        if rows is not None:
            months[m] = rows
    if not months:
        return None
    rows = [r for m in sorted(months, reverse=True) for r in months[m]]
    for r in rows:
        r["perPyeong"] = round(r["amount"] / (r["buildingArea"] / 3.3058)) if r.get("buildingArea") else None
    recent = [r for m in refresh for r in months.get(m, [])]
    recent.sort(key=lambda x: x["amount"], reverse=True)
    by_gu, by_use = {}, {}
    for x in recent:
        for table, k in ((by_gu, x["gu"]), (by_use, x["use"] or "기타")):
            g = table.setdefault(k, {"count": 0, "amount": 0})
            g["count"] += 1
            g["amount"] += x["amount"]
    return {
        "source": "국토교통부 상업업무용 부동산 매매 신고 자료",
        "months": refresh, "count": len(recent), "totalAmount": sum(x["amount"] for x in recent),
        "top": recent[:12], "byGu": by_gu, "byUse": by_use,
        "history": {"months": sorted(months), "rows": rows},
    }, months


# ---------------------------------------------------------------- 뉴스 (제목·출처·링크만 저장)
NEWS_FEEDS = [
    # (이름, 주소, 기본 섹션) — 언론사·기관의 공개 RSS
    ("한국경제", "https://www.hankyung.com/feed/realestate", None),
    ("매일경제", "https://www.mk.co.kr/rss/50300009/", None),
    ("연합뉴스", "https://www.yna.co.kr/rss/economy.xml", None),
    ("조선비즈", "https://biz.chosun.com/arc/outboundfeeds/rss/category/real_estate/?outputType=xml", None),
    ("아시아경제", "https://www.asiae.co.kr/rss/realestate.htm", None),
    ("파이낸셜뉴스", "https://www.fnnews.com/rss/r20/fn_realnews_realestate.xml", None),
    ("머니투데이", "https://rss.mt.co.kr/mt_news.xml", None),
    ("동아일보", "https://rss.donga.com/economy.xml", None),
    ("경향신문", "https://www.khan.co.kr/rss/rssdata/economy_news.xml", None),
    ("한겨레", "https://www.hani.co.kr/rss/economy/", None),
]
NEWS_QUERIES = ["오피스 빌딩 매각", "꼬마빌딩 매매", "물류센터 매각", "상업용 부동산", "리츠 오피스", "오피스 공실률",
                "빌딩 리모델링", "호텔 매각", "상업용 부동산 PF", "데이터센터 부지 매입", "지식산업센터 공실"]

# 상업용 부동산이 분명한 단어
CRE = re.compile(r"빌딩|오피스(?!텔)|상가|상업용|물류센터|물류 센터|리츠|REIT|꼬마빌딩|지식산업센터|호텔 매각|호텔 인수|리테일 부동산|쇼핑몰|업무시설|근린생활|프라임 오피스|CBD|GBD|YBD")
# 사옥은 거래·이전 기사일 때만 (기업 홍보성 '사옥' 기사 제외)
SAOK = re.compile(r"사옥.*(매각|매입|인수|매물|이전|임차|입찰|팔|사들)|(매각|매입|인수|매물|이전|임차|입찰|팔|사들).*사옥")
# 빌딩 오너에게 필요 없는 기사: 해외 기업 자동 번역 기사, 코인, 지방 의회·민원
EXCLUDE_SOURCES = {"Investing.com 한국어", "Investing.com", "Simply Wall St", "데이터투자", "토큰포스트", "코인리더스",
                   "Mezha.net", "블록미디어", "코인데스크코리아"}
EXCLUDE_TITLE = re.compile(r"(시|구|도|군)의원|(시|도|군)의회|행정사무감사|도지사|주민들? 반대|비트코인|BTC|가상자산")
# 데이터센터는 부동산 관점(부지·매각·개발 등)일 때만
DC_RE = r"(부지 (확보|매입|매각)|매각|매입|인수|착공|준공|건립|부동산|펀드|리츠|임차)"
DATACENTER = re.compile(r"데이터센터.*" + DC_RE + r"|" + DC_RE + r".*데이터센터")
# 주택 기사 (상업용 단어가 없으면 뺀다)
HOUSING = re.compile(r"세입자|전세|월세|아파트|집값|주택|청약|신혼부부|빌라|분양|무주택|내집|내 집")


def is_cre(title: str) -> bool:
    if EXCLUDE_TITLE.search(title):
        return False
    if CRE.search(title) or SAOK.search(title) or DATACENTER.search(title):
        return not (HOUSING.search(title) and not re.search(r"빌딩|오피스(?!텔)|상가|물류센터|리츠|지식산업센터|상업용", title))
    return False
SECTIONS = [  # 먼저 맞는 섹션으로 분류
    ("deal", re.compile(r"매각|매입|인수|손바뀜|팔렸|팔아|사들|우선협상|낙찰|매매|거래액|거래 ")),
    ("players", re.compile(r"리츠|REIT|운용사|자산운용|펀드|연기금|공제회|기관투자|상장|증권사")),
    ("building", re.compile(r"리모델링|재개발|재건축|준공|착공|신축|개발|용적률|설계|공사|인허가|용도 변경|용도변경")),
    ("policy", re.compile(r"정책|규제|세금|취득세|양도세|보유세|대출|금리|국토부|국토교통부|기준금리|DSR|PF|법안|개정|시행")),
]


def _text(el, tag):
    t = el.find(tag)
    return (t.text or "").strip() if t is not None and t.text else ""


def _parse_date(s: str) -> str:
    s = (s or "").strip()
    try:  # RSS 표준 형식 (GMT, +0900 등 시간대 포함)
        d = email.utils.parsedate_to_datetime(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(KST).isoformat(timespec="minutes")
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M:%S"):
        try:
            d = dt.datetime.strptime(s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=KST)
            return d.astimezone(KST).isoformat(timespec="minutes")
        except Exception:
            continue
    return ""


def _clean_title(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", html.unescape(t or "")).strip()
    return re.sub(r"\s+", " ", t)


def _section(title: str, default):
    for name, rx in SECTIONS:
        if rx.search(title):
            return name
    return default or "market"


def _items(xml: bytes):
    root = ET.fromstring(xml)
    for it in root.iter("item"):
        src = it.find("source")
        yield {
            "title": _clean_title(_text(it, "title")),
            "link": _text(it, "link"),
            "date": _parse_date(_text(it, "pubDate") or _text(it, "{http://purl.org/dc/elements/1.1/}date")),
            "source": (src.text or "").strip() if src is not None and src.text else "",
        }


def fetch_news(now: dt.datetime, prev: list) -> list:
    found = []
    for name, url, default in NEWS_FEEDS:
        try:
            n = 0
            for x in _items(get(url)):
                if not x["title"] or not x["link"].startswith("http"):
                    continue
                if not is_cre(x["title"]):
                    continue  # 상업용 부동산과 관계없는 기사(아파트 등)는 뺀다
                x["source"] = name
                x["section"] = _section(x["title"], default)
                found.append(x); n += 1
            log(f"뉴스 {name}: {n}건")
        except Exception as e:
            log(f"뉴스 {name} 실패: {e}")
    for q in NEWS_QUERIES:
        if elapsed() > BUDGET_TOTAL:
            log("뉴스 검색: 시간 제한으로 나머지 건너뜀")
            break
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:14d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
        try:
            n = 0
            for x in _items(get(url)):
                if not x["title"] or not is_cre(x["title"]):
                    continue
                # 구글 뉴스 제목은 "제목 - 언론사" 형식
                if x["source"] and x["title"].endswith(" - " + x["source"]):
                    x["title"] = x["title"][: -len(" - " + x["source"])].strip()
                x["source"] = x["source"] or "Google 뉴스"
                x["title"] = re.sub(r"\s+By\s+\S+.*$", "", x["title"]).strip()
                x["section"] = _section(x["title"], None)
                found.append(x); n += 1
            log(f"뉴스 검색 '{q}': {n}건")
        except Exception as e:
            log(f"뉴스 검색 '{q}' 실패: {e}")

    now_iso = now.isoformat(timespec="minutes")
    for x in found:
        if not x.get("date") or x["date"] > now_iso:
            x["date"] = now_iso
    cutoff = (now - dt.timedelta(days=21)).isoformat()
    seen, out, grams = set(), [], []
    for x in sorted(found + (prev or []), key=lambda x: x.get("date") or "", reverse=True):
        key = re.sub(r"[^0-9A-Za-z가-힣]", "", x["title"])[:40]
        if not key or key in seen or (x.get("date") and x["date"] < cutoff):
            continue
        if x.get("source") in EXCLUDE_SOURCES or EXCLUDE_TITLE.search(x["title"]) \
                or not (is_cre(x["title"]) or "상업용 부동산" in (x.get("source") or "")):
            continue  # 지난 데이터에 남아 있던 것도 지금 기준으로 다시 거른다
        g = (_bigrams(x["title"]), _figures(x["title"]))
        dup = next((i for i, h in enumerate(grams) if _similar(g, h)), None)
        if dup is not None:
            # 같은 사건을 여러 언론사가 쓴 기사는 하나만 남긴다.
            # 남긴 기사가 구글 뉴스 링크이고 이 기사가 언론사 원문 링크면 원문으로 바꾼다.
            if _is_gnews(out[dup]["link"]) and not _is_gnews(x["link"]):
                out[dup] = {**x, "section": out[dup].get("section") or x.get("section")}
            continue
        seen.add(key); out.append(x); grams.append(g)
    return out[:120]


def _is_gnews(link: str) -> bool:
    return "news.google.com" in (link or "")


def _bigrams(title: str) -> set:
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", title)          # [단독], (종합) 같은 말머리 제거
    t = re.sub(r"[^0-9A-Za-z가-힣]", "", t)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _figures(title: str) -> set:
    """제목 속 % 숫자 (예: 24%, 5.7%)"""
    return set(re.findall(r"(\d+(?:\.\d+)?)\s*%", title))


def _similar(x: tuple, y: tuple) -> bool:
    (a, fa), (b, fb) = x, y
    if not a or not b:
        return False
    if fa and fb and not (fa & fb):
        return False  # 둘 다 %가 있는데 숫자가 다르면 다른 기사
    inter = len(a & b)
    # 제목 글자쌍이 짧은 쪽 기준 60% 이상 겹치면 같은 기사로 본다
    return inter / min(len(a), len(b)) >= 0.6

# ---------------------------------------------------------------- 빌딩러너 칼럼 (네이버 블로그 글)
NAVER_BLOG_ID = "morrison119"


def _plain(htmltext: str, n: int = 160) -> str:
    t = re.sub(r"<[^>]+>", " ", html.unescape(htmltext or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _blog_og_image(link: str) -> str:
    """글 페이지(모바일)의 대표 이미지(og:image)."""
    m = re.search(r"blog\.naver\.com/([^/]+)/(\d+)", link)
    if not m:
        return ""
    try:
        page = get(f"https://m.blog.naver.com/{m.group(1)}/{m.group(2)}", timeout=15).decode("utf-8", "ignore")
        og = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', page) \
            or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', page)
        return html.unescape(og.group(1)) if og else ""
    except Exception as e:
        log(f"칼럼 이미지 실패 ({link}): {e}")
        return ""


def fetch_blog() -> list:
    out = []
    for url in (f"https://rss.blog.naver.com/{NAVER_BLOG_ID}.xml", f"https://blog.rss.naver.com/{NAVER_BLOG_ID}.xml"):
        try:
            root = ET.fromstring(get(url))
            for it in root.iter("item"):
                title = _clean_title(_text(it, "title"))
                link = _text(it, "link").split("?")[0]
                if not title or not link:
                    continue
                desc = _text(it, "description")
                m = re.search(r'<img[^>]+src=["\']([^"\']+)', html.unescape(desc or ""))
                out.append({"type": "blog", "title": title, "link": link,
                            "date": _parse_date(_text(it, "pubDate")),
                            "summary": _plain(desc), "image": m.group(1) if m else "",
                            "tag": _text(it, "category")})
            for x in out:
                if not x["image"] and elapsed() < BUDGET_TOTAL:
                    x["image"] = _blog_og_image(x["link"])
            log(f"칼럼 블로그: {len(out)}건, 이미지 {sum(1 for x in out if x['image'])}건 ({url})")
            return out
        except Exception as e:
            log(f"칼럼 블로그 실패 ({url}): {e}")
    return out


def fetch_columns(prev: list) -> list:
    items = fetch_blog()
    if not items:
        return prev or []
    items = [x for x in items if x["title"]]
    items.sort(key=lambda x: x.get("date") or "", reverse=True)
    return items[:40]


# ---------------------------------------------------------------- 실행
def main() -> int:
    now = dt.datetime.now(KST)
    prev = {}
    try:  # 배포된 사이트의 최신 데이터 (월별 실거래·뉴스 누적에 씀)
        prev = json.loads(get(PUBLISHED_URL, timeout=15))
        log("지난 데이터: 배포된 사이트에서 읽음")
    except Exception as e:
        log(f"지난 데이터: 배포본을 읽지 못해 저장소 파일 사용 ({e})")
    if not prev and OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            prev = {}

    data = {"updatedAt": now.isoformat(timespec="minutes")}
    # 한 지표만 실패해도 나머지는 새 값으로, 실패한 지표는 지난 값으로 채운다
    data["rates"] = {**prev.get("rates", {}), **fetch_ecos(now.date())}
    # 종목별로 이번에 못 받은 것은 지난 값을 유지 (요청 제한 등)
    got = {x["symbol"]: x for x in fetch_reits(now.date())}
    old = {x["symbol"]: x for x in prev.get("reits", [])}
    stale = (now.date() - dt.timedelta(days=14)).strftime("%Y%m%d")
    data["reits"] = [got.get(sym) or old.get(sym) for sym, _, _ in REITS
                     if (got.get(sym) or old.get(sym)) and (got.get(sym) or old.get(sym)).get("date", "") >= stale]

    key = (os.environ.get("DATA_GO_KR_KEY") or "").strip()
    log("실거래 서비스키: " + ("있음" if key else "없음 (DATA_GO_KR_KEY 비어 있음, 실거래 수집 건너뜀)"))
    cache = {}
    hist = (prev.get("deals") or {}).get("history") or {}
    for r in hist.get("rows", []):
        cache.setdefault(r["date"][:4] + r["date"][5:7], []).append({k: v for k, v in r.items() if k != "perPyeong"})
    for m in hist.get("months", []):
        cache.setdefault(m, [])
    res = fetch_deals(key, now.date(), cache) if key else None
    deals = res[0] if res else prev.get("deals")  # 이번에 실패하면 지난번 값을 유지
    if deals:
        data["deals"] = deals
        h = deals.get("history", {})
        log(f"실거래 누적: {len(h.get('months', []))}개월, {len(h.get('rows', []))}건")

    data["news"] = fetch_news(now, prev.get("news", []))
    by = {}
    for x in data["news"]:
        by[x["section"]] = by.get(x["section"], 0) + 1
    log(f"뉴스 합계 {len(data['news'])}건 {by}")
    log(f"뉴스 원문 링크 {sum(not _is_gnews(x['link']) for x in data['news'])}건 / 구글 뉴스 링크 {sum(_is_gnews(x['link']) for x in data['news'])}건")
    for x in data["news"][:8]:
        log(f"  [{x['section']}] {x['date'][:16]} {x['source']} | {x['title']}")

    data["columns"] = fetch_columns(prev.get("columns", []))
    for x in data["columns"][:5]:
        log(f"  [칼럼 {x['type']}] {(x.get('date') or '')[:10]} | {x['title']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"저장: {OUT} (금리 {len(data['rates'])}개, 리츠 {len(data['reits'])}개, 실거래 {'있음' if deals else '없음'})")
    return 0 if data["rates"] or data["reits"] else 1


if __name__ == "__main__":
    sys.exit(main())
