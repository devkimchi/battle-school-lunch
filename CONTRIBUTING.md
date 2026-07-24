# School Lunch 기여 가이드

프로젝트에 기여해 주셔서 감사합니다. 이 저장소는 FastAPI 백엔드, React 프런트엔드,
Playwright 엔드투엔드 테스트 및 Azure 인프라로 구성되어 있습니다.

## 행동강령

프로젝트에 참여하면
[Contributor Covenant 행동강령](CODE_OF_CONDUCT.md)을 준수하는 데 동의한 것으로 간주합니다.

## 개발 환경 설정

필수 도구와 환경 변수 설정은 [`README.md`](./README.md)를 참고하세요.
GitHub Codespaces를 사용하면 `.devcontainer/` 설정이 필요한 도구, 각 작업 영역의
의존성 및 Playwright Chromium을 자동으로 준비합니다. 실제 NEIS 데이터를 조회하려면
`NEIS_API_KEY`를 Codespaces 시크릿으로 등록하세요.

로컬 환경에서는 각 작업 영역의 의존성을 개별적으로 설치합니다.

```sh
cd src/api
uv sync --all-groups

cd ../web
npm ci

cd ../e2e
npm ci
```

루트의 `.env` 또는 NEIS API 키를 절대 커밋하지 마세요. 테스트에서는 외부 NEIS 및
애플리케이션 API 호출을 모킹하므로 실제 API 키가 필요하지 않습니다.

## 풀 리퀘스트 생성 전 확인 사항

변경한 영역에 해당하는 검사를 실행합니다.

```sh
cd src/api
uv run pytest

cd ../web
npm run lint
npm test
npm run build

cd ../e2e
npx playwright install chromium
npm test
```

급식 조회는 `MMEAL_SC_CODE=2`로 고정하고, 프런트엔드의 API 접근은
`src/web/src/lib/api.ts`를 거쳐야 하며, 조회 기간은 최대 31일로 유지합니다.

## 브랜치와 커밋

브랜치 이름은 `feat/`, `fix/`, `docs/`, `chore/` 중 하나로 시작하고 간결하게 작성합니다.
커밋 메시지는 Conventional Commits 규칙에 따라 `feat:`, `fix:`, `test:`, `docs:`,
`refactor:`, `chore:` 등의 접두사를 사용합니다.

## 풀 리퀘스트

1. 변경 범위를 명확하게 유지하고 변경 이유를 설명합니다.
2. 동작이 변경되면 테스트를 추가하거나 수정합니다.
3. 변경 사항과 직접 관련된 문서를 업데이트합니다.
4. 관련 이슈가 있으면 `Closes #123` 형식으로 연결합니다.
5. 필수 CI 검사가 모두 통과했는지 확인합니다.
