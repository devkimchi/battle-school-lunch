# 변경 이력

이 프로젝트의 주요 변경 사항을 이 문서에 기록합니다.

이 문서는 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따르며,
프로젝트 버전은 [유의적 버전](https://semver.org/lang/ko/spec/v2.0.0.html)을 기준으로 관리합니다.

## [출시 예정]

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

[출시 예정]: https://github.com/justinyoo/school-lunch/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/justinyoo/school-lunch/releases/tag/v0.1.0
