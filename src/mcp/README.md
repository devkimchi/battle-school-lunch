# NEIS MCP 서버

`src/openapi.json`을 단일 명세 원본으로 사용해 학교기본정보와 중식 급식정보를
MCP 도구로 제공하는 Python 서버입니다. 전송 방식은 `/mcp`의 Streamable HTTP이며,
NEIS 응답 JSON을 구조화 결과로 그대로 반환합니다.

## 환경 변수

| 이름 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `NEIS_API_KEY` | 아니요 | `sample` | 서버에서만 사용하는 NEIS 인증키 |
| `NEIS_BASE_URL` | 아니요 | OpenAPI `servers[0].url` | 테스트·프록시용 NEIS base URL override |
| `PORT` | 아니요 | `8000` | 컨테이너 실행 포트 |

저장소 루트 `.env`의 값도 자동으로 읽습니다. API 키는 MCP 도구 입력, 응답,
로그에 포함하지 않습니다.

## 네이티브 실행

```bash
cd src/mcp
uv sync --all-groups
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

- MCP: <http://127.0.0.1:8001/mcp>
- Health: <http://127.0.0.1:8001/health>

MCP Inspector로 연결:

```bash
npx -y @modelcontextprotocol/inspector
```

Inspector의 transport를 `Streamable HTTP`로 선택하고 URL에
`http://127.0.0.1:8001/mcp`를 입력합니다.

Python MCP SDK 클라이언트 예시:

```python
import asyncio

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    async with streamable_http_client("http://127.0.0.1:8001/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print([tool.name for tool in tools.tools])


asyncio.run(main())
```

## Aspire

저장소 루트에서 `npm run dev`를 실행하면 `mcp` Uvicorn 리소스가 `api`, `agent`,
`web`과 함께 시작됩니다. Aspire 대시보드에서 `mcp`의 동적 URL을 확인한 뒤
그 URL에 `/mcp`를 붙여 연결합니다.

Azure Container Apps 게시 모델에도 MCP가 포함되지만 ingress는 internal입니다.
인증 없는 MCP endpoint를 인터넷에 공개하지 않으며, 외부 클라이언트 연결은
별도의 인증·gateway 설계 후 활성화해야 합니다.

## 도구

| 도구 | 동작 |
| --- | --- |
| `getSchoolInfo` | 학교명, 학교 코드, 교육청 코드 등으로 학교기본정보 조회 |
| `getMealServiceDietInfo` | 학교와 날짜 조건으로 중식 급식정보 조회 |

- 이름, 설명, 파라미터 타입·제약은 시작 시 OpenAPI 문서에서 생성합니다.
- `Type`, `pIndex`, `pSize`는 선택 입력이며 기본값은 `json`, `1`, `100`입니다.
- `MMEAL_SC_CODE`는 제품 정책에 따라 중식 코드 `2`만 허용합니다.
- `INFO-200`은 데이터 없음 JSON으로 반환하고, 그 외 NEIS 오류는 코드와 메시지를
  포함한 MCP tool error로 반환합니다.
- 명세가 없거나 유효하지 않으면 일부 도구만 등록하지 않고 서버 시작에 실패합니다.

## 테스트

```bash
cd src/mcp
uv sync --all-groups
uv run pytest
uv run pytest -m unit
uv run pytest -m integration
```

모든 NEIS HTTP 호출은 respx로 모킹되며 실제 NEIS 서비스나 API 키를 사용하지 않습니다.
