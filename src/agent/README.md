# 급식 비교 멀티에이전트 서비스

Microsoft Agent Framework로 두 학교의 같은 날짜 중식을 비교하는 Python
서비스입니다. 브라우저에는 AG-UI `POST /agent` + SSE endpoint를 제공하고, 학교와
중식 데이터는 기존 MCP 서버의 `getSchoolInfo`, `getMealServiceDietInfo` 도구로만
조회합니다.

## 워크플로

1. MCP 학교 전체 건수에서 무작위 인덱스를 표본 추출해 후보 10곳을 반환합니다.
2. 사용자가 선택한 두 학교의 중식을 병렬 조회하고 누락 시 평가를 중단합니다.
3. Nutrition(45%), Health(30%), Menu Quality(25%) Agent를 Concurrent 실행합니다.
4. 코드는 `(평점 / 5) × 가중치`로 환산 점수와 100점 총점을 계산합니다.
5. AI Judge는 점수를 바꾸지 않고 근거, 개선안과 데이터 한계를 종합합니다.

평가 기준은 루트 [`EVALUATION-RUBRIC.md`](../../EVALUATION-RUBRIC.md), 역할별
지침은 [`instructions/`](./instructions/)의 Markdown 파일에서 관리합니다.
Aspire는 실행·배포 준비 시 rubric을 gitignored `.generated/`에 복사해 image build
context에 포함합니다.

## 환경 변수

| 이름 | 필수 | 설명 |
| --- | --- | --- |
| `FOUNDRY_PROJECT_ENDPOINT` | 예 | Microsoft Foundry project endpoint |
| `FOUNDRY_MODEL_DEPLOYMENT_NAME` | 조건부 | 네이티브·Compose 채팅 모델 deployment name |
| `FOUNDRY_MODEL_DEPLOYMENT` | 조건부 | Aspire Foundry reference가 주입하는 deployment name |
| `MCP_URL` | 아니요 | 기본 `http://127.0.0.1:8001/mcp`; base URL이면 `/mcp` 자동 보완 |
| `PORT` | 아니요 | 기본 `8002` |

인증 비밀은 설정에 저장하지 않습니다. 로컬에서는 `az login`의 Azure CLI 자격
증명, Azure Container Apps에서는 관리 ID를 `DefaultAzureCredential`이 사용합니다.

## 실행

MCP 서버를 먼저 `127.0.0.1:8001`에서 실행하고:

```bash
az login
cd src/agent
uv sync --all-groups
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

- AG-UI: <http://127.0.0.1:8002/agent>
- Health: <http://127.0.0.1:8002/health>

저장소 루트의 `npm run dev`를 사용하면 Aspire Foundry integration이 account,
project와 `gpt-5-mini` deployment를 모델링하고 연결 정보와 추론 역할을 agent에
주입합니다. Aspire는 `mcp → agent → web` 순서로 준비 상태를 관리합니다.

## 테스트

```bash
cd src/agent
uv sync --all-groups
uv run pytest
uv run pytest -m unit
uv run pytest -m integration
```

테스트는 MCP 데이터 소스와 Foundry chat client를 경계에서 대체하므로 실제 NEIS나
모델을 호출하지 않습니다.

## 오류와 데이터 한계

- 선택 날짜의 중식이 한 곳이라도 없으면 `DATA_UNAVAILABLE` 상태로 평가 전에
  중단합니다.
- 예상하지 못한 MCP/Foundry 실패는 AG-UI `RUN_ERROR`로 전달합니다.
- NEIS에 정량 나트륨·당류·포화지방이 없으면 정성적 추정임을 명시하며 임의 수치를
  만들지 않습니다.
