# 운영 Docker 구성

현재는 배포 기반 설정이다. Docker 이미지 빌드와 운영 복원은 별도 검증이 필요하다.
운영 설정은 ASA_ENVIRONMENT=production, ASA_DEV_LOGIN_ENABLED=false로 개발 테스트 로그인을 차단한다.
인증·tenant 격리·작업 큐·비용 제어가 없는 초기 버전을 인터넷에 공개하지 않는다.

## 준비 및 실행

루트에서 .env.production.example을 .env.production으로 복사하고 비밀값을 설정한다.
POSTGRES_PASSWORD는 URL에 안전한 긴 임의 hex 문자열을 사용한다. AI 키는 worker에만 전달한다.
ASA_OWNER_ACCESS_KEY에는 무작위 owner 접근 키를, ASA_ALLOWED_ORIGINS에는 실제 HTTPS 웹 origin의 JSON 배열을 지정한다.
운영 세션 쿠키는 Secure이므로 TLS reverse proxy가 필요하다. owner 세션은 SaaS 인증을 대체하지 않는다.
웹의 API 목적지는 이미지 빌드 시 ASA_API_ORIGIN으로 정해지며 기본값은 http://api:8000이다.

```sh
docker compose --env-file .env.production -f deploy/compose.production.yml config --quiet
docker compose --env-file .env.production -f deploy/compose.production.yml build
docker compose --env-file .env.production -f deploy/compose.production.yml up -d db api web
docker compose --env-file .env.production -f deploy/compose.production.yml run --rm api python -m asa.registry.init
docker compose --env-file .env.production -f deploy/compose.production.yml run --rm worker init-checkpoints
```

worker는 operations 프로파일의 수동 명령 컨테이너다. 큐 서비스로 오인하지 않는다.
draft 명령을 실행할 때만 명시적인 --allow-paid-call을 붙인다.
이미지는 비루트 사용자로 실행한다. DB 포트는 외부에 노출하지 않는다.
웹/API는 loopback에만 바인딩하며 실제 서버에서는 TLS reverse proxy와 인증을 추가한다.
이미지에는 .env·캐시·가상환경이 포함되지 않는다. 릴리스 시 이미지 digest도 고정한다.

## 데이터와 장애 대응

PostgreSQL 18 볼륨은 /var/lib/postgresql, 향후 자산 볼륨은 /data/assets다.
등록 DB 스키마와 checkpointer 초기화는 위 명령으로 명시 실행한다. 후속 실행 원장 마이그레이션은 아직 없다.
백업은 DB pg_dump와 파일 자산의 동일 버전 스냅샷을 쌍으로 보관한다.
배포 전 별도 복원 DB에서 run/checkpoint/asset 참조 일치와 재개 동작을 검증한다.
현재 실제 복원 검증은 미완료다. docker compose down -v는 데이터 삭제이므로 기본 절차에 포함하지 않는다.
장애 시 새 유료 호출을 멈추고 공급자 요청 ID·사용량·저장 상태를 확인한다.
API 컨테이너 health는 DB 연결까지만 검증하며 전체 제작 성공을 보장하지 않는다.

현재 Compose의 POSTGRES_USER는 초기 부트스트랩 관리자다. 실제 운영 전 별도의 비-superuser 앱 역할을 만들고 API/worker 연결을 그 역할로 변경해야 한다.
