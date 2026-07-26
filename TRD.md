# TRD — 급식 정보 조회 및 분석 웹 앱

> [PRD](./PRD.md)의 제품 요구사항을 구현하기 위한 기술 요구사항 문서. NEIS API 계약은 [`src/openapi.json`](./src/openapi.json)을 단일 명세 원본으로 사용한다.

---

## 1. 시스템 구성 (System Architecture)

```text
Web browser
    │ /api/*
    ▼
Frontend (React/Vite → nginx or YARP)
    │ /api/*
    ▼
Backend (FastAPI)
    │ HTTPS + NEIS_API_KEY
    ▼
NEIS Open API

MCP client
    │ Streamable HTTP /mcp
    ▼
MCP server
    │ OpenAPI 기반 도구 + HTTPS + NEIS_API_KEY
    ▼
NEIS Open API
```

- 프론트엔드는 NEIS를 직접 호출하지 않고 백엔드의 `/api/*`만 사용한다.
- 급식 분석 채팅은 현재 프론트엔드 로컬 상태로만 동작하며 백엔드나 MCP 서버를 호출하지 않는다.
- MCP 서버는 `src/openapi.json`에서 도구 스키마를 구성하고 NEIS를 직접 호출한다.
- 백엔드와 MCP 서버는 `NEIS_API_KEY`를 서버 환경 변수로만 주입받는다.
- 로컬에서는 TypeScript Aspire AppHost가 `api`와 `web`을 오케스트레이션한다.
- Azure에서는 AppHost가 하나의 Container Apps Environment에 internal `api`와
  public `web`을 배포하며, `web`의 nginx가 `/api`를 내부 서비스로 프록시한다.
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

### 3.2 디렉터리 구조

```text
src/web/
├── .dockerignore
├── Dockerfile
├── eslint.config.js
├── index.html
├── package.json
├── package-lock.json
├── vite.config.ts        # @tailwindcss/vite, alias '@', proxy /api → :8000
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
| `/analysis` | MealAnalysisPage (프론트엔드 전용 분석 채팅) |

`App.tsx`의 공통 셸은 모든 경로 상단에 `학교 급식 조회`와 `학교 급식 분석`
링크를 표시한다. 현재 경로는 `aria-current="page"`로 식별하며, 내비게이션은
`position: sticky`, `top: 0`으로 스크롤 중에도 화면 상단에 유지한다.

### 3.4 분석 채팅 UI

- `MealAnalysisPage`는 React 로컬 상태에 사용자 메시지 배열과 현재 입력값을 보관한다.
- 공백을 제거한 입력이 비어 있으면 전송 버튼을 비활성화하고 폼 제출도 무시한다.
- 유효한 폼 제출은 사용자 메시지를 목록에 추가하고 입력값을 초기화한다.
- `textarea`의 일반 `Enter` 기본 동작은 유지해 줄바꿈을 입력한다.
- `Ctrl+Enter` 또는 `Command+Enter`는 IME 조합 중이 아닐 때
  `requestSubmit()`으로 전송 버튼과 동일한 폼 검증·제출 경로를 사용한다.
- 서버 API 호출, 분석 응답 생성, 대화 영속 저장은 구현하지 않는다.

### 3.5 Vite 개발 프록시

```ts
server: {
  port: 5173,
  proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } }
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

## 5. 데이터 모델 (Internal Schemas)

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

## 6. 설계 결정 및 트레이드오프 (Decisions & Trade-offs)

### 6.1 백엔드 프록시 패턴

NEIS API를 프론트엔드에서 직접 호출하지 않고 백엔드 프록시를 둔다.

- **이유**: `NEIS_API_KEY` 노출 방지, 응답 정규화, 향후 캐싱/재시도 추가 용이.
- **트레이드오프**: 호출마다 한 번의 네트워크 hop이 추가된다.

### 6.2 중식 고정 (`MMEAL_SC_CODE=2`)

요구사항이 중식만을 대상으로 하므로 백엔드에서 코드를 고정한다. 조식/석식 지원 시 쿼리 파라미터로 확장한다.

### 6.3 최대 31일 제한

- UX와 응답 페이로드 안정성을 위해 조회 범위를 제한한다.
- 백엔드와 프론트엔드 양쪽에서 검증한다.

### 6.4 shadcn CLI 미사용, 컴포넌트 수기 작성

- 사용하는 컴포넌트가 Button, Input, Card, Calendar로 제한되어 수기 구성이 단순하다.
- Tailwind v4의 `@theme inline` 블록으로 shadcn 스타일 CSS 변수 토큰을 유지한다.

### 6.5 react-router-dom v7 + react-query v5

- React 19 호환 메이저 버전을 사용한다.
- 검색·식단 데이터는 react-query 캐시 키로 관리한다.

### 6.6 학교 검색 페이지네이션 미지원

- NEIS 단일 응답에서 최대 100건만 사용한다.
- 결과가 많으면 구체적인 검색어를 권장하며, 필요 시 백엔드 `?page=` 파라미터로 확장한다.

### 6.7 OpenAPI 기반 MCP 도구

- `src/openapi.json`의 `operationId`를 MCP 도구 이름으로 사용한다.
- 인증과 NEIS 오류 처리는 공통 HTTP 클라이언트에서 수행한다.
- 독립 프로세스와 원격 환경에서 연결할 수 있도록 `/mcp` 기반 Streamable HTTP 전송을 사용한다.

### 6.8 프론트엔드 전용 분석 채팅

- 분석 API 계약이 없는 현재 단계에서는 채팅 상호작용과 레이아웃만 먼저 제공한다.
- 메시지를 로컬 상태로 제한해 존재하지 않는 분석 백엔드에 성공한 것처럼 보이는
  요청이나 임시 응답을 만들지 않는다.
- 향후 분석 API를 도입할 때는 `lib/api.ts` 래퍼와 react-query를 통해 연결하고,
  로딩·오류·스트리밍 상태를 별도 요구사항으로 정의한다.

---

## 7. 환경 변수 (Environment)

저장소 루트의 `.env`:

```env
NEIS_API_KEY=발급받은_NEIS_인증키
```

- 미발급 시 `sample` 키로 동작할 수 있으나 페이지와 건수가 제한된다.
- `.env`는 저장소에 커밋하지 않는다.

---

## 8. 실행 방법 (Run)

### 8.1 백엔드

```bash
cd src/api
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 8.2 프론트엔드

```bash
cd src/web
npm install
npm run dev
```

브라우저에서 <http://localhost:5173>에 접속한다.

### 8.3 MCP 서버

```bash
cd src/mcp
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

MCP endpoint는 `http://127.0.0.1:8001/mcp`이며 자세한 Inspector·Python client,
Aspire, Docker Compose 연결 방법은 `src/mcp/README.md`에 정리한다.

---

## 9. 구현 기록 (Implementation Record)

### 9.1 완료된 웹 앱 작업

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

### 9.2 구현 중 해결한 이슈

- **npm create vite 인터랙티브 프롬프트** → 비대화형 스캐폴딩 명령으로 우회했다.
- **shadcn CLI 초기화 중단** → UI 컴포넌트를 수기로 구성했다.
- **lucide-react 버전 확인** → 패키지 레지스트리의 최신 버전을 기준으로 설치했다.
- NEIS의 정상 응답과 `RESULT`만 있는 오류 응답을 공통 추출 로직으로 처리했다.
- MCP Docker build context를 `src`로 설정해 `src/openapi.json`을 중복 없이 이미지에 포함했다.
- `/mcp` trailing-slash redirect를 제거해 redirect를 따르지 않는 MCP SDK 클라이언트도 연결되게 했다.
