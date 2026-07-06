# SelfDeploy

**중소기업이 FDE(Forward Deployed Engineer)를 고용하지 않고도 FDE가 만들어주는 결과를 싸게 받게 한다.**

Palantir식 FDE는 SMB에게 비용 부담이 크다. SelfDeploy는 그 역할의 *정직한 핵심*만 도구화한다 — 대시보드를 만들어주는 게 아니라, **경영자의 요구를 실제로 측정 가능하게 만들 때 드러나는 은닉층(빨간 칸)을 표면화**한다.

## 핵심 명제

1. **당위 우선 (ought-first).** FDE는 *풍부한 데이터 위에* 온톨로지를 얹는다(descriptive). SMB엔 그 데이터가 없다. 우리는 반대로 — **경영자의 요구사항 자체를 당위로 삼아**, 그것이 *논리적으로 필연으로 요구하는* 하부구조를 세운다. "불량률을 원한다 ⟹ 불량 정의·검사 이벤트·처리 기록이 없으면 그 숫자는 거짓이다."
2. **탐침이지 스펙이 아니다.** 요구를 *구현하려는 시도*가 은닉층을 끌어올린다. 산출물은 대시보드가 아니라 **간극 지도(gap map)**.
3. **정직한 완료 정의.** KPI는 모든 필연 기록이 *실제 이벤트에 착지*할 때만 `VERIFIED`. 착지 못 하면 `RED`(빨간 칸). 이게 BI/OKR 도구와 갈리는 선.
4. **비결정성 구간 격리.** LLM(요구→KPI 매핑)은 한 스테이지에만, 그 뒤엔 결정론적 착지 게이트. 기본은 오프라인 결정론 동작.
5. **Kind-B 분할상각.** 업종별 *측정 문법*(entailment 템플릿)은 한 번 저작해 그 업종 전체에 재사용. 씨앗 = 사출/도장(CAMS).

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

```bash
python -m selfdeploy analyze \
  --vertical injection_molding \
  --requirement-file examples/requirement.txt \
  --evidence-file examples/injection_molding_evidence.json \
  --html out.html
```

예제 시나리오: 공장은 생산 수·설비 로그·출하 기록은 **데이터로** 갖고 있지만, **검사 기록·불량 처리 기록은 없다**(반장 머릿속/종이). 그래서 "불량률을 실시간으로 보고 싶다"는 요구는 예쁜 대시보드로 끝나는 게 아니라 — 불량률 KPI가 `RED`로 떨어지고, 정확히 그 은닉층(검사·처리 기록)이 빨간 칸으로 뜬다. 반면 가동중단은 데이터로 착지하되 사유 분류가 반장 판단(`JUDGMENT`)임이 드러난다.

## 테스트

```bash
python -m pytest -q
```

## 상태

v0 스캐폴드. 지금 있는 것: IR, 사출 시드 템플릿, 결정론 착지 게이트, 간극 지도. 다음: 증거 자동 수집(계측/ERP·MES 탭), Kind-A 추출 강제 함수(빨간 칸 → 강제 질문), 살아있는 SoT(신뢰 등급의 시간적 획득/상실).
