# 전국 초중고 급식 정보 조회 앱

전국 초중고 급식 정보 조회 앱.

```text
/
├── README.md    프로젝트 실행·테스트·배포 문서
├── AGENTS.md    AI 코딩 에이전트 작업 지침
├── PRD.md       제품 요구사항
├── TRD.md       기술 요구사항
├── .devcontainer/ GitHub Codespaces 개발 환경
├── azure.yaml   azd 서비스 매핑
├── compose.yaml Docker Compose 오케스트레이션
├── .env.example 환경 변수 템플릿
├── infra/       Azure Container Apps용 Bicep
└── src/
    ├── api/         FastAPI 백엔드 (Python 3.12+ / uv)
    ├── web/         React + Vite + TypeScript 프런트엔드 (nginx 운영 서빙)
    ├── e2e/         Playwright 엔드투엔드 테스트
    └── openapi.json NEIS Open API 스펙
```

프런트엔드는 `/api/*` 경로를 통해 백엔드와 통신합니다. `npm run dev` 모드에서는
`http://localhost:8000` 으로 프록시되며, 운영 빌드에서는 프런트엔드와 백엔드가
같은 오리진 아래 `/api`에서 접근 가능하다고 가정합니다.

각 앱의 자세한 내용은 개별 `README.md`를 참고하세요. 이 문서는 모든 것을
실행하고 테스트하기 위한 **단일 시작점**입니다.

## 1. 사전 준비물

| 도구 | 버전 | 사용 위치 |
| --- | --- | --- |
| Python | 3.12+ | `src/api` (네이티브 개발) |
| [`uv`](https://docs.astral.sh/uv/) | latest | `src/api` (네이티브 개발) |
| Node.js | 22+ (24 LTS 권장) | `src/web`, `src/e2e` (네이티브 개발) |
| npm | 10+ | `src/web`, `src/e2e` |
| Docker | Compose 플러그인 포함 24+ | 컨테이너/Compose 흐름 (선택 사항) |
| NEIS API 키 | — | `src/api` 런타임 (실데이터 호출용) |

네이티브 개발 시 NEIS 키는 저장소 루트의 `.env`에 `NEIS_API_KEY=...`
형태로 넣습니다 (api는 pydantic-settings를 통해 자동 로드하고, Docker Compose
및 azd도 동일한 변수를 읽습니다). 테스트 스위트는 키가 **필요 없습니다** —
적절한 경계에서 NEIS / `/api/*`를 모킹합니다.

### GitHub Codespaces

저장소의 **Code → Codespaces → Create codespace**를 선택하면 `.devcontainer/` 설정으로
Python 3.12, Node.js 24, uv, Docker Compose, Azure CLI, Bicep 및 azd가 자동 설치됩니다.
API·웹·E2E 의존성과 Playwright Chromium도 최초 생성 시 준비됩니다.

실제 NEIS 데이터를 조회하려면 저장소 또는 사용자 Codespaces 시크릿에
`NEIS_API_KEY`를 등록하세요. 시크릿은 환경 변수로 주입되므로 `.env` 파일을 만들
필요가 없습니다. 개발 서버 포트 `5173`, `8000`, `8080`, `4173`은 자동 전달됩니다.

## 2. 로컬에서 앱 실행

두 가지 방법이 있습니다. `uv`와 `npm`으로 앱을 직접 실행하는 방법(빠른 이너
루프 개발에 적합)과, Docker Compose로 운영용 컨테이너를 실행하는 방법(실제
배포될 이미지를 점검하기 좋음)입니다.

### 2.1 네이티브 (uv + npm)

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

### 2.2 Docker Compose (운영 스타일, 두 앱을 함께)

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

### 2.3 `azd up`을 통한 Azure Container Apps 배포

`infra/` 아래의 Bicep과 기존 Dockerfile을 사용해 두 앱을 Azure Container Apps
에 프로비저닝 및 배포합니다. 프런트엔드(`web`)만 퍼블릭 ingress이고, 백엔드
(`api`)는 internal-only이며 환경의 프라이빗 DNS를 통해 `web`에서만 접근
가능합니다.

프로비저닝되는 리소스:

- 리소스 그룹 (`rg-<env-name>`)
- Log Analytics + Application Insights
- User-Assigned Managed Identity (두 앱이 ACR에서 이미지를 풀할 때 사용)
- Azure Container Registry (admin 비활성화, UAMI에 `AcrPull` 부여)
- Azure Container Apps Environment (Consumption, 로그는 Log Analytics로 전송)
- `api` Container App — **internal** ingress, 포트 8000, NEIS_API_KEY는 시크릿
- `web` Container App — **external** ingress, 포트 8080, `API_UPSTREAM`은 `https://<api-internal-fqdn>` 으로 연결

사전 준비: [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), Docker.

```bash
# 환경별 일회성 설정
azd auth login
azd env new <random-string>       # 임의의 이름; 리소스 그룹 접미사를 결정함
azd env set NEIS_API_KEY <key>    # 선택: 비대화형 실행 시 미리 설정

# 프로비저닝 + 빌드 + 푸시 + 배포
azd up                            # 키가 없으면 마스킹 입력 후 환경에 저장
```

`azd up`은 리전을 선택하거나(또는 `AZURE_LOCATION`을 설정할 수 있음) 인프라를
프로비저닝하고, 두 Docker 이미지를 로컬에서 빌드해 프로비저닝된 ACR로 푸시한
뒤 Container Apps를 새 이미지로 업데이트합니다. 실행 마지막에 웹 URL이
`SERVICE_WEB_URI`로 출력됩니다.

`NEIS_API_KEY`가 현재 azd 환경에 없으면 `preprovision` 훅이 마스킹된 입력을
요청하고 `.azure/<환경명>/.env`에 저장합니다. 이후 같은 환경의 배포에서는 저장된
값을 재사용합니다. CI처럼 비대화형으로 실행할 때는 먼저
`azd env set NEIS_API_KEY <key>`로 설정하세요.

유용한 후속 명령어:

```bash
azd deploy            # 코드 변경 후 재빌드 + 푸시 + 재배포 (인프라 변경 없음)
azd provision         # bicep만 적용 (이미지 푸시 없음)
azd show              # 엔드포인트와 리소스 참조를 표시
azd monitor --live    # App Insights 실시간 로그
azd down --purge      # 프로비저닝된 모든 리소스 삭제
```

참고 사항:

- 각 Container App의 `azd-service-name` 태그(`api`, `web`)가 azd가 어떤 앱을
  업데이트할지 식별하는 데 사용됩니다. `azure.yaml`의 서비스 이름과 Bicep
  태그를 동기화해 유지하세요.
- 앱 간 연결은 `infra/resources.bicep`에서 결정적으로 계산됩니다(두 Container
  App 사이에 순환 참조 없음): `web`은 `api`의 internal FQDN을 알고 있고,
  `api`의 `CORS_ORIGINS`에는 `web`의 퍼블릭 URL이 미리 채워져 있습니다.
- 운영 환경에서 Web → API 통신은 nginx → `https://<api>.internal.<env-domain>`
  로 이루어지며 (HTTPS, 환경 엣지에서 종단), 업스트림의 호스트 헤더 라우팅과
  TLS SNI가 모두 동작하도록 nginx 설정에서 `proxy_set_header Host $proxy_host`
  와 `proxy_ssl_server_name on`을 적용합니다.

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
├── azure.yaml           azd 서비스 매핑 (api + web → containerapp)
├── compose.yaml         Docker Compose: api + web 오케스트레이션
├── .env.example         환경 변수 템플릿 (NEIS_API_KEY, WEB_PORT)
├── infra/               `azd up`에서 사용하는 Bicep
│   ├── main.bicep
│   ├── main.parameters.json
│   └── resources.bicep
└── src/
    ├── openapi.json     백엔드 구현 기준 NEIS Open API 스펙
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
- **개발 환경에서 NEIS 키 누락** — `api` 런타임만 필요로 합니다. 테스트는 필요
  없습니다.
- **Compose: `NEIS_API_KEY is required`** — `.env.example`을 `.env`로 복사한 뒤
  키를 설정하거나, `docker compose up` 전에 쉘에서 export 하세요.
