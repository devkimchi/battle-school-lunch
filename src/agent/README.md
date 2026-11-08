# 급식 비교 멀티에이전트 서비스

Microsoft Agent Framework와 Copilot SDK로 두 학교의 같은 날짜 중식을 비교하는
Python 서비스입니다. 브라우저에는 AG-UI `POST /agent` + SSE endpoint를 제공하고,
학교와 중식 데이터는 기존 MCP 서버의 `getSchoolInfo`, `getMealServiceDietInfo`
도구로만 조회합니다.

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
| `COPILOT_AUTH_MODE` | 아니요 | 기본 `local`; 배포 Agent는 AppHost가 `pat`로 설정 |
| `COPILOT_MODEL` | 아니요 | 기본 `auto`; Copilot SDK 모델 ID로 변경 가능 |
| `COPILOT_GITHUB_TOKEN` | PAT 모드만 | Azure 배포에서 Actions secret으로 주입하는 사용자 소유 fine-grained PAT |
| `MCP_URL` | 아니요 | 기본 `http://127.0.0.1:8001/mcp`; base URL이면 `/mcp` 자동 보완 |
| `PORT` | 아니요 | 기본 `8002` |

로컬 `local` 모드는 개발자의 개인 Copilot 로그인 사용자로 인증하며 PAT가
필요하지 않습니다. Azure 배포의 `pat` 모드는 `COPILOT_GITHUB_TOKEN`을 명시적으로
사용하고 로그인된 사용자나 다른 환경 토큰으로 fallback하지 않습니다. 배포 PAT는
GitHub fine-grained PAT의 `Copilot Requests` 권한을 가져야 합니다. `az login`은
Azure 리소스 프로비저닝용이며 Copilot 추론 인증과는 별개입니다.

Aspire 모델 설정 우선순위는 명시적 `copilot-model` parameter > 프로세스
`COPILOT_MODEL` > 저장소 루트 `.env`의 `COPILOT_MODEL` > 기본값 `auto`입니다.
별도 모델을 지정하지 않으면 SDK가 `auto`를 사용합니다. 토큰은 `.env`, 명령
인자, 로그 또는 프런트엔드에 기록하지 않습니다.

## 실행

MCP 서버를 먼저 `127.0.0.1:8001`에서 실행하고:

```bash
cd src/agent
uv sync --all-groups
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

실행 전에 Copilot CLI에서 개인 계정으로 로그인합니다. `az login`은 Azure 배포를
위한 것이므로 로컬 Copilot 로그인 대신 사용할 수 없습니다. 배포용 PAT는 로컬
실행에 필요하지 않습니다.

- AG-UI: <http://127.0.0.1:8002/agent>
- Health: <http://127.0.0.1:8002/health>

저장소 루트에서 `npm run dev`를 실행하면 Aspire가 `mcp → agent → web` 순서로
준비 상태를 관리합니다. Agent의 `/health` 성공은 Copilot 인증이나 모델 추론 성공을
의미하지 않습니다. `COPILOT_GITHUB_TOKEN` Actions secret을 교체한 뒤에는
Aspire 배포를 다시 실행해 새 토큰이 Agent Container App revision에 반영되었는지
확인합니다. 실제 배포는 대상 환경을 확인한 뒤 진행합니다.

컨테이너 이미지 빌드는 Copilot SDK runtime을 미리 내려받아 포함하도록
구성되어 런타임 다운로드에 의존하지 않게 합니다. 최종 이미지를 빌드하고
UID 10001 non-root 사용자로 SDK runtime 시작·종료와 실행 파일 접근 권한을
확인했습니다. 실제 Copilot 추론은 자동 이미지 검증에서 실행하지 않습니다.

## 테스트

```bash
cd src/agent
uv sync --all-groups
uv run pytest
uv run pytest -m unit
uv run pytest -m integration
```

테스트는 MCP 데이터 소스와 Copilot SDK client/runtime 경계를 fake로 대체하므로
실제 NEIS나 Copilot 모델을 호출하지 않으며 Azure CLI 로그인 또는 PAT가 필요하지
않습니다.

## 오류와 데이터 한계

- 선택 날짜의 중식이 한 곳이라도 없으면 `DATA_UNAVAILABLE` 상태로 평가 전에
  중단합니다.
- 예상하지 못한 MCP/Copilot SDK 실패는 AG-UI `RUN_ERROR`로 전달합니다.
- NEIS에 정량 나트륨·당류·포화지방이 없으면 정성적 추정임을 명시하며 임의 수치를
  만들지 않습니다.
