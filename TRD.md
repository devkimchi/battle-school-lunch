# TRD — 급식 정보 조회 및 분석 웹 앱

> [PRD](./PRD.md)의 제품 요구사항을 구현하기 위한 기술 요구사항 문서. NEIS API 계약은 [`src/openapi.json`](./src/openapi.json)을 단일 명세 원본으로 사용한다.

---

## 1. 시스템 구성 (System Architecture)

```text
Web browser
    ├─ /api/*
    │
    └─ /agent (AG-UI POST + SSE)
    ▼
Frontend (React/Vite → nginx or YARP)
    ├─ /api/*  → Backend (FastAPI) → NEIS Open API
    └─ /agent  → Agent (FastAPI + Microsoft Agent Framework)
                    ├─ DefaultAzureCredential → Microsoft Foundry model
                    └─ MCP Streamable HTTP /mcp
                           ▼
                       MCP server → NEIS Open API

MCP client
    │ Streamable HTTP /mcp
    ▼
MCP server
    │ OpenAPI 기반 도구 + HTTPS + NEIS_API_KEY
    ▼
NEIS Open API
```

- 프론트엔드는 NEIS를 직접 호출하지 않고 백엔드의 `/api/*`만 사용한다.
- 급식 분석은 같은 오리진 `/agent`에서 AG-UI 프로토콜로 상태와 결과를 스트리밍한다.
- agent는 MCP 서버로 학교·중식을 직접 조회하고 세 전문 에이전트를 Concurrent 실행한 뒤 Judge로 fan-in한다.
- MCP 서버는 `src/openapi.json`에서 도구 스키마를 구성하고 NEIS를 직접 호출한다.
- 백엔드와 MCP 서버는 `NEIS_API_KEY`를 서버 환경 변수로만 주입받는다.
- 로컬에서는 TypeScript Aspire AppHost가 `api`, `mcp`, `agent`, `web`을 오케스트레이션한다.
- Azure에서는 AppHost가 하나의 Container Apps Environment에 internal `api`, `mcp`,
  `agent`와 public `web`을 배포하며, nginx가 `/api`와 `/agent`를 내부 서비스로 프록시한다.
- Azure 배포 토폴로지의 단일 원본은 `apphost.mts`이며 `aspire deploy`로 적용한다.

---

## 2. Backend (`src/api`)

### 2.1 기술 스택

| 구분 | 선정 |
| --- | --- |
| 언어 | Python 3.12+ |
| 패키지/가상환경 | **uv** (`pyproject.toml`, `uv.lock`) |
| 웹 프레임워크 | **FastAPI** |
| ASGI 서버 | **Uvicorn** |
| HTTP 클라이언트 | **httpx** (async) |
| 설정 로딩 | **pydantic-settings**, `python-dotenv` |
| 응답 검증 | **Pydantic v2** |

### 2.2 디렉터리 구조

```text
src/api/
├── .dockerignore
├── Dockerfile
├── pyproject.toml
├── uv.lock
├── README.md
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI 인스턴스, CORS, 라우터 등록, lifespan
│   ├── config.py        # NEIS_API_KEY 등 Settings
│   ├── neis_client.py   # NEIS httpx async 래퍼 + RESULT.CODE 처리
│   ├── schemas.py       # Pydantic 응답 모델 (School, Meal)
│   └── routers/
│       ├── __init__.py
│       ├── health.py    # GET /api/health
│       ├── schools.py   # GET /api/schools?name=
│       └── meals.py     # GET /api/meals?eduOfficeCode&schoolCode&from&to
└── tests/
    ├── conftest.py
    ├── unit/            # 설정, 스키마, NEIS 클라이언트, 라우터 헬퍼
    └── integration/     # health, schools, meals API
```

### 2.3 API 엔드포인트

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/health` | Liveness probe |
| GET | `/api/schools?name={partial}` | 학교명 부분 검색 |
| GET | `/api/meals?eduOfficeCode=&schoolCode=&from=YYYY-MM-DD&to=YYYY-MM-DD` | 중식 식단 조회 |

---

## 3. Frontend (`src/web`)

### 3.1 기술 스택

| 구분 | 선정 |
| --- | --- |
| 빌드 도구 | **Vite 8** |
| 프레임워크 | **React 19** + **TypeScript** |
| 라우팅 | **react-router-dom v7** |
| 데이터 페칭 | **@tanstack/react-query v5** |
| 스타일 | **Tailwind CSS v4** (`@tailwindcss/vite`) + `tw-animate-css` |
| UI 컴포넌트 | **shadcn 스타일** 수기 작성 (Button, Input, Card, Calendar) |
| 날짜 위젯 | **react-day-picker v10** (Calendar 래퍼) |
| 날짜 유틸 | **date-fns v4** |
| 클래스 합성 | `clsx` + `tailwind-merge` (`cn` 헬퍼) |
| 아이콘 | `lucide-react` |
| Agent 프로토콜 | `@ag-ui/client` (`HttpAgent`) |

### 3.2 디렉터리 구조

```text
src/web/
├── .dockerignore
├── Dockerfile
├── eslint.config.js
├── index.html
├── package.json
├── package-lock.json
├── vite.config.ts        # @tailwindcss/vite, alias '@', proxy /api + /agent
├── vitest.config.ts
├── tsconfig*.json        # paths: { "@/*": ["./src/*"] }
├── README.md
├── nginx/
│   ├── nginx.conf
│   └── default.conf.template
├── public/
│   └── vite.svg
└── src/
    ├── main.tsx          # QueryClientProvider + BrowserRouter
    ├── App.tsx           # sticky 상단 탭 + Routes
    ├── index.css         # @import "tailwindcss" + 테마 토큰
    ├── types.ts          # School, Meal
    ├── vite-env.d.ts
    ├── lib/
    │   ├── api.ts        # fetch 래퍼 (searchSchools, getMeals)
    │   ├── api.test.ts
    │   ├── analysis-agent.ts       # AG-UI HttpAgent 래퍼
    │   ├── analysis-agent.test.ts
    │   ├── analysis-types.ts       # shared state/result 타입
    │   └── utils.ts      # cn()
    ├── components/ui/    # button, input, card, calendar
    ├── pages/
    │   ├── LandingPage.tsx
    │   ├── DateRangePage.tsx
    │   ├── MealsResultPage.tsx
    │   └── MealAnalysisPage.tsx
    └── test/
        ├── setup.ts
        ├── test-utils.tsx
        ├── msw/          # /api/* mock handlers and server
        └── integration/  # search, meals, analysis chat flows
```

### 3.3 클라이언트 라우트

| Path | Page |
| --- | --- |
| `/` | LandingPage (학교 검색) |
| `/school/:schoolCode` | DateRangePage (날짜 범위 선택) |
| `/school/:schoolCode/meals` | MealsResultPage (날짜별 중식 카드) |
| `/analysis` | MealAnalysisPage (학교 선택·멀티에이전트 비교 보고서) |

`App.tsx`의 공통 셸은 모든 경로 상단에 `학교 급식 조회`와 `학교 급식 분석`
링크를 표시한다. 현재 경로는 `aria-current="page"`로 식별하며, 내비게이션은
`position: sticky`, `top: 0`으로 스크롤 중에도 화면 상단에 유지한다.

### 3.4 멀티에이전트 분석 UI

- `HttpAgent` 인스턴스는 thread ID, 메시지와 typed shared state를 유지한다.
- 페이지 진입 시 `load_candidates` action을 보내고 학교 후보 10곳을 렌더링한다.
- 두 학교와 허용 날짜가 선택되면 프롬프트를 자동 작성하지만 전송은 사용자가 수행한다.
- `loading_meals`, `evaluating`, `judging`, `completed`, `error` phase를 SSE
  `STATE_SNAPSHOT`으로 받아 진행 상태와 결과를 갱신한다.
- 결과는 학교별 메뉴, 영역별 5점 평점·환산 점수, 100점 총점, Judge 보고서,
  개선안과 데이터 한계를 접근 가능한 카드와 표로 표시한다.
- `RUN_ERROR`는 구독자 내부 예외에 의존하지 않고 스트림 종료 후 명시적으로
  전파해 사용자 오류 상태로 변환한다.

### 3.5 Vite 개발 프록시

```ts
server: {
  port: 5173,
  proxy: {
    '/api': { target: 'http://localhost:8000', changeOrigin: true },
    '/agent': { target: 'http://localhost:8002', changeOrigin: true }
  }
}
```

---

## 4. MCP Server (`src/mcp`)

### 4.1 기술 스택

| 구분 | 선정 |
| --- | --- |
| 언어 | Python 3.12+ |
| 패키지/가상환경 | **uv** (`pyproject.toml`, `uv.lock`) |
| MCP 구현 | Python MCP SDK 기반 서버 |
| HTTP 클라이언트 | **httpx** (async) |
| 도구 명세 | `src/openapi.json` (OpenAPI 3.0.3) |
| 전송 방식 | Streamable HTTP (`/mcp`) |

### 4.2 디렉터리 구조

```text
src/mcp/
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── README.md
├── app/
│   ├── __init__.py
│   ├── config.py        # 환경 변수와 저장소 루트 .env 로드
│   ├── main.py          # MCP 서버 엔트리포인트와 Streamable HTTP 실행
│   ├── openapi.py       # OpenAPI 문서 로드 및 MCP 도구 등록
│   └── neis_client.py   # 인증키 주입, NEIS 비동기 HTTP 호출 및 오류 매핑
└── tests/               # OpenAPI, NEIS, MCP protocol 단위·통합 테스트
```

### 4.3 MCP 도구

| Tool | OpenAPI operationId | Description |
| --- | --- | --- |
| `getSchoolInfo` | `getSchoolInfo` | 학교명, 학교 코드, 교육청 코드 등으로 학교기본정보 조회 |
| `getMealServiceDietInfo` | `getMealServiceDietInfo` | 학교와 날짜 조건으로 급식식단정보 조회 |

- 시작할 때 `src/openapi.json`을 읽어 도구 입력 스키마를 구성한다.
- 명세의 `operationId`, 설명, 입력 파라미터와 필수 여부를 MCP 도구에 반영한다.
- 명세가 없거나 유효하지 않으면 도구가 일부만 등록된 상태로 실행하지 않고 시작 오류를 반환한다.
- `Type`, `pIndex`, `pSize`는 선택 파라미터이며 생략 시 `json`, `1`, `100`을 사용한다.
- 급식 도구의 `MMEAL_SC_CODE`는 중식 코드 `2`로 제한한다.
- `NEIS_API_KEY`는 도구 인자로 노출하지 않는다.
- NEIS 오류는 코드와 메시지를 포함한 MCP 도구 오류로 전달한다.
- `/health`는 Aspire와 Docker Compose의 liveness probe에만 사용한다.

---

## 5. Agent Service (`src/agent`)

### 5.1 기술 스택과 구성

| 구분 | 선정 |
| --- | --- |
| 언어/패키지 | Python 3.12+ / uv |
| 웹·프로토콜 | FastAPI + `agent-framework-ag-ui` |
| 에이전트 | Microsoft Agent Framework + `FoundryChatClient` |
| 인증 | `DefaultAzureCredential` (로컬 Azure CLI, Azure 관리 ID) |
| Aspire 리소스 | `Aspire.Hosting.Foundry` account + project + `gpt-5-mini` deployment |
| 데이터 도구 | `MCPStreamableHTTPTool` (`getSchoolInfo`, `getMealServiceDietInfo`만 허용) |
| endpoint | `POST /agent` (SSE), `GET /health` |

`src/agent/instructions/*.md`는 Nutrition, Health, Menu Quality, Judge 지침을
코드 밖에서 관리한다. 모든 점수 정의와 가중치의 사람이 읽는 단일 원본은 루트
`EVALUATION-RUBRIC.md`다.

### 5.2 데이터 준비와 워크플로

1. 학교 전체 건수에서 난수 인덱스를 표본 추출하고 필요한 MCP 페이지만 조회해
   중복 없는 후보 10곳을 만든다.
2. 선택한 두 학교의 해당 날짜 중식을 병렬 조회하고 누락 시 구조화 오류로 중단한다.
3. Nutrition(45), Health(30), Menu Quality(25) Agent를 Concurrent 실행한다.
4. Pydantic 구조화 출력에서 1~5 평점을 받아 애플리케이션 코드가 환산 점수와
   총점을 계산한다.
5. custom aggregator의 Judge가 점수를 수정하지 않고 근거·모순·한계를 검토해
   한국어 최종 보고서를 작성한다.

각 브라우저 실행은 thread별 workflow factory와 shared state를 사용해 격리된다.
정상적인 사용자 조치 오류는 `phase=error` 스냅샷으로, 예상하지 못한 실패는 AG-UI
`RUN_ERROR`로 전달한다.

### 5.3 데이터 한계

NEIS 메뉴명과 영양 문자열에 정량 나트륨·당류·포화지방이 없으면 해당 평가는
정성적 추정임을 밝힌다. 에이전트는 제공되지 않은 수치를 생성해서는 안 된다.

---

## 6. 데이터 모델 (Internal Schemas)

```ts
interface School {
  schoolCode: string;        // NEIS SD_SCHUL_CODE
  eduOfficeCode: string;     // NEIS ATPT_OFCDC_SC_CODE
  schoolName: string;        // NEIS SCHUL_NM
  eduOfficeName: string;     // NEIS ATPT_OFCDC_SC_NM
  lctnScNm: string | null;   // NEIS LCTN_SC_NM
}

interface Meal {
  date: string;              // YYYY-MM-DD
  dishes: string[];          // NEIS DDISH_NM (<br/> split)
  calorie: string | null;    // NEIS CAL_INFO
  origin: string[];          // NEIS ORPLC_INFO (<br/> split)
  nutrition: string[];       // NEIS NTR_INFO (<br/> split)
  servings: number | null;   // NEIS MLSV_FGR
}
```

---

## 7. 설계 결정 및 트레이드오프 (Decisions & Trade-offs)

### 7.1 백엔드 프록시 패턴

NEIS API를 프론트엔드에서 직접 호출하지 않고 백엔드 프록시를 둔다.

- **이유**: `NEIS_API_KEY` 노출 방지, 응답 정규화, 향후 캐싱/재시도 추가 용이.
- **트레이드오프**: 호출마다 한 번의 네트워크 hop이 추가된다.

### 7.2 중식 고정 (`MMEAL_SC_CODE=2`)

요구사항이 중식만을 대상으로 하므로 백엔드에서 코드를 고정한다. 조식/석식 지원 시 쿼리 파라미터로 확장한다.

### 7.3 최대 31일 제한

- UX와 응답 페이로드 안정성을 위해 조회 범위를 제한한다.
- 백엔드와 프론트엔드 양쪽에서 검증한다.

### 7.4 shadcn CLI 미사용, 컴포넌트 수기 작성

- 사용하는 컴포넌트가 Button, Input, Card, Calendar로 제한되어 수기 구성이 단순하다.
- Tailwind v4의 `@theme inline` 블록으로 shadcn 스타일 CSS 변수 토큰을 유지한다.

### 7.5 react-router-dom v7 + react-query v5

- React 19 호환 메이저 버전을 사용한다.
- 검색·식단 데이터는 react-query 캐시 키로 관리한다.

### 7.6 학교 검색 페이지네이션 미지원

- NEIS 단일 응답에서 최대 100건만 사용한다.
- 결과가 많으면 구체적인 검색어를 권장하며, 필요 시 백엔드 `?page=` 파라미터로 확장한다.

### 7.7 OpenAPI 기반 MCP 도구

- `src/openapi.json`의 `operationId`를 MCP 도구 이름으로 사용한다.
- 인증과 NEIS 오류 처리는 공통 HTTP 클라이언트에서 수행한다.
- 독립 프로세스와 원격 환경에서 연결할 수 있도록 `/mcp` 기반 Streamable HTTP 전송을 사용한다.

### 7.8 AG-UI와 결정적 점수 계산

- 브라우저와 agent는 임의 REST 응답이 아니라 AG-UI POST + SSE 계약을 사용한다.
- LLM은 영역별 구조화 평가만 생성하고 환산 점수·총점·승자 판정은 코드가 수행한다.
- Judge는 비채점 품질 게이트로 제한해 설명 품질이 급식 자체 점수를 바꾸지 않게 한다.
- 세 전문 호출을 병렬화해 순차 호출 대비 지연 시간을 줄이는 대신 모델 호출 비용은
  한 분석당 네 번 발생한다.

---

## 8. 환경 변수 (Environment)

저장소 루트의 `.env`:

```env
NEIS_API_KEY=발급받은_NEIS_인증키
FOUNDRY_PROJECT_ENDPOINT=https://.../api/projects/...
FOUNDRY_MODEL_DEPLOYMENT_NAME=배포_이름
```

- 미발급 시 `sample` 키로 동작할 수 있으나 페이지와 건수가 제한된다.
- Foundry 두 변수는 네이티브·Compose 실행용이다. Aspire에서는 Foundry integration
  resource reference가 `FOUNDRY_PROJECT_ENDPOINT`와
  `FOUNDRY_MODEL_DEPLOYMENT`를 주입한다.
- `MCP_URL` 기본값은 `http://127.0.0.1:8001/mcp`이며 Aspire에서는 MCP endpoint
  reference를 주입한다. base URL만 주입되면 agent가 `/mcp`를 보완한다.
- `.env`는 저장소에 커밋하지 않는다.

---

## 9. 실행 방법 (Run)

### 9.1 백엔드

```bash
cd src/api
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 9.2 프론트엔드

```bash
cd src/web
npm install
npm run dev
```

브라우저에서 <http://localhost:5173>에 접속한다.

### 9.3 MCP 서버

```bash
cd src/mcp
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

MCP endpoint는 `http://127.0.0.1:8001/mcp`이며 자세한 Inspector·Python client,
Aspire, Docker Compose 연결 방법은 `src/mcp/README.md`에 정리한다.

### 9.4 Agent 서비스

MCP 서버를 먼저 실행한 뒤:

```bash
az login
cd src/agent
uv sync --all-groups
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

Vite는 `AGENT_URL`이 없으면 `/agent`를 `http://localhost:8002`로 프록시한다.

---

## 10. 구현 기록 (Implementation Record)

### 10.1 완료된 웹 앱 작업

1. `bootstrap-api` — `uv init` + FastAPI/httpx/python-dotenv/pydantic 설치
2. `api-config` — `.env` 로딩 + Settings 모듈
3. `api-neis-client` — NEIS httpx 비동기 래퍼
4. `api-schools-route` — `GET /api/schools`
5. `api-meals-route` — `GET /api/meals` (중식 고정, 31일 제한)
6. `api-cors-health` — CORS 미들웨어 + `/api/health` + 에러 매핑
7. `api-manual-verify` — cURL로 서울고등학교 식단 조회 검증
8. `bootstrap-web` — Vite + React + TypeScript 스캐폴딩
9. `web-tailwind-shadcn` — Tailwind v4 + shadcn 스타일 컴포넌트
10. `web-routing-query` — react-router-dom, react-query, Vite proxy
11. `web-landing` — 검색 페이지 (300ms debounce)
12. `web-date-range` — 31일 한도 range date picker
13. `web-meals-result` — 날짜별 중식 카드
14. `web-manual-verify` — 전체 흐름 수동 검증
15. `docs` — 루트 `README.md` 업데이트
16. `mcp-openapi` — OpenAPI 검증·참조 해석·도구 입력 스키마 생성
17. `mcp-runtime` — NEIS 비동기 호출·오류 매핑·Streamable HTTP `/mcp`
18. `mcp-compose` — hardened MCP 이미지와 localhost 전용 Compose endpoint
19. `mcp-aspire` — Uvicorn 로컬 리소스와 internal ACA Container App 게시 모델
20. `mcp-tests` — OpenAPI·NEIS·MCP protocol 단위·통합 테스트와 CI
21. `mcp-docs` — 실행·연결·보안 정책 문서화
22. `web-analysis-tabs` — sticky 조회·분석 탭과 `/analysis` 라우트
23. `web-analysis-chat` — 로컬 메시지 채팅 UI와 Enter/수정자+Enter 키보드 동작
24. `agent-foundation` — Foundry/MCP 설정, 구조화 계약과 결정적 점수 계산
25. `concurrent-workflow` — 세 전문 에이전트 병렬 실행과 Judge aggregator
26. `agui-hosting` — typed shared state, AG-UI endpoint와 hardened 이미지
27. `web-analysis-ui` — 학교·날짜 선택, 진행 상태, 가중 결과와 Judge 보고서
28. `runtime-integration` — Aspire/Compose/nginx/CI/E2E 연결

### 10.2 구현 중 해결한 이슈

- **npm create vite 인터랙티브 프롬프트** → 비대화형 스캐폴딩 명령으로 우회했다.
- **shadcn CLI 초기화 중단** → UI 컴포넌트를 수기로 구성했다.
- **lucide-react 버전 확인** → 패키지 레지스트리의 최신 버전을 기준으로 설치했다.
- NEIS의 정상 응답과 `RESULT`만 있는 오류 응답을 공통 추출 로직으로 처리했다.
- MCP Docker build context를 `src`로 설정해 `src/openapi.json`을 중복 없이 이미지에 포함했다.
- `/mcp` trailing-slash redirect를 제거해 redirect를 따르지 않는 MCP SDK 클라이언트도 연결되게 했다.
