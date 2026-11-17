#!/usr/bin/env python3
"""빌딩러너 매거진 실시간 지표 수집기.

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
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
OUT = Path(__file__).resolve().parent.parent / "data" / "live.json"
UA = "Mozilla/5.0 (compatible; buildingrunner-bot/1.0)"

# ---------------------------------------------------------------- 공통
def get(url: str, timeout: int = 20) -> bytes:
    last = None
    for attempt in range(3):
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
    start = (today - dt.timedelta(days=75)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    for sid, name, stat, cycle, item, unit in ECOS_SERIES:
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


def fetch_deals(key: str, today: dt.date) -> dict | None:
    months = []
    d = today.replace(day=1)
    for _ in range(2):  # 이번 달 + 지난달 (신고 기한 30일)
        months.append(d.strftime("%Y%m"))
        d = (d - dt.timedelta(days=1)).replace(day=1)
    deals, errors = [], 0
    for ymd in months:
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
                        continue
                    amount = num(pick(item, "amount"))  # 만원
                    bar = num(pick(item, "bar"))
                    if amount <= 0:
                        continue
                    deals.append({
                        "gu": gu, "dong": pick(item, "dong"), "use": pick(item, "use"), "type": pick(item, "btype"),
                        "zone": pick(item, "zone"), "buildingArea": bar, "landArea": num(pick(item, "par")),
                        "built": pick(item, "built"), "floor": pick(item, "floor"),
                        "amount": amount, "buyer": pick(item, "buyer"),
                        "date": f"{pick(item, 'year')}.{pick(item, 'month').zfill(2)}.{pick(item, 'day').zfill(2)}",
                        "perPyeong": round(amount / (bar / 3.3058)) if bar > 0 else None,
                    })
            except Exception as e:
                errors += 1
                log(f"실거래 {gu} {ymd} 실패: {e}")
            time.sleep(0.15)
    if not deals and errors:
        return None
    buildings = [x for x in deals if x["type"] in ("일반", "")]  # 집합(구분상가)이 아닌 건물 단위 거래
    buildings.sort(key=lambda x: x["amount"], reverse=True)
    by_gu = {}
    for x in buildings:
        g = by_gu.setdefault(x["gu"], {"count": 0, "amount": 0})
        g["count"] += 1
        g["amount"] += x["amount"]
    return {
        "source": "국토교통부 상업업무용 부동산 매매 신고 자료",
        "months": months, "count": len(buildings), "totalAmount": sum(x["amount"] for x in buildings),
        "top": buildings[:12], "byGu": by_gu,
    }


# ---------------------------------------------------------------- 실행
def main() -> int:
    now = dt.datetime.now(KST)
    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            prev = {}

    data = {"updatedAt": now.isoformat(timespec="minutes")}
    data["rates"] = fetch_ecos(now.date()) or prev.get("rates", {})
    data["reits"] = fetch_reits(now.date()) or prev.get("reits", [])

    key = os.environ.get("DATA_GO_KR_KEY")
    deals = fetch_deals(key, now.date()) if key else None
    if deals is None and prev.get("deals"):
        deals = prev["deals"]  # 이번에 실패하면 지난번 값을 유지
    if deals:
        data["deals"] = deals

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"저장: {OUT} (금리 {len(data['rates'])}개, 리츠 {len(data['reits'])}개, 실거래 {'있음' if deals else '없음'})")
    return 0 if data["rates"] or data["reits"] else 1


if __name__ == "__main__":
    sys.exit(main())
