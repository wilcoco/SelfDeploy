# SelfDeploy

**중소기업이 FDE(Forward Deployed Engineer)를 고용하지 않고도 FDE가 만들어주는 결과를 싸게 받게 한다.**

Palantir식 FDE는 SMB에게 비용 부담이 크다. SelfDeploy는 그 역할의 *정직한 핵심*만 도구화한다 — 대시보드를 만들어주는 게 아니라, **경영자의 요구를 실제로 측정 가능하게 만들 때 드러나는 은닉층(빨간 칸)을 표면화**한다.

## 핵심 명제

1. **당위 우선 (ought-first).** FDE는 *풍부한 데이터 위에* 온톨로지를 얹는다(descriptive). SMB엔 그 데이터가 없다. 우리는 반대로 — **경영자의 요구사항 자체를 당위로 삼아**, 그것이 *논리적으로 필연으로 요구하는* 하부구조를 세운다. "불량률을 원한다 ⟹ 불량 정의·검사 이벤트·처리 기록이 없으면 그 숫자는 거짓이다."
2. **탐침이지 스펙이 아니다.** 요구를 *구현하려는 시도*가 은닉층을 끌어올린다. 산출물은 대시보드가 아니라 **간극 지도(gap map)**.
3. **정직한 완료 정의.** KPI는 모든 필연 기록이 *실제 이벤트에 착지*할 때만 `VERIFIED`. 착지 못 하면 `RED`(빨간 칸). 이게 BI/OKR 도구와 갈리는 선.
4. **비결정성 구간 격리.** LLM(요구→KPI 매핑)은 한 스테이지에만, 그 뒤엔 결정론적 착지 게이트. 기본은 오프라인 결정론 동작.
5. **Kind-B 분할상각.** 업종별 *측정 문법*(entailment 템플릿)은 한 번 저작해 그 업종 전체에 재사용. 씨앗 = 사출/도장(CAMS). 둘째 업종(식품가공)이 `templates.py`만 바뀌고 나머지 엔진 전부를 그대로 재사용함을 실증(`--vertical food_manufacturing`).

> 주: 요구→KPI 오프라인 매칭은 키워드 substring이라 한국어에서 취약함(예: `수율`⊂`준수율`). 이건 *결정론 폴백*이고, 견고한 경로는 `--llm`(결정론 게이트가 감쌈).

## 구조

```
경영자 요구           →  decompose  →  당위 그래프(IR)   →  ground  →  등급 매겨진 그래프  →  report
(apex output pin)       (KPI 매핑)     (컨트랙트 그래프)     (결정론 게이트)  RED/UNVERIFIED/…      (간극 지도)
```

- `selfdeploy/ir.py` — 컨트랙트 그래프 IR. provenance(출처)·grade(신뢰등급)가 1급 시민.
- `selfdeploy/templates.py` — Kind-B 측정 문법. 사출 업종 시드(불량률/가동중단/납기).
- `selfdeploy/decompose.py` — 요구 → 당위 하부구조. 매핑 안 되는 요구는 조용히 버리지 않고 `RED` unknown으로.
- `selfdeploy/grounding.py` — 결정론적 착지 게이트 + `red_density`(생사 지표).
- `selfdeploy/report.py` — 텍스트/HTML 간극 지도.

## 등급 (grade)

| 기호 | 등급 | 의미 |
|---|---|---|
| ✓ | `VERIFIED` | 회사 데이터(로그)로 착지 — 검증됨 |
| ? | `UNVERIFIED` | 주장/템플릿 추정만 — 미검증 (고무도장 위험) |
| ✗ | `RED` | 착지 불가/누락 — **숙제(빨간 칸)** |
| ◐ | `JUDGMENT` | 담당자 있는 사람 판단 — 억지로 닫지 않는 합법적 종착점 |

## 실행

**1) 간극 지도 — 요구를 착지시켜 은닉층을 빨간 칸으로:**
```bash
python -m selfdeploy analyze \
  --requirement-file examples/requirement.txt \
  --evidence-file examples/injection_molding_evidence.json \
  --html out.html
# --llm 을 붙이면 요구→KPI 매핑을 Claude(opus-4-8)가 함(결정론 게이트로 감쌈). 없으면 오프라인 키워드 매핑.
```

예제 시나리오: 공장은 생산 수·설비 로그·출하 기록은 **데이터로** 갖고 있지만, **검사 기록·불량 처리 기록은 없다**(반장 머릿속/종이). 그래서 "불량률을 실시간으로 보고 싶다"는 요구는 예쁜 대시보드로 끝나는 게 아니라 — 불량률 KPI가 `RED`로 떨어지고, 정확히 그 은닉층(검사·처리 기록)이 빨간 칸으로 뜬다. 반면 가동중단은 데이터로 착지하되 사유 분류가 반장 판단(`JUDGMENT`)임이 드러난다.

**2) 강제 질문 — 빨간 칸을 타입 미닫힘에서 자동 생성한 질문으로:**
```bash
python -m selfdeploy questions \
  --requirement-file examples/requirement.txt \
  --evidence-file examples/injection_molding_evidence.json
```
"승인"이 아니라 "빨간 칸 채우기". 질문은 LLM 직감이 아니라 `missing_record / claim_only / unowned_judgment / unknown_requirement` 분류에서 결정론적으로 나온다.

**3) 빨간 칸 채우기 — 답변→재착지 살아있는 루프:**
```bash
python -m selfdeploy interview \
  --requirement-file examples/requirement.txt \
  --evidence-file examples/injection_molding_evidence.json \
  --answers-file examples/answers.json
```
담당자가 빨간 칸을 채우면 red 밀도가 떨어지고, KPI가 `RED`→`UNVERIFIED`로(약속했으나 데이터 미확인, 정직하게) 이동한다.

**4) 말단 센싱 대안 — 빨간 칸을 어떤 계측으로 닫을 수 있나:**
```bash
python -m selfdeploy plan-sensing \
  --requirement-file examples/requirement.txt \
  --evidence-file examples/injection_molding_evidence.json
```
빨간 칸을 **센싱으로 닫히는 칸**(후보 수집기 + 강/약 등급)과 **센싱 대안 없는 칸**(은닉 판단/머릿속 → 인터뷰 게이트)으로 갈라준다. 간극 지도가 곧 *계측 조달 계획*이 됨.

증거 자동 수집(수집기 가동 → 신호 병합 → 재착지):
```bash
python -m selfdeploy collect \
  --requirement-file examples/requirement.txt \
  --evidence-file examples/injection_molding_evidence.json \
  --pm-readings examples/pm_readings.json   # predictive-maintenance /ingest 스타일 feed
```
`predictive-maintenance`(비침습 CT전류/토크/압력 + drift/dropout 검출)를 어댑터로 흡수 — 기계 관측 태그(`machine_state`, `downtime_log`)를 데이터 신호(as_of 포함)로. 단, 검사·처리 기록 같은 **인간 판단 은닉층은 기계로 못 닫는다**는 걸 정직하게 드러냄.

**5) 이중 속도 — 변화가 상시입력인지 재설계인지 타입으로 판정:**
```bash
# 트랩 케이스: 검사 데이터처럼 보이지만 새 처리경로를 실은 신호 → 승급 판정
echo '{"id":"QC.new","kind":"data","tags":["inspection_log","repaint_route"]}' \
  | python -m selfdeploy classify --requirement-file examples/requirement.txt --signal-file /dev/stdin
```
`상시 입력(가벼운 게이트)` / `승급 판정(사람 결정)` / `재설계(무거운 게이트)` 세 갈래. 빠른 맥박과 느린 맥박 사이를 타입 닫힘이 지킨다.

## 테스트

```bash
python -m pytest -q
```

## 모듈

- `ir.py` — 컨트랙트 그래프 IR (provenance/grade 1급)
- `templates.py` — Kind-B 측정 문법 (사출 시드)
- `decompose.py` — 요구 → 당위 하부구조
- `grounding.py` — 결정론 착지 게이트 + red 밀도
- `interview.py` — 강제 질문 → 답변 → 재착지 (Kind-A 추출)
- `evolve.py` — 이중 속도 판정 (상시입력/승급/재설계)
- `collectors.py` — 말단 센싱 수집기 + 카탈로그 + 갭→센싱 플래너 (predictive-maintenance 어댑터)
- `llm.py` — 선택적 Claude 요구→KPI 매퍼 (격리된 비결정성 단계)
- `report.py` — 텍스트/HTML 간극 지도
- `cli.py` — analyze / questions / interview / classify / plan-sensing / collect

## 상태

v0 스캐폴드, 44 테스트 통과. 있는 것: IR, 사출+식품 시드 템플릿, 결정론 착지 게이트, 간극 지도, Kind-A 강제 질문 루프, 이중 속도 판정, 시간적 부식, 선택적 LLM 매핑, 말단 센싱 수집기 + 갭→센싱 플래너(predictive-maintenance 어댑터).

다음: 수집기 확충(진동/음향/온도 IoT, 비전 검사, OPC-UA/Modbus 탭), HTML 간극 지도에 센싱 계획 렌더링, 라이브 predictive-maintenance 서버 연동(REST poll), 셋째 업종.
