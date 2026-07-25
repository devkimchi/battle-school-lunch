# 전국 초중고 급식 정보 조회 앱

전국 초중고 급식 정보 조회 웹 앱과 NEIS OpenAPI 기반 MCP 서버 프로젝트.

```text
/
├── README.md    프로젝트 실행·테스트·배포 문서
├── AGENTS.md    AI 코딩 에이전트 작업 지침
├── PRD.md       제품 요구사항
├── TRD.md       기술 요구사항
├── .devcontainer/ GitHub Codespaces 개발 환경
├── apphost.mts  Aspire 오케스트레이션·Azure 배포 모델 (api + web)
├── aspire.config.json Aspire AppHost 설정
├── azure.yaml   Azure 프로젝트 식별자 (배포 모델은 apphost.mts)
├── compose.yaml Docker Compose 오케스트레이션
├── .env.example 환경 변수 템플릿
└── src/
    ├── api/         FastAPI 백엔드 (Python 3.12+ / uv)
    ├── web/         React + Vite + TypeScript 프런트엔드 (nginx 운영 서빙)
    ├── mcp/         OpenAPI 기반 MCP 서버 (Python 3.12+ / uv, 구현 예정)
    ├── e2e/         Playwright 엔드투엔드 테스트
    └── openapi.json NEIS Open API 스펙
```

프런트엔드는 `/api/*` 경로를 통해 백엔드와 통신합니다. `npm run dev` 모드에서는
`http://localhost:8000` 으로 프록시되며, 운영 빌드에서는 프런트엔드와 백엔드가
같은 오리진 아래 `/api`에서 접근 가능하다고 가정합니다.

MCP 서버는 `src/openapi.json`에서 `getSchoolInfo`와
`getMealServiceDietInfo` 도구 스키마를 구성하고, `/mcp`에서 Streamable HTTP
전송을 제공하도록 설계되어 있습니다. 제품 범위는 [PRD](./PRD.md), 시스템 구조와
기술 결정은 [TRD](./TRD.md), 각 앱의 사용법은 개별 `README.md`를 참고하세요.
이 문서는 현재 구현된 앱을 실행하고 테스트하기 위한 **단일 시작점**입니다.

## 1. 사전 준비물

| 도구 | 버전 | 사용 위치 |
| --- | --- | --- |
| Python | 3.12+ | `src/api`, `src/mcp` (네이티브 개발) |
| [`uv`](https://docs.astral.sh/uv/) | latest | `src/api`, `src/mcp` (네이티브 개발) |
| Node.js | 22+ (24 LTS 권장) | `src/web`, `src/e2e` (네이티브 개발) |
| npm | 10+ | `src/web`, `src/e2e` |
| [Aspire CLI](https://aspire.dev/get-started/install-cli/) | 13.4+ | `api` + `web` 로컬 오케스트레이션 |
| Docker | Compose 플러그인 포함 24+ | 컨테이너/Compose 흐름 (선택 사항) |
| NEIS API 키 | — | `src/api`, `src/mcp` 런타임 (실데이터 호출용) |

네이티브 개발 시 NEIS 키는 저장소 루트의 `.env`에 `NEIS_API_KEY=...`
형태로 넣습니다 (api는 pydantic-settings를 통해 자동 로드하고, Aspire와
Docker Compose도 동일한 변수를 읽습니다). MCP 서버도 같은 환경 변수만 사용하며 도구
인자로 키를 노출하지 않습니다. 테스트 스위트는 키가 **필요 없습니다** —
적절한 경계에서 NEIS / `/api/*`를 모킹합니다.

### GitHub Codespaces

저장소의 **Code → Codespaces → Create codespace**를 선택하면 `.devcontainer/` 설정으로
Python 3.12, Node.js 24, uv, Aspire CLI, Docker Compose 및 Azure CLI가 자동
설치됩니다. Aspire VS Code 확장과 동적 포트 전달도 활성화되며,
AppHost·API·웹·E2E 의존성과 Playwright Chromium은 최초 생성 시 준비됩니다.

실제 NEIS 데이터를 조회하려면 저장소 또는 사용자 Codespaces 시크릿에
`NEIS_API_KEY`를 등록하세요. 시크릿은 환경 변수로 주입되므로 `.env` 파일을 만들
필요가 없습니다. 개발 서버 포트 `5173`, `8000`, `8080`, `4173`은 자동 전달됩니다.

## 2. 로컬에서 앱 실행

세 가지 방법이 있습니다. Aspire로 두 앱을 함께 실행하는 방법(권장), `uv`와
`npm`으로 각 앱을 직접 실행하는 방법, Docker Compose로 운영용 컨테이너를
실행하는 방법입니다.

### 2.1 Aspire (권장, 두 앱을 함께)

루트의 TypeScript AppHost는 FastAPI를 Uvicorn 리소스로, React 앱을 Vite
리소스로 실행합니다. Aspire가 포트를 동적으로 할당하고 API가 준비된 후 웹을
시작하며, `API_URL`을 통해 Vite의 `/api` 프록시를 연결합니다.

```bash
npm install
npm run dev
```

Aspire 대시보드에 `api`와 `web`의 상태, 로그, 트레이스, 실행 URL이 표시됩니다.
`src/api`의 Python 환경과 `src/web`의 npm 의존성은 각 Aspire 통합이 시작 전에
준비합니다. AppHost는 루트 `.env`의 `NEIS_API_KEY`를 secret parameter로 모델링해
API에 주입하며, 값이 없으면 Aspire가 입력을 요청합니다. 종료하려면 실행 터미널에서
`Ctrl+C`를 누르거나 다른 터미널에서 `aspire stop`을 실행하세요.

### 2.2 네이티브 (uv + npm)

터미널 두 개가 필요합니다. 하나는 API, 다른 하나는 웹 앱용입니다.

#### 백엔드 (터미널 1)

```bash
cd src/api
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

- 앱: <http://localhost:8000>
- OpenAPI 문서: <http://localhost:8000/docs>

#### 프런트엔드 (터미널 2)

```bash
cd src/web
npm install
npm run dev
```

- 앱: <http://localhost:5173> (Vite 개발 서버, `/api`는 `:8000`으로 프록시됨)

#### 운영 스타일 프런트엔드 빌드

```bash
cd src/web
npm run build
npm run preview          # 빌드된 번들을 http://localhost:4173 에서 서빙
```

#### MCP 서버 (구현 예정)

MCP 서버는 `src/mcp`에 추가되며 `/mcp`에서 Streamable HTTP로 동작합니다.
구현 후 `src/mcp/README.md`에 실행 명령과 MCP 클라이언트 연결 예시를 제공합니다.
도구 입력 스키마는 `src/openapi.json`에서 로드하며 API 키는 서버 환경 변수로만
주입합니다.

### 2.3 Docker Compose (운영 스타일, 두 앱을 함께)

루트의 `compose.yaml`은 강화된 두 이미지(uv 기반 FastAPI 백엔드,
unprivileged nginx로 서빙되는 Vite 빌드 프런트엔드)를 빌드하고 오케스트레이션
합니다. 웹 컨테이너만 외부 진입점이며, 프라이빗 네트워크를 통해 `/api/*`를
백엔드로 리버스 프록시합니다.

사전 준비: Docker 24+ 와 Compose 플러그인(`docker compose ...`).

```bash
cp .env.example .env             # 그 다음 편집해서 NEIS_API_KEY 설정
docker compose up -d --build     # 이미지 빌드 + 두 서비스 기동
```

- 앱: <http://localhost:8080> (`.env`에서 `WEB_PORT`를 설정하면 다른 호스트 포트 사용 가능)
- API (web을 통해 프록시): <http://localhost:8080/api/health>
- `api` 서비스는 호스트에 **노출되지 않습니다** — Compose 네트워크 내부에서만 `http://api:8000`으로 접근 가능합니다.

유용한 명령어:

```bash
docker compose ps                # 서비스 헬스 확인
docker compose logs -f web api   # 로그 tail
docker compose down              # 컨테이너 중지 및 제거
docker compose down -v           # 네트워크까지 제거
```

`compose.yaml`에 포함된 보안 강화:

- 두 서비스 모두 non-root로 실행되며 `cap_drop: ALL`,
  `no-new-privileges`, 그리고 read-only 루트 파일시스템을 사용합니다. 쓰기 가능
  경로(`/tmp`, nginx 런타임 디렉터리, envsubst 출력 디렉터리)는 명시적인
  tmpfs 마운트로만 제공됩니다.
- `web` 서비스는 `api`가 `healthy`로 보고할 때까지 기다린 후 시작됩니다.
- `NEIS_API_KEY`는 필수입니다 — 설정되지 않으면 Compose가 명확한 에러와 함께
  즉시 실패합니다.

### 2.4 Aspire를 통한 Azure Container Apps 배포

`apphost.mts`가 Azure Container Apps 환경과 배포 토폴로지의 단일 원본입니다.
`api`는 internal ingress를 사용하는 Container App으로 배포되고,
`web`은 정적 Vite 빌드를 nginx 컨테이너의 public ingress로 제공합니다.
Aspire가 주입한 `API_UPSTREAM`을 사용해 nginx가 같은 오리진의 `/api` 요청을
내부 `api` 리소스로 전달합니다.

Aspire는 Container Apps Environment, Azure Container Registry, managed identity,
Aspire dashboard와 두 Container App을 프로비저닝하고, 이미지를 빌드·푸시합니다.
`neis-api-key` secret parameter는 `api`의 `NEIS_API_KEY` 환경 변수로만 전달됩니다.

사전 준비: [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli),
[Aspire CLI](https://aspire.dev/get-started/install-cli/), Docker.

```bash
az login

# 적용 전에 배포 파이프라인 확인
aspire publish --list-steps --non-interactive
aspire deploy --list-steps --non-interactive

# 환경별 비시크릿 설정
export Azure__SubscriptionId="<subscription-id>"
export Azure__Location="koreacentral"
export Azure__ResourceGroup="<resource-group>"

# Parameters__neis_api_key는 CI secret 또는 현재 셸 환경으로 별도 주입
aspire deploy --environment production --non-interactive
```

AppHost parameter 이름의 `-`는 환경 변수에서 `_`로 바뀌므로
`neis-api-key`는 `Parameters__neis_api_key`로 제공합니다. 시크릿 값은 저장소나
명령 기록에 넣지 말고 CI secret store 또는 현재 프로세스 환경으로 주입하세요.

배포 파일을 적용하지 않고 검토하려면 `aspire publish -o <output-dir>
--non-interactive`를 사용합니다. 이 산출물은 검토·인계용이며, 실제 배포는
산출물 디렉터리를 입력으로 받지 않고 AppHost에서 다시 해석합니다.

```bash
aspire deploy --environment production    # 이후 변경 재배포
aspire destroy --environment production   # Aspire가 만든 Azure 리소스 제거
```

`azure.yaml`에는 프로젝트 식별자만 남아 있습니다. 현재 `azd`는 TypeScript
AppHost를 직접 가져오지 못하므로 `azd up`용 서비스나 별도 Bicep 토폴로지를
병행하지 않습니다.

GitHub Actions용 Entra 앱, OIDC federated credential, Azure RBAC, 저장소 variable과
`NEIS_API_KEY` secret은 다음 스크립트 중 하나로 구성할 수 있습니다. 두 스크립트
모두 Azure CLI와 GitHub CLI 로그인이 필요하며, `NEIS_API_KEY`는 환경 변수 또는
보안 프롬프트로 입력받습니다.

```bash
./scripts/aspire-pipeline-config.sh --enable-deployment
```

```powershell
./scripts/aspire-pipeline-config.ps1 -EnableDeployment
```

## 3. 앱 테스트

작은 것부터 큰 것까지 세 가지 테스트 계층:

| 계층 | 위치 | 도구 | 속도 | 모킹 대상 |
| --- | --- | --- | --- | --- |
| 단위 / 통합 (API) | `src/api/tests/` | pytest + respx | < 1초 | NEIS HTTP 경계 |
| 단위 / 통합 (Web) | `src/web/src/**/*.test.*`, `src/web/src/test/integration/` | Vitest + RTL + MSW | ~4초 | `/api/*` (브라우저) |
| 엔드투엔드 | `src/e2e/tests/` | Playwright (Chromium) | ~5초 | `/api/*` (브라우저, `page.route` 사용) |

### 3.1 백엔드 테스트 (40개)

```bash
cd src/api
uv sync --all-groups            # pytest + respx + pytest-cov 설치
uv run pytest                   # 전체 테스트
uv run pytest -m unit           # 단위 테스트만
uv run pytest -m integration    # 통합 테스트만
uv run pytest --cov=app         # 커버리지와 함께 실행
```

`tests/conftest.py`는 공유 픽스처(설정 오버라이드, `TestClient`, respx 모의
객체, NEIS row 팩토리)를 제공합니다. 어떤 테스트도 실제 NEIS 서비스에 접근하지
않습니다.

### 3.2 프런트엔드 테스트 (17개)

```bash
cd src/web
npm install
npm test                   # 1회 실행
npm run test:watch         # watch 모드
npm run test:coverage      # 커버리지 리포트 (HTML은 ./coverage)
```

`src/test/msw/handlers.ts`의 MSW 핸들러가 모든 `/api/*` 호출을 가로채므로
테스트는 결정적이고 오프라인에서 실행됩니다.

### 3.3 엔드투엔드 테스트 (3개)

E2E 스위트는 `web`의 **운영 Vite 번들**을 대상으로 Chromium에서 실행되며,
`page.route()`로 `/api/*` 호출을 가로챕니다. FastAPI 백엔드는 실행 중이지
**않아도** 됩니다.

```bash
cd src/e2e
npm install
npx playwright install chromium     # 1회성, 브라우저 바이너리 다운로드
npm test                            # ../web 빌드 (pretest) 후 Playwright 실행
```

기타 유용한 명령어:

```bash
npm run test:headed     # 브라우저를 보면서 실행
npm run test:ui         # Playwright UI 모드 (디버깅에 매우 유용)
npm run report          # 최신 HTML 리포트 열기
```

### 3.4 전체 실행

저장소 루트에서:

```bash
( cd src/api  && uv sync --all-groups && uv run pytest ) \
  && ( cd src/web  && npm install && npm test ) \
  && ( cd src/e2e  && npm install && npx playwright install chromium && npm test )
```

기대 결과: **40 + 17 + 3 = 60개 테스트 통과**.

## 4. 디렉터리 구조

```text
school-lunch/
├── .github/             이슈/PR 템플릿, CODEOWNERS, Dependabot, CI
├── .devcontainer/       GitHub Codespaces 개발 환경
├── AGENTS.md            AI 코딩 에이전트 작업 지침
├── README.md            현재 문서
├── PRD.md               제품 요구사항
├── TRD.md               기술 요구사항
├── CONTRIBUTING.md      기여 가이드
├── SECURITY.md          취약점 신고 정책
├── apphost.mts          Aspire 로컬 오케스트레이션·Azure 배포 모델
├── aspire.config.json   Aspire AppHost 설정·통합 패키지
├── azure.yaml           Azure 프로젝트 식별자
├── compose.yaml         Docker Compose: api + web 오케스트레이션
├── .env.example         환경 변수 템플릿 (NEIS_API_KEY, WEB_PORT)
└── src/
    ├── openapi.json     백엔드·MCP 도구의 단일 NEIS Open API 명세
    ├── api/
    │   ├── app/         FastAPI 앱과 `/api/*` 라우터
    │   ├── tests/       pytest 단위·통합 테스트
    │   ├── Dockerfile
    │   ├── pyproject.toml
    │   └── uv.lock
    ├── web/
    │   ├── src/         페이지, UI 컴포넌트, API 래퍼, Vitest 테스트
    │   ├── public/      정적 파일
    │   ├── nginx/       운영 nginx 설정
    │   ├── Dockerfile
    │   └── package.json
    ├── mcp/             OpenAPI 기반 Streamable HTTP MCP 서버 (구현 예정)
    └── e2e/
        ├── tests/       Playwright 시나리오
        ├── support/     Page Object Model
        ├── fixtures/    NEIS 형식 테스트 페이로드
        ├── playwright.config.ts
        └── package.json
```

## 5. 트러블슈팅

- **포트가 이미 사용 중** — `8000`(api), `5173`(web dev), `4173`(web preview / e2e),
  `8080`(compose web). `--port`로 변경하거나, compose의 경우 `.env`에 `WEB_PORT=...`
  설정, 또는 이전 프로세스를 종료하세요.
- **E2E `webServer` 타임아웃** — Playwright는 `127.0.0.1:4173`을 프로빙합니다.
  설정은 Vite preview를 `127.0.0.1`에 명시적으로 바인딩해 일치시킵니다. 호스트를
  변경하는 경우 양쪽 모두 업데이트해야 합니다.
- **개발 환경에서 NEIS 키 누락** — `api`와 MCP 서버 런타임에 필요합니다. 테스트는
  필요 없습니다.
- **Compose: `NEIS_API_KEY is required`** — `.env.example`을 `.env`로 복사한 뒤
  키를 설정하거나, `docker compose up` 전에 쉘에서 export 하세요.
