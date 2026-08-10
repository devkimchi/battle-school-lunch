# 변경 이력

이 프로젝트의 주요 변경 사항을 이 문서에 기록합니다.

이 문서는 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따르며,
프로젝트 버전은 [유의적 버전](https://semver.org/lang/ko/spec/v2.0.0.html)을 기준으로 관리합니다.

## [출시 예정]

## [0.4.0] - 2026-08-09

### 변경

- 프로젝트 디렉터리와 기본 Azure 리소스 그룹 이름을
  `battle-school-lunch`, `rg-battle-school-lunch`로 통일
  ([#72](https://github.com/devkimchi/battle-school-lunch/pull/72))
- GitHub Actions Azure 로그인 액션을 v3으로 업데이트
  ([#45](https://github.com/devkimchi/battle-school-lunch/pull/45))
- Web 런타임 의존성인 React DOM, TanStack Query, Lucide React,
  React Router를 업데이트
  ([#52](https://github.com/devkimchi/battle-school-lunch/pull/52),
  [#55](https://github.com/devkimchi/battle-school-lunch/pull/55),
  [#59](https://github.com/devkimchi/battle-school-lunch/pull/59),
  [#63](https://github.com/devkimchi/battle-school-lunch/pull/63),
  [#65](https://github.com/devkimchi/battle-school-lunch/pull/65))
- Web 및 E2E 개발·테스트 도구를 최신 호환 버전으로 업데이트
  ([#48](https://github.com/devkimchi/battle-school-lunch/pull/48),
  [#51](https://github.com/devkimchi/battle-school-lunch/pull/51),
  [#53](https://github.com/devkimchi/battle-school-lunch/pull/53),
  [#56](https://github.com/devkimchi/battle-school-lunch/pull/56),
  [#57](https://github.com/devkimchi/battle-school-lunch/pull/57),
  [#58](https://github.com/devkimchi/battle-school-lunch/pull/58),
  [#60](https://github.com/devkimchi/battle-school-lunch/pull/60),
  [#62](https://github.com/devkimchi/battle-school-lunch/pull/62),
  [#64](https://github.com/devkimchi/battle-school-lunch/pull/64),
  [#66](https://github.com/devkimchi/battle-school-lunch/pull/66),
  [#67](https://github.com/devkimchi/battle-school-lunch/pull/67),
  [#68](https://github.com/devkimchi/battle-school-lunch/pull/68),
  [#69](https://github.com/devkimchi/battle-school-lunch/pull/69),
  [#70](https://github.com/devkimchi/battle-school-lunch/pull/70))
- TypeScript 7 업데이트를 준비될 때까지 Dependabot 대상에서 제외
  ([#61](https://github.com/devkimchi/battle-school-lunch/pull/61))

### 수정

- Windows `az.cmd`에서 JMESPath와 JSON 인자가 잘못 해석되는 문제를 해결하고,
  GitHub OIDC 주체에 저장소 숫자 ID가 유지되도록 파이프라인 설정 스크립트를 수정
  ([#71](https://github.com/devkimchi/battle-school-lunch/pull/71))

### 포함된 Pull Request

- [#45 Bump azure/login from 2 to 3](https://github.com/devkimchi/battle-school-lunch/pull/45)
- [#48 Bump @types/node from 26.1.1 to 26.1.2 in /src/e2e](https://github.com/devkimchi/battle-school-lunch/pull/48)
- [#51 Bump typescript-eslint from 8.64.0 to 8.65.0 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/51)
- [#52 Bump react-dom from 19.2.7 to 19.2.8 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/52)
- [#53 Bump @testing-library/jest-dom from 6.9.1 to 7.0.0 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/53)
- [#55 Bump @tanstack/react-query from 5.101.2 to 5.101.4 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/55)
- [#56 Bump @playwright/test from 1.61.1 to 1.62.1 in /src/e2e](https://github.com/devkimchi/battle-school-lunch/pull/56)
- [#57 Bump jsdom from 29.1.1 to 30.0.1 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/57)
- [#58 Bump globals from 17.7.0 to 17.8.0 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/58)
- [#59 Bump lucide-react from 1.25.0 to 1.28.0 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/59)
- [#60 Bump @vitejs/plugin-react from 6.0.3 to 6.0.5 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/60)
- [#61 Defer TypeScript 7 updates](https://github.com/devkimchi/battle-school-lunch/pull/61)
- [#62 Bump @types/node from 26.1.1 to 26.1.2 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/62)
- [#63 Bump react-router-dom from 7.18.1 to 7.18.2 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/63)
- [#64 Bump eslint from 10.7.0 to 10.8.0 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/64)
- [#65 Bump lucide-react from 1.28.0 to 1.29.0 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/65)
- [#66 Bump typescript-eslint from 8.65.0 to 8.66.0 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/66)
- [#67 Bump @types/react from 19.2.17 to 19.2.18 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/67)
- [#68 Bump @types/react-dom from 19.2.3 to 19.2.4 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/68)
- [#69 Bump globals from 17.8.0 to 17.9.0 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/69)
- [#70 Bump vite from 8.1.5 to 8.2.0 in /src/web](https://github.com/devkimchi/battle-school-lunch/pull/70)
- [#71 Fix Azure CLI argument handling in pipeline scripts](https://github.com/devkimchi/battle-school-lunch/pull/71)
- [#72 Align battle school lunch resource names](https://github.com/devkimchi/battle-school-lunch/pull/72)

## [0.3.0] - 2026-07-27

### 추가

- OpenAPI 명세에서 생성한 MCP 서버와 학교 정보 및 급식 조회 도구 구현
  ([#33](https://github.com/justinyoo/school-lunch/pull/33))
- 급식 분석 채팅 UI, AG-UI 기반 에이전트 서비스와 동시 실행되는 전문 분석
  에이전트 추가
  ([#37](https://github.com/justinyoo/school-lunch/pull/37),
  [#39](https://github.com/justinyoo/school-lunch/pull/39))
- 급식 분석 채팅의 제품 요구사항과 평가 기준 문서화
  ([#38](https://github.com/justinyoo/school-lunch/pull/38))
- 에이전트 워크플로 실패 원인을 확인할 수 있는 진단 로그 추가
  ([#41](https://github.com/justinyoo/school-lunch/pull/41))

### 변경

- 저장소 및 각 앱 문서를 현재 Aspire 기반 실행·배포 구조에 맞게 개편하고,
  통합 테스트 스크립트와 아키텍처 다이어그램 추가
  ([#44](https://github.com/justinyoo/school-lunch/pull/44))
- Azure 배포 작업을 저장소 변수로 제어하도록 변경
  ([#32](https://github.com/justinyoo/school-lunch/pull/32))

### 수정

- CI에서 Aspire 모듈 복원 후 AppHost TypeScript 빌드를 수행하도록 수정
  ([#34](https://github.com/justinyoo/school-lunch/pull/34))
- GitHub Actions의 Azure OIDC 주체 구성을 브랜치·PR 및 숫자 ID 기반으로
  정정
  ([#35](https://github.com/justinyoo/school-lunch/pull/35),
  [#36](https://github.com/justinyoo/school-lunch/pull/36))
- End-to-end GitHub Actions 작업의 실패를 수정
  ([#40](https://github.com/justinyoo/school-lunch/pull/40))
- 에이전트 ID에 Foundry 프로젝트 권한을 부여하고 역할 할당 프로비저닝을
  안정화
  ([#42](https://github.com/justinyoo/school-lunch/pull/42),
  [#43](https://github.com/justinyoo/school-lunch/pull/43))

### 제거

- 더 이상 사용하지 않는 Docker Compose 실행 경로와 관련 설정 제거
  ([#44](https://github.com/justinyoo/school-lunch/pull/44))

### 포함된 Pull Request

- [#32 Gate Azure deployment job with repository variable](https://github.com/justinyoo/school-lunch/pull/32)
- [#33 Implement OpenAPI-based MCP server](https://github.com/justinyoo/school-lunch/pull/33)
- [#34 Fix AppHost TypeScript CI build by restoring Aspire modules before compile](https://github.com/justinyoo/school-lunch/pull/34)
- [#35 Fix Azure OIDC federation subjects](https://github.com/justinyoo/school-lunch/pull/35)
- [#36 Use numeric ID-based OIDC subject](https://github.com/justinyoo/school-lunch/pull/36)
- [#37 Add the school meal analysis chat tab](https://github.com/justinyoo/school-lunch/pull/37)
- [#38 Document school meal analysis chat requirements](https://github.com/justinyoo/school-lunch/pull/38)
- [#39 Add concurrent multi-agent meal analysis](https://github.com/justinyoo/school-lunch/pull/39)
- [#40 Fix the failing End-to-end GitHub Actions job](https://github.com/justinyoo/school-lunch/pull/40)
- [#41 Log agent workflow failures](https://github.com/justinyoo/school-lunch/pull/41)
- [#42 Grant agent Foundry project access](https://github.com/justinyoo/school-lunch/pull/42)
- [#43 Fix Foundry role assignment provisioning](https://github.com/justinyoo/school-lunch/pull/43)
- [#44 Refresh application documentation](https://github.com/justinyoo/school-lunch/pull/44)

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

[출시 예정]: https://github.com/devkimchi/battle-school-lunch/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/devkimchi/battle-school-lunch/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/devkimchi/battle-school-lunch/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/devkimchi/battle-school-lunch/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/devkimchi/battle-school-lunch/releases/tag/v0.1.0
