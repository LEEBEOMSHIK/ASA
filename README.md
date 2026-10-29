# AI Shorts Studio (ASA)

프롬프트로 쇼츠를 기획하고 사람이 검토하여 완성하는 개인 제작 도구. 이후 SaaS로 확장한다.

**현재 단계: 에이전트·도구 등록 구현. 자동화 실행과 영상 생성 MVP는 후속 단계다.**

## 확정 방향

- Next.js / FastAPI / PostgreSQL / Python 워커.
- LangGraph로 제작 흐름·승인, LangChain으로 외부 AI API 연결.
- 개발은 모든 앱 서비스를 로컬에서 직접 실행. AI 추론은 외부 API.
- Docker는 운영 배포용. AI 키는 서버에서만 보관.

## 시작

Node.js 22+, Python 3.13 x64, uv와 로컬 PostgreSQL을 준비한다.

```powershell
Set-Location C:/projects/ASA
./scripts/setup.ps1
# .env와 로컬 PostgreSQL 설정 후, 별도 터미널에서 각각 실행
./scripts/run.ps1 web
./scripts/run.ps1 api
# 테스트·타입·빌드 (유료 AI 호출 없음)
./scripts/check.ps1
```

웹 http://127.0.0.1:3000 (사용 중이면 3001) / API 문서 http://127.0.0.1:8127/docs.
상세 DB 설정·워커 명령은 [로컬 실행 가이드](docs/local-development.md)를 따른다.

## 구현됨 / 다음 단계

구현: 초기 안내 UI와 토큰·공통 컴포넌트, health API, 대본 생성→승인 LangGraph,
LangChain 공급자 어댑터, PostgreSQL 체크포인트 CLI, 로컬 스크립트, 운영 Docker 설정.

추가 구현: 로컬 owner 세션·CSRF, workspace별 에이전트 초안·검증·버전 확정·도구 등록 UI.
[에이전트 등록 사용법](docs/runbooks/agent-registry.md)을 참고한다.

미구현: SaaS 인증, 블록 연결 빌더·도구 자동 호출·실행 내역, 작업 큐, 웹 제작 API 연결, 비용 원장,
이미지·음성 생성, FFmpeg 렌더링, 자동 게시·결제. CLI의 approved는 영상 완료가 아니다.
실제 모델 호출·DB 지속성·Docker 운영 여부는 [검증 기록](docs/verification.md)을 확인한다.

## 문서

- [작업 보드](WORKBOARD.md) / [보드 템플릿](docs/templates/WORKBOARD.md)
- [아키텍처](docs/architecture.md) / [디자인 시스템](docs/design-system.md)
- [에이전트·자동화 빌더 설계](docs/agent-automation-design.md) / [구현 계획](docs/superpowers/plans/2026-10-26-agent-automation.md)
- [로컬 실행](docs/local-development.md) / [운영 배포](docs/production.md)
- [초기 구현 계획](docs/superpowers/plans/2026-10-26-foundation.md)
