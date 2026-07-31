# 공·방 에이전트 방법론

## 연구 명제

예선 보고서의 핵심은 특정 공격 규칙이 아니라 관측을 계층화하고, 정상 상태와의 차이를 predicate로 변환하며, 인과 체인을 구성해 공격 탐색과 방어 대응을 오케스트레이션하는 절차다. 같은 코어를 CAGE Challenge 4의 온라인 방어와 DARPA Transparent Computing의 오프라인 공격 체인 발굴에 적용한다.

벤치마크 이름, 정답 라벨, 고정 호스트 이름과 action index는 공통 코어에 넣지 않는다. 벤치마크 어댑터는 관측 형식과 허용 행동만 변환한다.

## 공통 증거 모델

모든 관측을 다음 필드의 증거로 정규화한다.

| 필드 | 의미 |
|---|---|
| timestamp | 관측 시각 또는 순서 |
| layer | 동적으로 발견한 계층 |
| source | 관측을 생성한 수집기 |
| subject | 행동 주체 |
| relation | 관측된 동작이나 관계 |
| object | 대상 자산 |
| context | 세션, 구역, 프로세스 등 연결 정보 |
| confidence | 관측 신뢰도 |
| provenance | 출처와 신뢰 경계 |

관측할 수 없는 필드는 정상으로 가정하지 않고 `unknown`으로 유지한다. 외부 payload가 주장한 신뢰 상태는 사용하지 않고 인증된 어댑터만 신뢰 경계를 지정한다.

정규화된 증거는 다음 다섯 단계의 predicate로 변환한다.

1. `ingress`: 접근점과 통신 경로 확보
2. `trust_break`: 신원, 권한, 정책, 무결성 관계 손상
3. `lifecycle`: 실행, 세션 생성, 권한 상승, 지속성
4. `mission_effect`: 서비스나 임무 상태에 실제 영향 발생
5. `response`: 탐지, 허니팟, 격리, 복구 행동 발생

## 정상 상태와 계층 탐색

정상 학습 구간에서 세 종류의 기준을 만든다.

- 빈도 기준: 정상 개체와 관계의 출현 범위
- trace 기준: 정상적인 시간 순서와 동시 발생 관계
- automaton 기준: 허용되는 상태 전이와 금지된 전이

계층은 데이터셋 이름이나 사전 고정 type ID로 정하지 않는다. 정상 그래프에서 개체 종류별 입·출력 관계 분포, 시간적 선후관계, 공유 context를 이용해 역할을 찾고 이 역할 사이의 전이를 계층으로 사용한다. 공격 라벨은 계층 발견과 정상 기준 학습에 사용하지 않는다.

TC의 원시 provenance 이벤트는 곧바로 공격 predicate로 간주하지 않는다. 정상 profile의 임계값을 넘은 이벤트를 seed로 삼고, 같은 프로세스의 18초 세션에서 주변 전이를 단계별 predicate로 집계한다. 이 과정은 정답 라벨이나 파일명 규칙을 사용하지 않으며, seed가 없는 정상 세션은 후보에 넣지 않는다.

## 인과 체인

predicate 사이의 연결 점수는 예선 보고서의 네 근거를 따른다.

- 시간 근접성: 0.30
- 공유 context의 Jaccard 유사도: 0.30
- 공격 단계의 순방향 진행: 0.25
- 임무 수준 영향과의 연결: 0.15

관측할 수 없는 항목을 0점으로 처리하지 않고 관측 가능한 항목의 가중치를 다시 정규화한다. 연결 임계값은 0.58, 최대 체인 길이는 5, 시간 창은 18초다. 일반 체인은 predicate 세 개와 고유 단계 세 개 이상으로 구성하고 `mission_effect` 또는 `response`에서 끝나야 한다.

체인 점수는 평균 연결 강도, 평균 신뢰도, 평균 심각도, 단계 다양성, 교차 계층 여부, 임무 영향 여부를 함께 사용한다. 특정 프로토콜이나 호스트 이름에 대한 보너스는 사용하지 않는다.

체인 점수를 개별 노드의 이상 점수로 그대로 대체하지 않는다. 노드별 체인 기여는 해당 predicate의 confidence를 곱해 실제 증거 강도로 제한하고, 체인 attribution과 node ranking 지표를 별도로 보고한다.

## 공격 에이전트

공격 에이전트는 무조건 공격을 실행하는 모델이 아니라 교차 계층 공격 가설 생성 및 검증 엔진이다.

처리 순서는 다음과 같다.

1. 정상 profile과 automaton 학습
2. 관측을 predicate로 변환
3. `ingress` 또는 `trust_break`에서 시작하는 체인 후보 생성
4. baseline, 단일 개념, pairwise, 전체 결합, negative control, 고위험 조합의 여섯 실험군 계획
5. 실제 행동 공간에서 가능한 전이인지 제약 검증
6. 검증된 축만 실행하거나 로그에서 검증
7. mission oracle과 체인 변화가 함께 확인된 경우에만 성공 기록
8. 실패 원인을 coverage gap으로 기록하고 frontier 탐색에 반영

오케스트레이터는 다음 역할을 순서대로 호출한다.

- Profiler
- Predicate Miner
- Chain Builder
- Experiment Planner
- Constraint Validator
- Campaign Scheduler
- Frontier Explorer

CAGE에서는 탐색, 서비스 확인, 침투, 권한 상승, 횡적 이동, Impact를 predicate로 변환할 수 있다. DARPA TC에서는 provenance 노드와 간선을 predicate로 변환하고 조사 우선순위와 공격 체인을 출력한다. 본 연구의 주 공격 평가는 TC에서 수행한다.

## 방어 에이전트

방어 에이전트는 지각, 탐지, 판단, 대응, 복구의 다섯 단계로 동작한다.

- 실제 관측된 증거만 사용한다.
- 약한 단일 이상은 즉시 강한 차단으로 올리지 않는다.
- 서로 독립적인 계층의 증거가 연결될수록 위험도를 높인다.
- 중요 자산일수록 강한 대응에 더 많은 증거를 요구한다.
- 감시, 허니팟, 분석, 제거, 임시 격리, 복구 순으로 가역적인 대응을 우선한다.
- ACK가 아니라 대응 전후 상태 변화로 성공을 판정한다.

사전 정의된 규칙의 위험도는 다음 식을 사용한다.

`risk = 0.35 × confidence + 0.25 × severity + 0.25 × correlation + 0.15 × target_criticality`

정상 범위 이탈은 다음 식을 사용한다.

`risk = 0.50 × adjusted_anomaly_magnitude + 0.30 × correlation + 0.20 × target_criticality`

기본 대응 구간은 다음과 같다.

| 위험도 | 기본 대응 |
|---|---|
| 0.00–0.49 | monitor |
| 0.50–0.69 | honeypot |
| 0.70–0.84 | temporary isolate 검토 |
| 0.85–1.00 | block 또는 restore 검토 |

기본 방법의 허니팟은 초기 일괄 배치가 아니다. 현재 체인의 다음 전이가 예상되는 호스트나 서비스에 동적으로 배치하고, 접촉을 별도 predicate로 다시 입력한다. CAGE 어댑터는 제한된 관측에서 현재 대상과 같은 구역의 정상 호스트를 다음 전이 후보로 사용한다. episode 중 적대 호스트 전이 빈도를 학습하는 확장도 평가했지만 개발 reward가 악화돼 기본 방법에서는 비활성화했다. 강화 방법은 위협이 없을 때 관측 역할별 coverage 공백을 한 번에 하나씩 채우고, 위협이 생기면 다시 체인 기반 동적 배치로 전환한다. 강한 대응은 독립 증거, 가역성, 중요 자산 영향, 최근 판단 이력, MetaMonitor 상태를 확인한 뒤 실행한다.

정상 기준은 같은 배치에서 위험도 0.5 이상의 판단이 없고, 같은 대상에서 이상이 없으며, 인증·통신 탐지기가 정상이고, 장기 위험 신호가 없을 때만 갱신한다. 강한 보호 상태는 약한 후속 신호 하나만으로 낮추지 않는다.

## 강화 오케스트레이션

방어 v11은 시간적 belief와 정적 행동 효용을 도입했지만 부분 Remove가 교차 계층 공격 범위를 덮지 못했다. v12는 행동의 범위가 증거의 범위를 포함해야 한다는 제약을 추가한다.

- 한 계층 근거만 있으면 Analyse 또는 honeypot으로 정보를 더 모은다.
- 두 계층 이상이 연결되면 부분 조치가 전체 체인을 끊는지 검사한다.
- process와 connection이 함께 확인되거나 mission effect가 형성되면 부분 Remove보다 정상 상태 Restore를 우선한다.
- 효과 확인이 끝나기 전에는 같은 대상에 강한 조치를 반복하지 않는다.
- 위협이 없을 때만 deception coverage를 순차적으로 확장한다.

공격 v5는 체인 존재와 node attribution을 분리한다. 긴 process session의 모든 endpoint를 공격 node로 올리지 않고, predicate target, 두 단계 이상을 연결하는 반복 connector, 세션 내 `median + 3 × MAD`를 넘는 endpoint 기여 outlier만 보고한다. 체인 선택은 원래 품질에서 이미 선택한 체인과의 최대 footprint Jaccard 유사도에 0.25를 곱한 값을 빼 중복 조사를 줄인다. path가 결측이면 `unknown`이라는 관측 상태를 만들지 않고 남은 구조·trace 항목으로 가중치를 재분배한다.

공격 v6은 단일 단계 leaf와 모든 predicate target을 제외하고 두 단계 이상에서 반복되는 endpoint만 causal cut set으로 보고한다. 공격 v7은 이를 더 엄격하게 만들어 체인의 모든 predicate endpoint 교집합만 최소 인과 핵심으로 보고하며, 교집합이 없으면 local anomaly가 가장 큰 target 하나만 남긴다. v7의 결측 path는 버리지 않고 relation별 path 존재 확률로 점수화한다. 세 변형은 CADETS에서 사전 순서대로 평가하되 통과한 버전만 THEIA로 이전하며, 실패한 버전을 보고 파라미터를 다시 조정하지 않는다.

## 공식 detector seed와 체인 결합

공격 조사 head는 detector와 체인 탐색을 분리한다. 공식 PIDSMaker Velox의 node anomaly score를 고정된 seed 인터페이스로 받고, validation edge loss의 정확한 최댓값보다 큰 node만 seed로 선택한다. Detector의 학습·feature·score·분할은 수정하지 않는다.

동결된 trace head는 정상 telemetry만으로 profile과 threshold를 만들고 test day별 체인을 구성한다. 하나 이상의 공식 seed를 포함한 체인만 확장하며, 그 체인 predicate에 실제 endpoint로 등장하고 공식 score universe에도 존재하는 node만 조사 후보에 추가한다. 확장 후보의 support는 다음 식으로 기록하지만 후보 포함 여부를 test label이나 support threshold로 다시 조정하지 않는다.

`support(node) = max(chain_score × predicate_confidence × official_node_score)`

이 결합은 detector score를 다시 학습하거나 ranking을 바꾸지 않는다. 비교군은 hybrid가 보고한 node 수와 정확히 같은 수의 공식 score 상위 node이며, score 동점은 라벨을 보지 않고 UUID 내림차순으로 고정한다. Metric 프로세스는 label을 연 뒤 cutoff 동점의 가능한 최소·최대 TP도 함께 계산한다.

Score manifest 생성 프로세스에는 공식 산출물의 `nodes`와 `pred_scores`만 전달한다. `y_truth`, attack metadata, fine UUID label은 별도 평가 프로세스에서만 읽는다. 따라서 체인 선택, 확장 범위, 보고 예산에는 test 정답이 들어가지 않는다.

## FlowSub 예산 교환

단순 결합은 seed를 보존한 채 endpoint를 추가하므로 조사량이 늘어난다. FlowSub는 공식 seed 수를 예산 \(B\)로 고정하고 seed와 seed-overlap 체인 endpoint의 합집합에서 정확히 \(B\)개를 다시 선택한다.

Predicate endpoint evidence는 noisy-OR로 chain reliability를 만들고, node를 삭제했을 때 reliability가 감소한 비율을 node-chain 반사실 책임도로 사용한다. 삭제가 연속 predicate의 마지막 공통 endpoint를 제거하면 남은 chain reliability는 0이다. 연속 predicate 사이의 edge score는 양쪽 local evidence 기하평균에 비례해 공통 endpoint로 보존 배분한다.

공식 detector score는 같은 score universe의 empirical percentile로 바꾸고, anomaly evidence와 causal evidence의 기하평균을 node-chain utility로 사용한다. 최종 목적함수는 정규화한 detector 보존 항과 포화형 chain coverage 항의 합이다. 이 함수는 비음수 단조 부분모듈 함수이며 cardinality \(B\) 아래 greedy 선택은 최적 목적값의 \(1-1/e\) 이상을 보장한다. 전체 식과 증명은 `docs/flow.md`에 둔다.

공식 score, split, detector threshold, trace profile, 체인 상수, 후보와 예산에는 label을 사용하지 않는다. CADETS 결과를 보기 전에 full·responsibility-only·flow-only·anomaly-only 네 식과 UUID tie-break를 고정했고 THEIA에서는 수정하지 않았다.

## RAVEL 조건부 증명 ledger

FlowSub의 성능 이득이 responsibility와 부분모듈 교환에 집중된다는 ablation 뒤, 별도 구성요소의 결합을 제거한 연구 분기를 만들었다. RAVEL은 official detector seed 하나를 공격 가설의 root로 두고, 그 root와 실제 endpoint가 겹치며 모든 인접 predicate 사이에 공통 endpoint가 있는 체인만 증명 후보로 인정한다.

Root, predicate endpoint, 인접 bridge를 하나의 proof clause 계층으로 만들고 대안 endpoint는 더하며 필수 clause는 곱한다. 반복 UUID는 proof 길이와 출현 횟수의 역수 지수를 사용해 같은 detector evidence를 복제하지 않는다. Root는 이미 관측됐다는 조건이므로 score를 다시 곱하지 않고 값 1의 gate로만 사용한다.

Node 점수는 조건부 proof ledger에서 해당 UUID를 제거했을 때 사라지는 자본

\[
\Delta_v=\mathcal L(\mathbf1)-\mathcal L(\mathbf1_{-v})
\]

로만 정의한다. Detector와 chain 점수의 가중합, flow, coverage, submodular objective는 사용하지 않는다. 정확한 동점에만 calibrated e-value를 사용한다. 전체 식, 증명과 실패한 보존형은 `docs/ravel.md`에 기록했다.

## Recovery-Reflex 방지

공격자가 약한 이상을 조작해 방어의 강한 복구 행동을 유도하고, 그 행동 자체로 임무를 방해할 수 있다. 이를 막기 위해 다음 조건을 적용한다.

- 두 개 이상의 독립 계층 증거
- 조치의 임무 영향과 가역성 검사
- 시간 제한 또는 명시적 해제 조건
- 실행 후 실제 상태 변화 검증
- 효과가 없거나 임무 손실이 커지면 단계 하향 또는 복구

## LLM의 역할과 비교

핵심 체인 생성, 점수 계산, 제약 검증, 최종 행동은 결정론적으로 수행한다. LLM은 모호한 텍스트 해석과 후보 설명에만 선택적으로 사용하며 최종 행동권을 갖지 않는다.

보조 비교군은 같은 모델, temperature, token 예산, 관측 도구, 행동 공간, 최대 step을 사용한다.

1. 목표만 받은 LLM
2. 구조화된 predicate와 행동 도구를 받은 LLM
3. predicate, 체인 메모리, 오케스트레이터를 모두 받은 LLM

API 비밀은 코드, 설정, 로그, 결과 파일에 저장하지 않는다.

## 벤치마크 연결

| 공통 개념 | CAGE Challenge 4 | DARPA TC |
|---|---|---|
| evidence | Blue 관측, 메시지, 행동 결과 | provenance 노드와 이벤트 |
| layer | 구역, 호스트, 서비스, 세션, 임무 | 네트워크, 파일, 프로세스, 주체 역할 |
| predicate | 탐색, 실행, 권한, Impact, 대응 | 읽기, 쓰기, 실행, 연결, 신원 관계 |
| 공격 출력 | 검증 가능한 공격 가설 | 조사 노드·간선·체인 |
| 방어 출력 | decoy, 분석, 제거, 격리, 복구 | 탐지 우선순위와 조사 체인 |
| oracle | reward, 서비스, 임무 상태 | 세밀한 악성 노드와 공격 사례 |

## 과적합 방지

- test 정답과 true state를 에이전트 입력으로 사용하지 않는다.
- 호스트 이름, action index, 데이터셋별 악성 패턴을 공통 코어에 넣지 않는다.
- 정상 학습 구간에서만 기준과 시간 창을 결정한다.
- CADETS 개발 후 파라미터를 고정하고 THEIA, TRACE, E5에 그대로 적용한다.
- 테스트 결과를 보고 임계값, epoch, seed를 선택하지 않는다.
- 모든 실패 seed와 모든 실행 결과를 보존한다.
- reward 외에 임무 영향, 행동 비용, 오탐, 체인 유효성, 실행 시간도 함께 보고한다.
