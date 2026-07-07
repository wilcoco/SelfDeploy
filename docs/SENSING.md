# 말단 센싱 대안 카탈로그 (parked — 나중에 다시)

각 센싱 모달리티가 **무엇을 계측하고(function)**, 우리 IR의 **어떤 grounding 태그를 채우며(covers)**, 그 결과 신호가 **강(데이터→VERIFIED) / 약(주장→UNVERIFIED)** 중 무엇인지 정리. `selfdeploy/collectors.py`의 `DEFAULT_CATALOG`가 이 표의 구현 시작점.

## 상태 범례
- **구현됨**: `collectors.py`에 어댑터 있음
- **카탈로그**: 커버리지만 등록(플래너용), 어댑터 미구현
- **후보**: 확충 대상

## 표

| 수집기 | 모달리티 | 계측 기능 | covers (태그) | 강/약 | 상태 |
|---|---|---|---|---|---|
| predictive-maintenance | machine_sensor | 비침습 CT전류·서보토크·압력 + drift/dropout 검출 | `machine_state`, `downtime_log` | 강 | 구현됨 |
| ERP-tap | data_source | ERP 전표 조회(입출고·주문·생산실적) | `production_count`, `order_due`, `shipment_log`, `incoming_lot`, `finished_lot` | 강 | 구현됨 |
| MES-disposition | data_source | MES 불량 처리(리워크/폐기) 기록 | `disposition_log` | 강 | 카탈로그 |
| QC-scan-gate | manual_gate | 검사원 태블릿 합/불 스캔(작업 부산물로 기록) | `inspection_log` | 강(도입 후) | 카탈로그 |
| CCP-iot-logger | machine_sensor | HACCP 중요관리점 온도·시간 IoT 로거 | `ccp_log` | 강 | 카탈로그 |
| doc-extract(LLM) | document | 매뉴얼/작업표준서에서 정의 추출 | `defect_catalog`, `ccp_catalog` | 약 | 카탈로그 |

## 후보 (확충 대상)

| 모달리티 | 계측 기능 | 채울 수 있는 태그(예) | 비고 |
|---|---|---|---|
| 진동 센서 | 베어링/금형 마모, 이상 진동 스펙트럼 | `machine_state`, (신규)`tool_wear` | predictive-maintenance와 결합 |
| 음향(초음파) | 누설·마찰·캐비테이션 음향 시그니처 | `machine_state`, (신규)`leak_event` | 비침습 |
| 온도(열화상/서미스터) | 과열·냉각 이상, 공정 온도 | `machine_state`, `ccp_log` | 식품·사출 공통 |
| 비전 검사(카메라+모델) | 외관 불량 자동 판정 — **검사 기록마저 기계로** | `inspection_log`, `defect_catalog` | (나) 인간판단 은닉층을 기계로 뚫는 핵심 후보 |
| OPC-UA / Modbus 탭 | PLC 태그 직접 폴링(사이클·상태·설정값) | `machine_state`, `downtime_log`, (신규)`setpoint` | 프로토콜 어댑터 |
| 전력 서브미터 | 라인별 전력 프로파일 → 가동/생산 추정 | `machine_state`, `production_count`(추정) | 가상 센싱 |
| 바코드/RFID 게이트 | 로트 이동 스캔 → 배합/투입 연결 | `batch_link`, `incoming_lot`, `finished_lot` | **은닉 batch_link를 물리로 뚫는 후보** |

## 설계 원칙 (다시 볼 때 기준)

1. **강/약 등급을 정직하게.** 데이터 착지는 강(VERIFIED), 도입 계획·주장은 약(UNVERIFIED). 절대 섞지 않는다.
2. **기계로 못 닫는 칸을 숨기지 않는다.** 인간 판단(정지 사유 분류, 경계 불량 판정)과 머릿속 지식(배합 로트 연결)은 센서 커버리지에서 제외 → 플래너가 "인터뷰 게이트(사람)만"으로 표면화.
3. **비전 검사와 RFID 게이트가 특권적 후보.** 각각 `inspection_log`와 `batch_link`라는 *가장 깊은 은닉층*을 기계로 뚫을 수 있는 유이한 경로.
4. **as_of 필수.** 모든 데이터 신호는 타임스탬프를 실어 부식(freshness) 규칙과 연결.
