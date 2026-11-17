# 빌딩러너 매거진

빌딩·상업용 부동산 매거진 사이트입니다. 페이지는 `index.html` 파일 하나이고, 실시간 지표는 `data/live.json`에서 읽습니다.

## 실시간 지표

`scripts/fetch_live.py`가 공개 API에서 지표를 받아 `data/live.json`으로 저장합니다 (파이썬 표준 라이브러리만 사용).

```
python magazine/scripts/fetch_live.py
```

| 지표 | 출처 | 키 |
|---|---|---|
| 기준금리, 국고채 3년·10년, 회사채 3년(AA-), CD 91일, 원/달러 | 한국은행 ECOS | 없어도 됨 (`ECOS_API_KEY` 있으면 사용) |
| 상장 리츠 7종 시세 | Yahoo Finance (지연 시세, 비공식 API) | 없음 |
| 서울 25개 구 빌딩 실거래 | 국토교통부 상업업무용 부동산 매매 신고 자료 | `DATA_GO_KR_KEY` 필요 |

- 실거래 서비스키는 공공데이터포털(data.go.kr)에서 "국토교통부_상업업무용 부동산 매매 신고 자료"를 활용 신청하면 무료로 받을 수 있습니다. 키가 없으면 거래 표는 '예시'로 표시됩니다.
- 실거래 응답은 서비스키로 아직 실제 확인하지 못했습니다. 키를 넣고 처음 돌릴 때 결과를 한 번 확인하세요.
- 한 API가 실패해도 나머지는 저장하고, 실패한 항목은 지난번 값을 유지합니다.

브라우저는 보안상 `file://`로 연 페이지에서 `data/live.json`을 읽지 못합니다. 로컬에서 볼 때는 간단한 서버로 여세요.

```
cd magazine && python -m http.server 8000   # http://localhost:8000
```

## 화면

| 화면 | 주소 | 내용 |
|---|---|---|
| 출발선(홈) | `#home` | 메인 레이스(커버), 오늘의 랩타임(금리·환율), 새로 들어온 기록, 결승선을 통과한 서울 빌딩, 리츠 레이스, 페이스메이커, 워밍업 |
| 구간(카테고리) | `#market` 페이스 체크 · `#deal` 결승선 · `#building` 코스 탐방 · `#invest` 워밍업 · `#people` 페이스메이커 · `#data` 랩타임 | 1F~6F 구간별 기사. 결승선·랩타임 구간에는 실시간 표도 함께 표시 |
| 기사 | `#a1` ~ `#a12` | 본문, 목차, 글자 크기 조절, 읽기 진행 막대, 스펙 시트 |

## 기사 고치기

`index.html`의 `<script>` 안 데이터만 바꾸면 됩니다.

- `ARTICLES`: 기사. 스펙 시트 값을 `"@ktb3"`처럼 쓰면 실시간 지표로 채워집니다 (`base` `ktb3` `ktb10` `corp` `cd91` `usd` `spread`).
- `SAMPLE_DEALS`: 실거래 키가 없을 때 보여 줄 예시 거래
- `VACANCY`, `MIX`: 공실률·섹터 거래액 예시 차트

> 기사, 인물, 건물명, '예시'로 표시된 수치는 화면 구성을 보여 주기 위한 가상의 콘텐츠입니다.

## 캐릭터 넣기

빌딩러너 캐릭터 이미지를 `magazine/assets/character.png`로 넣으면 상단 로고 왼쪽에 자동으로 나타납니다. 배경이 투명한 PNG, 가로 400px 안팎을 권장합니다. 파일이 없으면 글자 로고만 보입니다.

## 공개하기 (GitHub Pages + 내 도메인)

1. 이 브랜치를 저장소 기본 브랜치에 병합합니다. 병합하면 `.github/workflows/magazine-pages.yml`이 사이트를 배포하고, 평일 09:10·18:10(KST)마다 지표를 새로 받아 다시 배포합니다.
2. 저장소 Settings → Pages → Build and deployment → Source를 **GitHub Actions**로 바꿉니다.
3. 같은 화면의 Custom domain에 도메인을 입력합니다 (예: `www.buildingrunner.com`).
4. 도메인 업체의 DNS 설정에 아래 레코드를 추가합니다.
   - `www` → CNAME → `<GitHub 사용자명>.github.io`
   - 루트 도메인(@) → A 레코드 4개: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
5. DNS가 퍼지면(보통 몇 분~몇 시간) Settings → Pages에서 **Enforce HTTPS**를 켭니다.
6. 실거래 표를 실제 데이터로 바꾸려면 Settings → Secrets and variables → Actions에 `DATA_GO_KR_KEY`를 추가합니다.
