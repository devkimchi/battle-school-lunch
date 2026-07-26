# AGENTS.md

이 문서는 AI 코딩 에이전트가 이 저장소의 `src` 코드베이스에서 작업할 때
따라야 할 규칙·명령어·주의사항을 정리한 가이드입니다. 사람용 상세 문서는 각
패키지의 `README.md`를 참고하고, 이 문서는 **에이전트 전용 규칙**에 집중합니다.

## 1. 프로젝트 개요

NEIS 오픈 API(학교기본정보 / 급식식단정보) 위에 구축한 풀스택 급식 조회 앱,
OpenAPI 기반 MCP 서버와 Microsoft Agent Framework 비교 분석 서비스 프로젝트.

- 급식은 항상 **중식(lunch, `MMEAL_SC_CODE=2`)** 으로 필터링합니다.
- 프런트엔드 ↔ 백엔드는 `/api/*` 경로로 통신합니다.
  - Aspire 개발: AppHost가 주입한 `API_URL`로 Vite가 `/api`를 프록시.
  - 개별 실행: `API_URL`이 없으면 `http://localhost:8000`으로 프록시.
  - 운영: 프런트엔드와 백엔드가 같은 오리진의 `/api` 아래에서 동작.
- MCP 서버는 `src/openapi.json`을 단일 명세 원본으로 사용하고 `/mcp`에서
  Streamable HTTP 전송을 제공합니다.
- Agent 서비스는 `/agent`에서 AG-UI를 제공하고 MCP로 데이터를 준비한 뒤 세 전문
  에이전트를 Concurrent 실행하고 Judge가 종합합니다.
- 제품 요구사항은 `PRD.md`, 시스템 구조와 구현 결정은 `TRD.md`를 기준으로 합니다.

## 2. 디렉터리 구조

```text
/
├── .github/      이슈/PR 템플릿, CODEOWNERS, Dependabot, CI
├── .devcontainer/ GitHub Codespaces 개발 환경
├── AGENTS.md     AI 코딩 에이전트 작업 지침
├── README.md     프로젝트 실행·테스트·배포 문서
├── PRD.md        제품 요구사항
├── TRD.md        기술 요구사항
├── LICENSE       MIT 라이선스
├── apphost.mts   Aspire TypeScript AppHost (api + mcp + agent + web)
├── aspire.config.json Aspire AppHost 설정
├── compose.yaml  Docker Compose: 네 컨테이너 앱 오케스트레이션
├── .env.example  NEIS·Foundry·포트 환경 변수 템플릿
└── src/
    ├── api/          FastAPI 백엔드 (Python 3.12+ / uv)
    ├── web/          React 19 + Vite + TypeScript + Tailwind v4 프런트엔드
    ├── mcp/          OpenAPI 기반 MCP 서버 (Python 3.12+ / uv)
    ├── agent/        Agent Framework 서비스와 EVALUATION-RUBRIC.md
    ├── e2e/          Playwright 엔드투엔드 테스트 (Chromium)
    └── openapi.json  백엔드·MCP 도구의 단일 NEIS Open API 명세
```

### 백엔드 내부 구조 (`src/api/app/`)

- `main.py` — FastAPI 앱 팩토리, CORS, lifespan, 라우터 등록
- `config.py` — `pydantic-settings` 기반 설정(`NEIS_API_KEY`, `CORS_ORIGINS` 등)
- `neis_client.py` — NEIS Open API용 얇은 `httpx` 비동기 클라이언트
- `schemas.py` — 요청/응답 Pydantic 모델
- `routers/` — `/api/*` 라우트 핸들러 (`health.py`, `schools.py`, `meals.py`)

### 프런트엔드 내부 구조 (`src/web/src/`)

- `pages/` — 조회 페이지와 `MealAnalysisPage`
- `components/ui/` — shadcn 스타일 UI 컴포넌트
- `lib/api.ts` — `/api/*` 호출 래퍼
- `test/` — 테스트 인프라(MSW 핸들러, `renderWithProviders` 헬퍼, 통합 스위트)

### MCP 서버 목표 구조 (`src/mcp/app/`)

- `main.py` — `/mcp` Streamable HTTP 서버 엔트리포인트
- `openapi.py` — `src/openapi.json` 로드 및 MCP 도구 등록
- `neis_client.py` — 인증키 주입, NEIS 비동기 HTTP 호출, 오류 매핑
- 최소 도구 — `getSchoolInfo`, `getMealServiceDietInfo`

### Agent 서비스 구조 (`src/agent/`)

- `app/main.py` — `/agent` AG-UI와 `/health`, MCP·credential lifespan
- `app/data.py` — MCP 학교 후보·두 학교 중식 조회와 preflight
- `app/workflow.py` — 세 전문 에이전트 Concurrent + Judge aggregator
- `app/agui.py` — typed shared state와 AG-UI 단계 이벤트
- `instructions/*.md` — 역할별 외부 지침

## 3. 사전 준비물

| 도구 | 버전 | 사용 위치 |
| --- | --- | --- |
| Python | 3.12+ | `src/api`, `src/mcp`, `src/agent` |
| `uv` | latest | `src/api`, `src/mcp`, `src/agent` |
| Node.js | 22+ (24 LTS 권장) | `src/web`, `src/e2e` |
| npm | 10+ | `src/web`, `src/e2e` |
| Aspire CLI | 13.4+ | 로컬 풀스택 오케스트레이션 |
| Azure CLI | latest | Aspire Azure Container Apps 배포 |
| Docker | 24+ (Compose 플러그인) | Compose / Aspire 이미지 빌드 |
| NEIS API 키 | — | `src/api`, `src/mcp` 런타임 (실데이터 호출용) |

- NEIS 키는 저장소 루트의 `.env`에 `NEIS_API_KEY=...` 형태로 둡니다.
- MCP 도구 인자, 응답, 로그에는 NEIS 키를 포함하지 않습니다.
- **테스트는 NEIS 키가 필요 없습니다** — NEIS / `/api/*`를 경계에서 모킹합니다.

## 4. 명령어 (작업 디렉터리 기준)

### 백엔드 (`src/api/`)

```bash
uv sync                         # 런타임 의존성 설치
uv sync --all-groups            # 개발 의존성(pytest, respx, pytest-cov)까지 설치
uv run uvicorn app.main:app --reload --port 8000   # 개발 서버
uv run pytest                   # 전체 테스트
uv run pytest -m unit           # 단위 테스트만
uv run pytest -m integration    # 통합 테스트만
uv run pytest --cov=app         # 커버리지와 함께
```

### 프런트엔드 (`src/web/`)

```bash
npm install
npm run dev                     # Vite 개발 서버 (http://localhost:5173)
npm run build                   # tsc -b && vite build → dist/
npm run preview                 # 빌드 산출물 미리보기 (http://localhost:4173)
npm run lint                    # ESLint
npm test                        # Vitest 1회 실행
npm run test:watch              # Vitest watch
npm run test:coverage           # 커버리지 리포트
```

### MCP 서버 (`src/mcp/`)

```bash
uv sync --all-groups
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
uv run pytest
```

실행 명령과 `/mcp` 연결 예시는 `src/mcp/README.md`를 따릅니다.

### Agent 서비스 (`src/agent/`)

```bash
uv sync --all-groups
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
uv run pytest
```

실행 전 `az login`, `FOUNDRY_PROJECT_ENDPOINT`,
`FOUNDRY_MODEL_DEPLOYMENT_NAME`, 실행 중인 MCP 서버가 필요합니다.

### E2E (`src/e2e/`)

```bash
npm install
npm test                        # playwright test (pretest에서 ../web 빌드 수행)
npm run test:headed             # 브라우저 표시
npm run test:ui                 # Playwright UI 모드
npm run report                  # 마지막 리포트 보기
```

### 풀스택 / 배포 (저장소 루트)

```bash
npm install                     # TypeScript AppHost 의존성
npm run dev                     # Aspire로 api + mcp + agent + web 실행
aspire stop                     # Aspire AppHost와 리소스 중지

docker compose up -d --build    # 네 서비스 기동 (mcp, agent는 localhost 전용)
docker compose down             # 중지 및 제거

az login
aspire publish --list-steps --non-interactive
aspire deploy --list-steps --non-interactive
Azure__SubscriptionId=<id> Azure__Location=<region> Azure__ResourceGroup=<group> \
  aspire deploy --environment production --non-interactive
aspire destroy --environment production
```

배포 전 `Parameters__neis_api_key`는 CI secret 또는 현재 프로세스 환경으로 별도
주입합니다. 실제 값을 문서, 명령 기록, 로그에 넣지 마세요.

## 5. 코딩 규칙 및 패턴

- **백엔드**: 앱 팩토리 패턴(`main.py`), 설정은 `pydantic-settings`로만 주입,
  외부 호출은 `neis_client.py`의 `httpx` 비동기 클라이언트를 통해서만 수행.
  새 엔드포인트는 `routers/` 아래에 추가하고 `main.py`에 등록.
- **타입/스키마**: 요청·응답 모델은 `schemas.py`의 Pydantic 모델로 정의.
- **프런트엔드**: 모든 백엔드 호출은 `lib/api.ts` 래퍼를 거칩니다. 컴포넌트에서
  `fetch`를 직접 호출하지 마세요. 서버 상태는 `@tanstack/react-query`로 관리.
- **Aspire**: `apphost.mts`만 직접 편집하고 생성물인 `.aspire/modules/`는 수정하지
  마세요. `web`은 `api`를 참조하고 준비 상태를 기다리며, API URL은
  `withEnvironment("API_URL", api.getEndpoint("http"))`로 주입합니다.
  `NEIS_API_KEY`는 secret parameter로 모델링해 `api`와 `mcp` 환경 변수로 전달합니다.
  Azure 배포에서는 `aca` Container Apps environment와 기존 nginx Dockerfile을
  사용하는 `publishAsDockerFile(...)` 생산 모델을 유지합니다. nginx의 target
  port는 8080이고 `API_UPSTREAM`에는 internal `api` endpoint를 주입합니다.
  `web`만 external endpoint이고 `api`, `mcp`, `agent`는 internal입니다.
- **MCP 서버**: `src/openapi.json`의 `operationId`, 설명, 파라미터와 필수 여부를
  도구 스키마에 반영합니다. 동일한 스키마를 코드에 중복 정의하지 마세요.
  `NEIS_API_KEY`는 환경 변수로만 주입하고, NEIS 오류는 코드와 메시지가 포함된
  MCP 도구 오류로 전달합니다. 전송 방식은 `/mcp` 기반 Streamable HTTP입니다.
- **Agent 서비스**: 사람용 평가 기준은 `src/agent/EVALUATION-RUBRIC.md`, 역할 지침은
  `src/agent/instructions/*.md`에서 관리합니다. 전문 에이전트 점수는 1~5 정수이며
  45/30/25 환산과 총점은 코드가 계산합니다. Judge는 점수를 변경하지 않습니다.
  MCP와 Foundry는 반드시 경계에서 모킹하고 자격 증명을 web으로 전달하지 마세요.
- **급식 조회 제약**: 날짜 범위는 **최대 31일**.

## 6. 테스트 원칙

| 계층 | 위치 | 도구 | 모킹 경계 |
| --- | --- | --- | --- |
| 단위/통합 (API) | `src/api/tests/` | pytest + respx | NEIS HTTP 경계 |
| 단위/통합 (Web) | `src/web/src/**/*.test.*`, `src/web/src/test/integration/` | Vitest + RTL + MSW | `/api/*` |
| 단위/통합 (MCP) | `src/mcp/tests/` | pytest + respx | NEIS HTTP 경계 |
| 단위/통합 (Agent) | `src/agent/tests/` | pytest | MCP·Foundry 경계 |
| 엔드투엔드 | `src/e2e/tests/` | Playwright | `/api/*`, `/agent` (`page.route`) |

- **어떤 테스트도 실제 NEIS나 Foundry 서비스에 접근하지 않습니다.** 항상 경계에서 모킹.
- 백엔드 마커: `unit`(순수 함수, I/O 없음), `integration`(`TestClient` + respx).
  `--strict-markers`가 켜져 있으므로 새 마커는 `pyproject.toml`에 먼저 등록.
- 프런트엔드: 프레젠테이션 컴포넌트(`Button` 등)와 한 줄짜리 유틸(`cn`)에는
  **의도적으로 단위 테스트를 두지 않습니다**. 실제 로직(state machine, 폼
  유효성 검사, 복잡한 키보드 핸들러 등)이 있을 때만 컴포넌트 단위 테스트를
  추가하세요. 불필요한 테스트를 양산하지 마세요.

## 7. Git 커밋 및 PR 규칙

- Git 작업을 시작하기 전에 항상 `git branch --show-current` 명령으로 현재 브랜치를
  확인합니다.
- 계획에 포함된 각 작업을 완료할 때마다 해당 작업의 변경 사항을 별도 커밋으로
  만듭니다. 서로 다른 계획 작업의 변경 사항을 하나의 커밋에 섞지 마세요.
- 모든 계획 작업과 검증을 마친 후 현재 브랜치에서 `main` 브랜치로 Pull Request를
  생성합니다.
- 만약 커밋하지 않은 변경사항이 있을 경우 해당 변경사항을 커밋할 것인지 물어보세요.
- PR 본문은 `.github/PULL_REQUEST_TEMPLATE.md`의 구조와 항목을 그대로 따릅니다.
- PR의 변경 요약은 현재 브랜치와 `main` 사이의 커밋 기록을 확인해 작성하며,
  각 커밋에서 완료한 주요 변경 사항을 빠짐없이 포함합니다.

## 8. 주의사항 / 가드레일

- **시크릿**: `.env`는 절대 커밋하지 않습니다. 키는 로컬 `.env` 또는 배포
  프로세스의 `Parameters__neis_api_key` 환경 변수로만 주입합니다.
- **의존성**: 백엔드, MCP, Agent 서버는 각 패키지 디렉터리에서 `uv add`로 추가해
  `uv.lock`을 갱신하고, 프런트엔드는 `npm`으로 추가해 `package-lock.json`을
  갱신합니다. 락 파일을 수동 편집하지 마세요.
- **Azure 배포 원본**: `apphost.mts`가 Azure 토폴로지의 단일 원본입니다.
- **컨테이너 보안 강화 유지**: `compose.yaml`과 각 Dockerfile은 non-root, `cap_drop: ALL`,
  `no-new-privileges`, read-only 루트 파일시스템을 사용합니다. 디버깅 편의를 위해
  이 설정을 약화시키지 마세요.
- **운영 nginx 프록시**: Web→API/Agent는 nginx에서 `proxy_set_header Host $proxy_host`와
  `proxy_ssl_server_name on`으로 HTTPS 업스트림에 연결됩니다. 이 설정을 변경할 때
  TLS SNI / 호스트 라우팅이 깨지지 않도록 주의하세요.
- **CORS**: 허용 오리진은 `src/api/app/config.py`의 `CORS_ORIGINS`로 제어합니다.
  Azure에서는 public `web`의 nginx가 같은 오리진 `/api`와 `/agent`를 internal
  서비스로 프록시하므로 브라우저에 내부 origin을 별도로 노출하지 않습니다.
