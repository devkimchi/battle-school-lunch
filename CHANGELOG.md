# 변경 이력

이 프로젝트의 주요 변경 사항을 이 문서에 기록합니다.

이 문서는 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따르며,
프로젝트 버전은 [유의적 버전](https://semver.org/lang/ko/spec/v2.0.0.html)을 기준으로 관리합니다.

## [출시 예정]

## [0.2.0] - 2026-07-25

### 추가

- OpenAPI 명세를 단일 원본으로 사용하는 MCP 서버 요구사항과 `/mcp` Streamable
  HTTP 전송, `getSchoolInfo`, `getMealServiceDietInfo` 도구 명세 추가
  ([#28](https://github.com/justinyoo/school-lunch/pull/28))
- Python API와 Vite 웹을 함께 실행하는 TypeScript Aspire AppHost 및 로컬
  오케스트레이션 구성 추가
  ([#30](https://github.com/justinyoo/school-lunch/pull/30))
- Aspire 초기화, 리소스 연결, 실행, 모니터링 및 배포용 에이전트 스킬 추가
  ([#30](https://github.com/justinyoo/school-lunch/pull/30))

### 변경

- 제품 요구사항과 기술 설계를 `PRD.md`와 `TRD.md`로 분리하고 MCP 구조, 테스트
  경계 및 구현 지침을 관련 문서에 반영
  ([#28](https://github.com/justinyoo/school-lunch/pull/28))
- Azure 배포 원본을 수동 Bicep/azd 구성에서 Aspire AppHost 기반 Azure Container
  Apps 모델로 전환
  ([#27](https://github.com/justinyoo/school-lunch/pull/27),
  [#30](https://github.com/justinyoo/school-lunch/pull/30))
- Dev Container에 Aspire CLI, Aspire VS Code 확장, 동적 포트 전달 및 AppHost
  의존성 설치를 추가
  ([#31](https://github.com/justinyoo/school-lunch/pull/31))

### 수정

- Azure 배포 시 `NEIS_API_KEY`를 안전하게 재사용, 입력 및 검증하도록 azd 훅 개선
  ([#27](https://github.com/justinyoo/school-lunch/pull/27))
- Azure Container Apps에서 API Uvicorn 명령과 nginx의 내부 API 프록시가 올바르게
  동작하도록 게시 구성을 수정
  ([#30](https://github.com/justinyoo/school-lunch/pull/30))
- Codespaces 생성 시 오래된 Yarn APT 소스와 불필요한 pnpm 설치로 Dev Container
  기능 설치가 실패하는 문제 수정
  ([#31](https://github.com/justinyoo/school-lunch/pull/31))

### 포함된 Pull Request

- [#27 Improve azd NEIS API key prompting](https://github.com/justinyoo/school-lunch/pull/27)
- [#28 Define OpenAPI-based MCP server requirements](https://github.com/justinyoo/school-lunch/pull/28)
- [#30 Initialize Aspire orchestration and Azure deployment](https://github.com/justinyoo/school-lunch/pull/30)
- [#31 Configure Aspire tooling in the devcontainer](https://github.com/justinyoo/school-lunch/pull/31)

## [0.1.0] - 2026-07-24

### 추가

- 전국 초중고 학교 검색 및 최대 31일 중식 조회 기능
- FastAPI, React, Docker Compose 및 Azure Container Apps 배포 구성
- GitHub Codespaces 개발 환경과 API/Web/E2E CI 파이프라인
- 저장소 상태 관리, 기여 가이드, Dependabot 및 보안 정책

### 변경

- GitHub Actions, Python, Node.js, nginx 및 프런트엔드 의존성 업데이트
- Vite 8, TypeScript 6, React 19 기반으로 프런트엔드 도구 체인 정합성 개선
- Git 작업 전 브랜치 확인, 계획 작업별 커밋 및 PR 템플릿 사용 규칙 문서화

### 수정

- 컨테이너 내부의 얕은 경로에서도 API 설정이 `.env`를 안전하게 탐색하도록 수정
- Dependabot PR 간 잠금 파일 충돌과 상호 의존 버전 불일치 해결

[출시 예정]: https://github.com/justinyoo/school-lunch/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/justinyoo/school-lunch/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/justinyoo/school-lunch/releases/tag/v0.1.0
