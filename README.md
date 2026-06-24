# SelfDeploy — 카카오톡 단톡방 실시간 AI 분석 시스템

회사 업무용 카카오톡 단톡방의 대화를 **실시간으로 수집 → 개인정보 마스킹 → 저장 → AI 이슈 분류 → RAG 검색/요약**하는 시스템입니다.

> ⚠️ **법적 고지 (반드시 먼저 읽어주세요)**
> - 카카오톡은 단톡방 메시지를 읽는 **공식 API를 제공하지 않습니다.** 이 시스템의 실시간 수집은 안드로이드 `NotificationListenerService`(알림 가로채기)에 의존하며, **카카오 이용약관 위반 소지**가 있습니다. 수집 전용 단말/계정으로만 운영하세요.
> - 회사 단톡방 대화에는 직원 개인정보가 포함됩니다. **참여자 전원의 사전 동의**와 **개인정보보호법(PIPA) 검토**가 선행되어야 합니다. (`docs/consent-template.md` 참고)

---

## 전체 구조

```
[안드로이드 수집 단말]                [FastAPI 서버]                     [AI]
카카오톡 알림 발생
 → NotificationListener가
   방이름/발신자/본문 추출
 → HTTPS POST  ───────────────▶  POST /ingest
                                  → 개인정보 마스킹 (masking.py)
                                  → DB 저장 (SQLite/Postgres)
                                  → 실시간 이슈 분류 (classifier.py, Claude) ──▶ 긴급 알림
                                  → RAG 인덱싱
                                 POST /ask  ──▶ RAG 검색 + Claude 요약 답변
```

## 디렉터리

```
server/                FastAPI 수집·분석 서버 (Python)
  app/
    main.py            엔드포인트 (/ingest, /ask, /issues, /health)
    config.py          환경설정
    db.py              DB 세션
    models.py          ORM 모델 (Message, IssueClassification)
    schemas.py         요청/응답 스키마
    masking.py         개인정보 마스킹 (전화/주민/계좌/카드/이메일/이름)
    classifier.py      Claude 기반 실시간 이슈 분류
    rag.py             키워드+시간 기반 검색 + Claude 요약 답변
    ingest.py          수집 파이프라인 (마스킹→저장→분류)
  requirements.txt
  .env.example
android-collector/     안드로이드 수집 앱 예제 (Kotlin)
docs/
  consent-template.md  개인정보 수집·이용 동의서 템플릿 (한글)
```

## 빠른 시작 (서버)

```bash
cd server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env 에 ANTHROPIC_API_KEY, INGEST_TOKEN 설정
uvicorn app.main:app --reload --port 8000
```

### 안드로이드 없이 테스트 (가짜 메시지 주입)

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $INGEST_TOKEN" \
  -d '{
    "room": "개발팀 운영방",
    "sender": "홍길동",
    "text": "결제 서버 장애 발생했습니다. 010-1234-5678로 연락주세요. 긴급!",
    "ts": "2026-06-24T10:00:00+09:00"
  }'
```

→ 응답에서 개인정보(`010-...`)가 마스킹되고, 이슈가 `장애/긴급`으로 분류됩니다.

### 질의응답 (RAG)

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "오늘 결제 관련 이슈 있었어?"}'
```

### 최근 긴급 이슈 조회

```bash
curl http://localhost:8000/issues?level=urgent
```

## 다음 단계

1. **서버 검증** — 위 curl로 파이프라인이 도는지 확인
2. **안드로이드 수집 앱 연결** — `android-collector/README.md` 참고
3. **운영 강화** — SQLite → Postgres(pgvector), 임베딩 기반 RAG, 긴급 알림 채널(메일/Slack/알림톡) 연동

자세한 운영 전환 가이드는 각 디렉터리의 README를 참고하세요.
