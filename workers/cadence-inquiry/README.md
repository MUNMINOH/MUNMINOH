# cadence-inquiry (Cloudflare Worker)

CADENCE 사이트의 매도·매수 의뢰서를 받아 노션 데이터베이스 "CADENCE 매도·매수 의뢰"에 한 줄씩 저장합니다.
메일 알림(FormSubmit)은 사이트에서 따로 보내므로, 이 Worker가 멈춰도 메일은 계속 옵니다.

- 주소: `https://api.bldgrunner.com/inquiry` (POST, JSON)
- 허용 출처: `https://cadence.bldgrunner.com`, `https://munminoh.github.io`
- 환경 변수
  - `NOTION_DB`: 노션 데이터베이스 ID (일반 변수)
  - `NOTION_TOKEN`: 노션 통합(Internal integration) 시크릿. Cloudflare 대시보드 → Workers & Pages → cadence-inquiry → Settings → Variables and Secrets에 **Secret**으로 저장합니다. 저장소에는 넣지 않습니다.
- 노션 데이터베이스는 해당 통합에 연결(⋯ → Connections)돼 있어야 합니다.

## 배포 상태

- 스크립트 이름 `cadence-inquiry`, 라우트 `api.bldgrunner.com/*`, DNS `api` (Proxied, 자리 표시용 A 레코드)
- 다시 올릴 때는 Cloudflare API의 Workers 스크립트 업로드(`PUT /accounts/{account}/workers/scripts/cadence-inquiry`)에
  `keep_bindings: ["secret_text"]`를 넣어 `NOTION_TOKEN`이 지워지지 않게 합니다.
- `NOTION_TOKEN`이 없으면 `503 not_configured`를 돌려주고, 사이트는 메일(FormSubmit)만으로 접수를 계속합니다.

## 정기 갱신 (Cron Trigger)

GitHub Actions 예약 실행(`schedule`)은 자주 늦거나 빠집니다. 그래서 이 Worker가 3시간마다(`17 */3 * * *`, UTC)
GitHub API로 '매거진 배포' 워크플로를 실행시킵니다 (`workflow_dispatch`, `source=cron`).

- 필요한 시크릿: `GH_TOKEN`. GitHub fine-grained personal access token이며 조건은 다음과 같습니다.
  - 저장소: MUNMINOH/MUNMINOH만
  - 권한: Actions **Read and write**
  - Cloudflare 대시보드 → Workers & Pages → cadence-inquiry → Settings → Variables and Secrets에 **Secret**으로 저장합니다.
- 토큰이 없거나 만료되면 Worker 로그에 남기고 건너뜁니다. 이때는 GitHub 예약 실행만으로 갱신됩니다.
- 토큰 만료일이 다가오면 GitHub이 메일로 알려 줍니다. 새로 만들어 같은 이름으로 다시 저장하면 됩니다.
