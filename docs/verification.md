# 초기 구성 검증 기록

일자: 2026-10-26 (Asia/Seoul)
저장소: C:/projects/ASA / origin https://github.com/LEEBEOMSHIK/ASA.git
범위: 초기 기반. 전체 쇼츠 제작 MVP 완료가 아님.

## 통과한 검사

- Python 3.13.15 x64 전용 .venv, Node.js 24.18.0. 의존성은 uv.lock / package-lock.json으로 고정.
- 전체 backend pytest: 11 passed. 승인·거절·중단·재개 시 중복 생성 방지, 잘못된 입력·승인,
  DB 누락/실패 상태, 공급자 설정 누락, 외부 추적 차단, 실패 전 run ID 출력 포함.
- ruff check: All checks passed.
- mypy: Success, 7 source files.
- TypeScript typecheck 통과, Next.js 16.4.3 production build 통과.
- 로컬 API 프로세스를 임시 포트에서 실제 시작: live HTTP 200, DB 미설정 ready HTTP 503.
  검증 후 해당 임시 API 프로세스만 종료.
- PowerShell setup/run/check 스크립트 문법 검사 통과. check.ps1 전체 실행 통과.
- 운영 Compose YAML 파싱 및 db/api/web/worker 정의 확인. Docker 자체 검증과 구분.
- 브라우저에서 http://127.0.0.1:3001 초기 화면 렌더링, 입력 label·설명 연결,
  제작 버튼 비활성 상태, Tab 키의 본문 바로가기 포커스를 확인.
  현재 시스템의 dark 테마와 데스크톱 화면 기준. 모든 뷰포트·테마·스크린리더를 검증한 것은 아님.
- 독립 읽기 전용 리뷰: x64 런타임 선택, 외부 추적 차단, run ID 조기 출력 3건 수정.
  회귀 테스트 실패 확인 후 통과, 수정 재리뷰에서 남은 중요 결함 없음.

## 제한과 미검증

- 실제 AI API 호출 0회. 공급자 키·모델 미설정. 지원 모델·출력 품질·과금·실제 timeout 미검증.
- PostgreSQL 실행 파일은 설치되어 있지만 ASA 전용 DB/접속 정보는 준비하지 않음.
  실제 체크포인트 테이블 생성, 프로세스 재시작 후 지속성, 승인 동시성은 미검증.
- worker check 결과: database_configured=false, ai_model_configured=false,
  ai_key_configured=false, ffmpeg_available=false. exit 1은 준비되지 않은 상태를 알리는 정상 결과.
- FFmpeg는 PATH에서 발견하지 못했으며 실제 렌더링을 수행하지 않음.
- Docker 명령을 찾지 못했으므로 이미지 build/compose config/컨테이너 실행/복원은 미검증.
- 운영 전 DB 관리자와 앱 역할 분리, 인증, TLS reverse proxy, 큐·비용 한도,
  tenant 격리·백업 복원 수용 검증이 필요하다. 현재 compose DB 사용자는 초기 부트스트랩용이다.
- 상시 큐 워커·앱 데이터 스키마·웹 제작 API·영상 합성·게시·결제는 후속 구현.
- Windows ARM64 기본 Python으로 최초 설치는 psycopg wheel 부재로 실패.
  기존 x64 Python으로 해결했고 setup에도 x64 선택을 명시했다.
- 기본 웹 포트 3000은 다른 프로세스가 사용하여 Next.js가 3001을 선택.
  기존 프로세스는 변경하지 않음. 로컬 미리보기용 웹 서버만 실행 상태로 둠.
- 커밋·push·공개 배포 없음. 프로젝트 파일은 아직 Git untracked 상태.

## ASA-009 등록 기능 (2026-10-26)

실제 PostgreSQL 포함 pytest 26개, ruff/mypy(17개 소스), 웹 typecheck/build 통과.
브라우저 로그인·초안 저장·검증·버전 확정·도구 목록·로그아웃 변경 보호 확인.
상세: [검증 기록](worklogs/2026-10-26-agent-registry.md). 실제 AI 호출·Docker·자동화 실행은 미검증.

## ASA-014 관리자 로그인 (2026-10-26)

별도 /login과 개발 테스트 로그인: 실제 DB 포함 pytest29개, ruff/mypy, 웹 typecheck/build 통과.
브라우저 로그인·관리 화면 복귀·로그아웃 확인. [기록](worklogs/2026-10-26-admin-login.md).



## ASA-033 자동화 실행·예약

pytest50개/ruff/mypy24소스/웹typecheck/build 통과. 실제 로컬도구 실행·승인·이력·매일예약 UI 확인. 외부 AI는 모의 호출만 검증. [상세](worklogs/2026-10-26-automation-runtime.md).
