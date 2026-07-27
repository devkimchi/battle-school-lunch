# 상세 개발 가이드

루트 [README](../README.md)의 빠른 시작보다 각 실행 방식, 서비스 endpoint,
테스트 계층과 배포 운영을 자세히 설명합니다.

## 서비스 구성

| 서비스 | 구현 | 로컬 기본 endpoint | 역할 |
| --- | --- | --- | --- |
| Web | React 19, Vite 8, TypeScript, nginx | `http://localhost:5173` | 학교 검색·중식 조회·비교 분석 UI |
| API | FastAPI, httpx | `http://localhost:8000` | NEIS 응답 정규화와 `/api/*` 제공 |
| MCP | Python MCP SDK, Starlette | `http://127.0.0.1:8001/mcp` | OpenAPI 기반 NEIS 도구 제공 |
| Agent | Microsoft Agent Framework, AG-UI | `http://127.0.0.1:8002/agent` | 세 전문 평가와 AI Judge 실행 |

Web은 조회 기능에서 `/api/*`, 분석 기능에서 `/agent`만 호출합니다. NEIS API 키와
Azure 자격 증명은 브라우저에 전달되지 않습니다. 급식 조회는 중식
(`MMEAL_SC_CODE=2`)으로 고정하며 날짜 범위는 최대 31일입니다.

## 환경 변수

| 변수 | 소비자 | 설명 |
| --- | --- | --- |
| `NEIS_API_KEY` | API, MCP | NEIS 인증키; Aspire secret parameter의 원본 |
| `NEIS_BASE_URL` | API, MCP | 선택적 NEIS base URL override |
| `CORS_ORIGINS` | API | 네이티브 Web origin 목록 |
| `API_URL`, `AGENT_URL` | Vite | 개발 프록시 대상 |
| `API_UPSTREAM`, `AGENT_UPSTREAM` | nginx | Azure internal endpoint |
| `FOUNDRY_PROJECT_ENDPOINT` | Agent | 네이티브 Foundry project endpoint |
| `FOUNDRY_MODEL_DEPLOYMENT_NAME` | Agent | 네이티브 model deployment |
| `FOUNDRY_PROJECT_URI` | Agent | Aspire project reference가 주입 |
| `FOUNDRY_MODEL_MODELNAME` | Agent | Aspire model reference가 주입 |
| `MCP_URL` | Agent | 기본 `http://127.0.0.1:8001/mcp` |

루트 `.env.example`을 `.env`로 복사해 사용합니다. Aspire 로컬 실행에는
`NEIS_API_KEY`만 필요하며, 개별 서비스를 네이티브로 실행할 때 Foundry endpoint와
deployment name도 설정합니다.

## Aspire 실행

TypeScript AppHost인 `apphost.mts`는 다음 리소스를 모델링합니다.

- Uvicorn 기반 `api`, `mcp`, `agent`
- Vite 기반 `web`
- Azure Container Apps environment
- Microsoft Foundry account, project, 10K TPM `gpt-5-mini` deployment
- Agent 전용 user-assigned identity와 Foundry 역할 할당

```bash
npm install
az login
npm run dev
```

`mcp → agent → web` 준비 순서가 적용됩니다. Vite에는 `API_URL`과 `AGENT_URL`,
운영 nginx에는 `API_UPSTREAM`과 `AGENT_UPSTREAM`이 endpoint reference로
주입됩니다.

## 개별 서비스 네이티브 실행

Aspire 없이 특정 앱만 개발할 때 사용합니다. 분석 흐름 전체를 사용하려면 아래
네 서비스를 모두 실행해야 합니다.

### API

```bash
cd src/api
uv sync --all-groups
uv run uvicorn app.main:app --reload --port 8000
```

- API: <http://localhost:8000>
- OpenAPI UI: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/health>

### MCP

```bash
cd src/mcp
uv sync --all-groups
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

- MCP: <http://127.0.0.1:8001/mcp>
- Health: <http://127.0.0.1:8001/health>

### Agent

MCP를 먼저 실행하고 `.env`에 네이티브 Foundry 설정을 추가합니다.

```dotenv
FOUNDRY_PROJECT_ENDPOINT=https://example.services.ai.azure.com/api/projects/example
FOUNDRY_MODEL_DEPLOYMENT_NAME=deployment-name
```

```bash
az login
cd src/agent
uv sync --all-groups
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

- AG-UI: <http://127.0.0.1:8002/agent>
- Health: <http://127.0.0.1:8002/health>

### Web

```bash
cd src/web
npm install
npm run dev
```

Vite는 `/api`를 `API_URL` 또는 `http://localhost:8000`으로, `/agent`를
`AGENT_URL` 또는 `http://localhost:8002`로 프록시합니다.

## MCP Inspector

```bash
npx -y @modelcontextprotocol/inspector
```

transport는 `Streamable HTTP`를 선택합니다.

- 네이티브: `http://127.0.0.1:8001/mcp`
- Aspire: 대시보드의 `mcp` endpoint 뒤에 `/mcp` 추가

연결 후 `getSchoolInfo`, `getMealServiceDietInfo` 도구와 OpenAPI에서 생성된 입력
스키마를 확인할 수 있습니다.

## Azure Container Apps 배포

`apphost.mts`가 Azure 배포 토폴로지의 단일 원본입니다. `api`, `mcp`, `agent`는
internal ingress, `web`은 external ingress로 배포됩니다. nginx는 같은 오리진의
`/api`와 `/agent`를 internal 서비스로 프록시하며 AG-UI SSE buffering을
비활성화합니다.

```bash
az login
aspire publish --list-steps --non-interactive
aspire deploy --list-steps --non-interactive
aspire deploy --environment production --non-interactive
```

`neis-api-key` parameter는 `Parameters__neis_api_key`로 CI에서 주입할 수 있습니다.
시크릿은 저장소, 명령 인자, 로그에 넣지 않습니다.

### GitHub Actions 배포 구성

CI는 API, MCP, Agent, Web, E2E 작업이 모두 성공한 뒤 `AZURE_DEPLOYMENT=true`인
`main` push에서 Aspire 배포를 실행합니다. Entra 앱, OIDC federated credential,
Azure RBAC, 저장소 variable과 `NEIS_API_KEY` secret은 다음 중 운영체제에 맞는
스크립트로 구성합니다.

```powershell
./scripts/aspire-pipeline-config.ps1
```

```bash
./scripts/aspire-pipeline-config.sh
```

배포를 즉시 활성화하려면 PowerShell은 `-EnableDeployment`, Bash는
`--enable-deployment`를 추가합니다.

## 테스트 계층

| 계층 | 위치 | 도구 | 모킹 경계 |
| --- | --- | --- | --- |
| API | `src/api/tests/` | pytest, respx | NEIS HTTP |
| MCP | `src/mcp/tests/` | pytest, respx, MCP SDK | NEIS HTTP |
| Agent | `src/agent/tests/` | pytest, Agent Framework | MCP, Foundry |
| Web | `src/web/src/**/*.test.*` | Vitest, RTL, MSW | `/api/*`, AG-UI client |
| E2E | `src/e2e/tests/` | Playwright Chromium | `/api/*`, `/agent` |

전체 검증은 루트에서 하나의 스크립트로 실행합니다.

```powershell
./scripts/test-all.ps1
```

```bash
./scripts/test-all.sh
```

테스트는 실제 NEIS, MCP 또는 Foundry 서비스에 접근하지 않습니다.

## 디렉터리 상세

```text
src/
├── openapi.json
├── api/
│   ├── app/              FastAPI 설정, NEIS client, `/api/*` router
│   └── tests/            단위·통합 테스트
├── web/
│   ├── src/              조회·분석 페이지, API·AG-UI client
│   ├── nginx/            운영 reverse proxy 설정
│   └── public/           정적 asset
├── mcp/
│   ├── app/              OpenAPI loader, NEIS client, `/mcp`
│   └── tests/            도구 schema·protocol 테스트
├── agent/
│   ├── app/              데이터 준비, Concurrent workflow, AG-UI
│   ├── instructions/     전문 Agent와 Judge 지침
│   └── tests/            점수·workflow·stream 테스트
└── e2e/
    ├── tests/            조회·분석 브라우저 시나리오
    ├── fixtures/         모의 응답
    └── support/          Page Object와 test fixture
```

## 관련 문서

- [API](./api/README.md)
- [Web](./web/README.md)
- [MCP](./mcp/README.md)
- [Agent](./agent/README.md)
- [E2E](./e2e/README.md)
- [제품 요구사항](../PRD.md)
- [기술 요구사항](../TRD.md)
- [평가 기준](../EVALUATION-RUBRIC.md)
