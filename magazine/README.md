# CADENCE 케이던스

빌딩러너가 만드는 상업용 부동산 리뷰.

빌딩·상업용 부동산 매거진 사이트입니다. 페이지는 `index.html` 파일 하나이고, 실시간 지표는 `data/live.json`에서 읽습니다.

## 콘텐츠 원칙

사이트에는 지어낸 기사나 수치를 싣지 않습니다. 모든 내용은 아래 출처에서 자동으로 모읍니다.

| 내용 | 출처 | 비고 |
|---|---|---|
| 뉴스 | 한국경제·매일경제·연합뉴스·조선비즈·아시아경제 부동산 RSS, Google 뉴스 검색 | 제목·출처·날짜·원문 링크만 저장. 본문은 옮기지 않음 |
| 금리·환율 | 한국은행 ECOS | 기준금리, 국고채 3년·10년, 회사채 AA- 3년, CD 91일, 원/달러 |
| 상장 리츠 시세 | Yahoo Finance (지연 시세) | 2주 넘게 시세가 없는 종목은 제외 |
| 서울 빌딩 실거래 | 국토교통부 상업업무용 부동산 매매 신고 자료 | `DATA_GO_KR_KEY` 필요. 최근 12개월을 월별로 쌓아 실거래 검색·구별 시세·월별 추이·금액대 분포에 씀. 커버 기사도 이 자료로 자동 작성 |
| 건물주 가이드 | 지방세법, 공인중개사법 시행규칙, 부가가치세법, 상가건물 임대차보호법(시행령), 종합부동산세법, 은행권 RTI 가이드라인 | 확인일과 근거 법령 링크를 함께 표시. 세율이 바뀌면 `FACTS`와 계산기 숫자를 고칩니다 |

`scripts/fetch_live.py`가 위 자료를 받아 `data/live.json`으로 저장합니다. 배포 워크플로가 3시간마다 실행합니다.

- 뉴스는 상업용 부동산 단어(빌딩, 오피스, 상가, 물류센터, 리츠 등)가 제목에 있는 것만 남기고, 아파트·전월세 같은 주택 기사는 뺍니다.
- 뉴스 섹션(마켓, 클로징, 빌딩, 정책·금융, 페이스메이커)은 제목의 단어로 자동 분류합니다.
- 최근 3주, 최대 120건을 보관합니다.

## 화면

| 화면 | 주소 | 내용 |
|---|---|---|
| 홈 | `#home` | 이번 달 서울 최대 빌딩 거래, 금리·환율, 최신 뉴스, 서울 빌딩 거래, 구·용도별 거래, 상장 리츠 |
| 섹션 | `#market` `#deal` `#building` `#players` | 섹션별 뉴스. 클로징에는 실거래 검색, 페이스메이커에는 리츠 시세 |
| 건물주 가이드 | `#policy` | 자주 묻는 기준(근거 법령), 매입 비용·수익률(RTI)·임대차 보호 범위 계산기, 구별 시세, 정책 뉴스 |
| 랩타임 | `#data` | 금리·환율, 리츠, 구별 시세, 월별 거래, 금액대 분포, 실거래 검색 |
| 의뢰 | `#inquiry` `#sell` `#buy` | 매도·매수 의뢰서 (FormSubmit으로 메일 전달) |

## 주소와 검색엔진 최적화(SEO)

배포할 때 `scripts/build_site.py`가 `index.html`을 바탕으로 페이지별 실제 주소를 만듭니다.

| 주소 | 화면 |
|---|---|
| `/` | 홈: 오늘의 숫자, 이번 달 큰 거래, 최신 뉴스, 권역별 평당가, 칼럼, 기관별 시장 지표, 계산기 |
| `/price/` | 1F 시세: 권역·구·동별, 연식·용도별 평당가, 월별 거래, 금액대 분포 |
| `/seoul/{구}/` | 25개 구별 빌딩 시세·실거래가 페이지 (예: `/seoul/gangnam/`) |
| `/deal/` | 2F 실거래: 실거래 검색, 큰 거래, 매매 뉴스 |
| `/report/` | 3F 시장 리포트: 기관별 분기 지표, 금리·은행 대출 금리, 리츠 |
| `/guide/` | 4F 건물주 가이드: 기준 정리와 계산기 |
| `/news/` | 5F 뉴스: 주제 탭 (시장·임대, 매매·투자, 개발, 정책·세금·금융, 리츠·운용사) |
| `/column/` | 6F 빌딩러너 칼럼 |
| `/inquiry/` `/sell/` `/buy/` | 매도·매수 의뢰 |

예전 주소(`/market/` `/building/` `/players/` `/data/`, `#deal` 같은 주소)는 새 주소로 넘깁니다.

### 분기 시장 지표 고치기

`content/market.json`에 기관별 분기 지표와 출처 기사 링크가 있습니다. 새 분기 발표가 나오면 수치와 링크를 바꿉니다.

### 검색엔진 등록

구글 서치 콘솔과 네이버 서치어드바이저에서 사이트를 등록하고 받은 확인 코드를 `scripts/build_site.py`의 `SITE_VERIFICATION`에 넣은 뒤, `https://cadence.bldgrunner.com/sitemap.xml`을 제출합니다.

- 페이지마다 제목, 설명, 대표 주소(canonical), 공유 이미지(`assets/og-image.png`), 구조화 데이터(JSON-LD)를 넣습니다.
- 자바스크립트를 실행하지 않는 검색엔진도 읽을 수 있게 뉴스·실거래·평당가·칼럼 목록을 HTML 본문에 미리 넣습니다.
- `sitemap.xml`, `robots.txt`, `404.html`을 함께 만듭니다.
- 예전 `#deal` 같은 주소로 들어오면 새 주소로 넘깁니다.
- 건물주 가이드의 기준은 `content/guide.json` 한 곳에서 고칩니다.

## 자동 갱신 중지 알림

GitHub은 저장소에 60일 동안 커밋이 없으면 예약 실행을 멈춥니다. 배포 워크플로가 마지막 커밋 후 45일이 지나면 저장소에 알림 이슈를 엽니다 (GitHub 알림과 메일로 옵니다). 아무 변경이나 커밋하면 다시 60일이 시작됩니다.

## 칼럼

7F 칼럼은 빌딩러너 네이버 블로그(morrison119) RSS에서 글과 대표 이미지를 자동으로 모읍니다.

## 캐릭터 넣기

빌딩러너 캐릭터 이미지를 `magazine/assets/character.png`로 넣고, `index.html`의 `CHARACTER_IMAGE`를 `"assets/character.png"`로 바꾸면 상단 로고 왼쪽에 나타납니다. 배경이 투명한 PNG, 가로 400px 안팎을 권장합니다. 파일이 없으면 글자 로고만 보입니다.

## 공개하기 (GitHub Pages + cadence.bldgrunner.com)

주소 구조: 빌딩러너 본 도메인 `bldgrunner.com` 아래에 매거진을 `cadence.bldgrunner.com`으로 둡니다. 본 사이트가 생기기 전까지 `bldgrunner.com`은 CADENCE로 넘깁니다.

사이트는 `.github/workflows/magazine-pages.yml`이 GitHub Pages로 배포합니다. 기본 브랜치에 `magazine/`이 바뀌어 올라오면 배포하고, 평일 09:10·18:10(KST)마다 지표를 새로 받아 다시 배포합니다.

### 도메인 연결 (Cloudflare 기준, 처음 한 번)

1. Cloudflare에서 `bldgrunner.com`을 구입합니다. 자동 갱신은 켜 둡니다.
2. **매거진 주소**: DNS → Records → Add record
   - Type `CNAME`, Name `cadence`, Target `munminoh.github.io`, Proxy status **DNS only**(회색 구름)
3. GitHub 저장소 Settings → Pages → Custom domain에 `cadence.bldgrunner.com`을 입력하고 Save. 인증서가 나오면 **Enforce HTTPS**를 켭니다.
4. **본 도메인 넘기기** (본 사이트가 생기기 전까지)
   - DNS에 Type `A`, Name `@`, IPv4 `192.0.2.1`, Proxy status **Proxied**(주황 구름)를 추가합니다. 실제 서버가 없는 자리 표시용 주소이고, 아래 규칙이 요청을 넘깁니다.
   - 같은 방식으로 Name `www`도 추가합니다.
   - Rules → Redirect Rules → Create rule: 조건 **All incoming requests**, URL redirect **Static**, URL `https://cadence.bldgrunner.com`, 상태 코드 `302`(나중에 본 사이트를 열 수 있게 임시 이동), Preserve query string 체크.
5. (선택) 한글 보조 도메인 `빌딩러너.com`을 샀다면 4번과 같은 방법으로 넘깁니다.

### 실거래 서비스키

Settings → Secrets and variables → Actions → **Repository secrets**에 `DATA_GO_KR_KEY`로 저장합니다. 배포 로그에 "실거래 서비스키: 있음"이 나오면 연결된 것입니다.
