# 보안 모델: 로컬-우선 (local-first), 강제되는 보장

대표이사가 이 도구에 넣는 것은 회사의 **약점·은닉 리스크·임원 품행·핵심가치**다 — 회사가 가진 대부분의 데이터보다 민감하다. 2026년 환경은 이 우려가 정당함을 보여준다: 조사 조직의 **97%가 최근 1년 내 GenAI 관련 보안사고**를 겪었고(Capgemini), **삼성 직원의 기밀 코드 공개 AI 유출 → 사내 AI 금지** 사례가 반면교사다. "민감 데이터는 AI에 넣기 전 암호화하라"가 시장의 처방이다(Journey, *Make-or-Break CEO Trends of 2026*, Trend #4).

SelfDeploy의 답은 처방을 넘어서 **아키텍처**다: 민감 데이터가 애초에 기계를 떠나지 않는다.

## 보장 (약속이 아니라 강제)

| # | 보장 | 강제 수단 |
|---|---|---|
| 1 | **결정론 코어는 네트워크가 필요 없다** | `--offline` 플래그 = `security.offline_guard()` — 소켓 계층에서 모든 아웃바운드 차단. 코어 전체가 이 가드 아래서 실행됨을 테스트로 증명 (`tests/test_security.py`) |
| 2 | **유일한 아웃바운드 = 명시적 LLM 플래그** | `--llm` 계열만 네트워크 사용. `--offline`과 함께 쓰면 소켓에서 `NetworkBlockedError`로 즉시 실패 — 조용한 유출 불가 |
| 3 | **UI는 로컬 전용** | `serve`는 `127.0.0.1`에 하드코딩 바인딩. `--host` 옵션이 *의도적으로 없음* — 설정 실수로 외부 노출 불가 |
| 4 | **저장 데이터 암호화** | 포트폴리오(state)는 `SELFDEPLOY_PASSPHRASE` 환경변수 설정 시 scrypt KDF + Fernet(AES-CBC+HMAC)으로 at-rest 암호화. passphrase는 저장되지 않고 CLI 인자도 아님(셸 히스토리 유출 방지) |
| 5 | **단일 컨테이너 배포** | `Dockerfile` — 고객 인프라에서 직접 구동(self-deploy). 외부 서비스 의존 없음 |

## LLM 사용 시 데이터 최소화

`--llm` 경로는 필요한 최소만 보낸다: 욕구/요구 **문자열과 알려진 키 카탈로그**만. 리스크 포트폴리오·증거·조직도 전체를 보내지 않는다. 매핑 결과는 결정론 게이트(알려진 키 enum)로 걸러져 모델이 구조를 발명할 수 없다.

## 운영 권장

```bash
# 완전 오프라인 (기본 권장 — 모든 결정론 기능 동작)
selfdeploy --offline manage --vertical foodservice_franchise --select C4 --track pf.json

# 암호화 포트폴리오
export SELFDEPLOY_PASSPHRASE='긴-무작위-문구'
selfdeploy manage --select C4 --track pf.json   # 저장 시 자동 암호화

# 대표 UI (로컬 전용)
selfdeploy serve --evidence-file evidence.json --org-chart org.json
```

## 티어 (전략)

1. **셀프호스트(기본·무료 경로)** — 위 보장 전부. "직접 돌려봐, 아무것도 전화 안 함."
2. **매니지드(프리미엄)** — 테넌트별 격리 + 고객 관리 키 암호화 DB + VPC 배포. 편의를 원하되 로컬 운영이 부담인 고객용.
