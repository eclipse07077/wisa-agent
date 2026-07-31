# 선행 연구와 공개 코드 점검

## CAGE Challenge 4

- 공식 환경: `cage-challenge/cage-challenge-4`, commit `8c3c50ca54b176c2de199847944e8dcc035497e3`
- 공식 평가: `FiniteStateRedAgent`, 100 episode, episode당 500 step
- 환경 논문: Kiely et al., AAAI 2025, DOI `10.1609/aaai.v39i28.35158`
- 전체 결과 논문: Kiely et al., AI Magazine 2025, DOI `10.1002/aaai.70021`
- 공개 상위 MARL 코드: `cybermonic/cage-4-submission`, commit `2afd652d80ce9d4051a07c23c2538f3dec6bb6c6`
- 계층형 MARL 비교: Singh et al., Reinforcement Learning Journal 6 (2025), 790–810

전체 결과 논문에서 상위 네 팀 중 세 팀은 heuristic이었다. Team UC는 topology 존재 여부와 지속되는 process·connection·file flag를 추적하고 reactive 대응과 policy 정렬을 결합했다. Team Lancer는 host priority, decoy, Analyse, Remove, Restore를 상태기계로 운용했다. Team Punch는 Analyse와 Restore를 round-robin으로 실행했다. Cybermonic은 부분 관측을 host, router, port, file, internet의 temporal attributed graph로 유지하고 PPO와 GNN을 사용했다.

공식 CC4 평균 reward는 Team UC `-113±35`, Team Lancer `-118±40`, Team Punch `-142±44`, Cybermonic `-193±84`였다. 휴리스틱이 MARL보다 높았지만 Red 변형에서는 순위와 성능이 크게 바뀌었다. 따라서 본 연구는 공식 reward와 함께 topology 일반화, invalid action, 행동 비용, 공격 변형을 별도로 평가한다.

전체 결과 논문은 피싱으로 감염된 사용자 권한 세션에서는 `Analyse`가 제거 가능한 파일을 충분히 찾지 못해 `Remove`의 가치가 낮을 수 있다고 분석한다. 그러므로 `Analyse → Remove` 빈도를 늘리는 것 자체를 일반적인 개선으로 간주하지 않고, privileged session과 mission effect가 연결된 경우의 복구 경로를 분리해 평가한다.

Cybermonic 공개 코드는 관측을 누적 그래프로 유지하고 행동을 host node, subnet edge, global action으로 분해한다. `Restore`, `DeployDecoy`, `Analyse`, `Monitor`의 결과를 서로 다른 그래프 편집으로 반영하고, 8-bit 메시지에는 subnet별 compromise와 scan 존재 여부 및 통신 유효 비트를 넣는다. 본 구현은 이 코드에서 관측 누적과 행동 수준 분리 원칙만 참고하며 PPO 가중치, 학습 분포, action index는 가져오지 않는다.

Singh et al.의 H-MARL은 방어를 Investigate, Recover, Control Traffic으로 분해하고 master policy가 하위 정책을 선택한다. 이 분해는 행동 오케스트레이션 비교 근거로 사용하되, 본 보고서 기반 정책의 위험 구간이나 체인 점수를 해당 논문의 학습 결과에 맞춰 조정하지 않는다.

## MAGIC

- 공식 코드: `FDUDSDE/MAGIC`, commit `aa0b647eea74b6faa0e52eb444370c4411a32cbe`
- 논문: Jia et al., USENIX Security 2024
- 데이터: DARPA TC E3 CADETS, THEIA, TRACE

MAGIC은 정상 provenance graph의 node·edge type을 masked graph autoencoder로 학습하고, KNN distance를 anomaly score로 사용한다. 공개 quick evaluation은 재현됐지만 공개 `model/eval.py`의 entity-level F1은 test label로 계산한 precision-recall curve에서 데이터셋별 목표 recall에 도달하는 지점을 선택한다. 이 F1은 재현 참고값으로만 사용하고 본 연구의 공정 비교에는 사용하지 않는다.

MAGIC의 ThreaTrace 라벨은 CADETS 12,846개, THEIA 25,319개, TRACE 68,086개로 넓은 공격 neighborhood를 포함한다. 세밀한 attribution을 주장하는 주 평가에는 부적합하다.

## ORTHRUS

- 공식 코드: `ubc-provenance/orthrus`, commit `e7f25dfee1ddd182a955b88f8a90a8cbd4a8e543`
- 통합 재현 코드: `ubc-provenance/PIDSMaker`, `velox` commit `54f687c54aa03e5519cf44953d5ee44f5f6a4a28`
- 논문: Jiang et al., USENIX Security 2025
- 통합 프레임워크 논문: Bilot et al., USENIX Security 2025 및 arXiv:2601.22983
- 데이터: CADETS, THEIA, ClearScope의 E3·E5

ORTHRUS는 word2vec node feature, temporal graph attention, edge type prediction loss, validation 최대 loss threshold, K-Means를 이용해 node-level anomaly를 찾고 DEPIMPACT로 공격 경로를 복원한다. 세밀한 ground truth는 데이터셋별 41–123개 수준으로 attribution 품질 평가에 적합하다.

공개 README는 누락된 `PYTHONHASHSEED` 때문에 논문 결과를 정확히 재현할 수 없다고 명시한다. 또한 현재 `attack_reconstruction/tracing.py`는 test MCC가 가장 높은 epoch를 선택하므로, 본 연구에서는 validation으로 선택한 epoch를 고정해 사용한다.

현재 ORTHRUS README의 ClearScope E5 기대값은 전체 방법 `TP 4, FP 8, FN 47`, anomaly-only `TP 2, FP 5, FN 49`다. 이는 우리 방법의 목표값이나 임계값으로 사용하지 않고, 외부 코드가 실제로 E5 attribution을 평가한 근거와 결과 해석의 참고 범위로만 사용한다.

PIDSMaker는 2025년 6월부터 원본 Avro 변환 대신 사전구축 PostgreSQL dump를 공식 재현 경로로 제공한다. ClearScope E5 dump는 약 6.2GB이고 로드 시 약 49GB다. 첫 동결 E5 실험은 공개 dump의 node·event 테이블을 서버에 복원하지 않고 읽기 전용으로 스트리밍해 기존 SQLite 표현으로 변환했으며, PIDSMaker feature나 모델 출력은 입력하지 않았다.

후속 detector 분리 실험은 이 결과와 별개로 공식 PostgreSQL preprocessing, 공개 pretrained weights와 Velox score를 변경 없이 재현하고, score를 체인 seed로만 사용한다. 이 경우 detector 지표는 공식 Velox 재현으로, 확장 뒤의 matched-budget attribution만 결합 방법의 결과로 구분한다.

PIDSMaker 논문은 서로 다른 전처리, 데이터 분할, ground truth와 metric이 PIDS 비교를 어렵게 만든다고 지적한다. 본 연구는 각 실험에서 detector의 원래 분할과 node universe를 유지하고, fine UUID ground truth를 출력 고정 뒤 동일 metric 프로세스에서 적용한다. 기존 profile-chain 결과와 공식 Velox-seed 결과는 분할과 universe가 다르므로 서로 직접 합치지 않는다.

## 수정 OpTC와 라벨 민감도

- 논문: Majorczyk, Pilastre, Dijoud, “A New Hope for DARPA OpTC,” CSET 2025
- 논문 원문: HAL `hal-05474126`
- 수정 데이터: DOI `10.57745/UXCWOC`
- 공개 코드: `fmajorcz/a_new_hope_for_darpa_optc`, commit `644f41fb0a955e471f34bed016fb2bfd9c74dc04`

저자들은 원본 OpTC의 process·entity UUID timeline 오류가 약 40%의 process와 4.22%의 event에 영향을 준다고 측정했다. 세 번의 정정 뒤 오류 event 비율은 1.6%로 줄지만, 약 28.24%의 process는 여전히 영향을 받으며 PID 4와 일부 timestamp 문제도 남는다. 새 expert ground truth는 360,925개 malicious event와 1,103개 actorID를 포함해 기존 라벨의 313,018개 event와 779개 actorID보다 넓다. Host 라벨은 악성 actor process, 그 자식과 이들이 생성한 event를 network eCAR-Bro 기록과 대조해 구성한다.

정정과 라벨 변경은 방법마다 다르게 작용한다. 논문에 보고된 원본→수정 F1은 Flash H201 `0.84→0.84`, Flash H501 `0.84→0.87`, GAE H201 `0.24→0.19`, GAE H501 `0.60→0.60`, KAIROS aggregate `0.18→0.16`이다. 즉 데이터 정정이 모든 IDS 점수를 일률적으로 높이지 않으며, label coverage와 attack segment 정의가 성능 결론을 바꿀 수 있다.

이 결과 때문에 본 연구는 수정 OpTC를 PIDSMaker dump와 분리된 경로로 다룬다. 동일한 H201·H501 split과 512 budget에서 detector root와 RAVEL v6를 비교했지만, 두 label은 이후 인증형 projection 설계에 사용됐으므로 최종 논문에서는 개발 근거로만 분류한다. 수정 ground truth는 label-free manifest를 고정한 뒤 열었고 저자 파일의 `actorID` process UUID를 별도 malicious node set으로 평가했다.

## ThreaTrace와 KAIROS

ThreaTrace 공개 코드는 E3 CADETS, THEIA, TRACE, FiveDirections 파서와 ground truth를 제공한다. 이 라벨은 MAGIC 재현용 보조 평가에 사용한다.

KAIROS 공개 코드는 DARPA TC에서 temporal graph network의 edge type prediction loss를 anomaly score로 사용하고, 시간 창별 이상 edge를 attack graph로 묶는다. 본 연구는 시간 순서 보존과 attack-instance 단위 평가를 참고하되, fixed threshold나 test 기반 선택은 복제하지 않는다.

KAIROS 재현성 연구는 공개 E5 평가 코드가 필요한 `attack_list`를 생성하지 않아 ClearScope E5에서 모든 graph를 정상으로 라벨링하는 문제를 보고했다. 따라서 논문의 요약 그래프나 공개 스크립트의 출력만 신뢰하지 않고, ORTHRUS fine UUID ground truth와 우리 metric 코드의 label coverage를 함께 확인한다.

## 반사실·흐름·부분모듈 설명

ProvX는 provenance GNN의 예측을 뒤집는 연속 edge-mask를 학습해 counterfactual explanation을 만든다. FlowSub는 GNN gradient나 재학습 없이 이미 생성된 typed temporal chain에서 node 하나를 삭제한 정확한 reliability 차이를 계산한다. 따라서 반사실이라는 개념 자체가 아니라 detector-independent chain responsibility가 구별점이다.

Axiomatic effect propagation의 recursive Shapley value는 structural causal graph에서 effect를 경로별로 배분한다. FlowSub는 관측된 연속 predicate의 공통 endpoint라는 더 좁은 구조에서 edge evidence 보존, local-evidence 비례성, null endpoint와 대칭성으로 유일한 배분을 정의한다. 일반 causal attribution의 최초 제안으로 주장하지 않는다.

부분모듈 feature·region 선택과 abductive explanation은 이미 확립된 연구 영역이다. FlowSub의 novelty 경계는 공식 detector 예산을 늘리지 않는 provenance-node 교환, 정확한 chain deletion responsibility, 보존 flow, label-free detector interface를 하나의 정규화된 단조 부분모듈 목적함수로 묶은 데 있다. Greedy의 \(1-1/e\) 근사 보장은 이 목적함수 선택에 대한 계산 보장이지 악성 node 회수율 보장은 아니다.

Ablation에서는 conserved flow의 수학적 공리는 성립했지만 full 선택이 responsibility-only와 같았다. 따라서 실증적 성능 주장은 반사실 책임도와 부분모듈 예산 교환으로 좁히며, flow는 dependency explosion을 해석하는 보조 attribution으로만 남긴다.

## E-process·semiring·조건부 proof

E-value와 e-process는 optional stopping에도 유효한 순차 검정 단위로 이미 확립돼 있다. 조건부 e-variable의 product, predictable convex mixture, Ville inequality도 기존 이론이다. RAVEL은 이 결과 자체를 새 기여로 주장하지 않는다.

Semiring of Evidence와 attack-tree attribute domain은 대안 경로를 더하고 직렬 requirement를 곱하는 일반 계산 틀을 제공한다. Weighted automata와 trust-path 연구에도 같은 sum-product 구조가 있다. 따라서 provenance chain을 sum-product로 계산한다는 것만으로 novelty를 주장할 수 없다.

RAVEL의 더 좁은 연구 질문은 detector alert가 연 root account 안에서 typed predicate endpoint와 continuity bridge를 조건부 proof clause로 만들고, chain reconstruction과 node attribution을 같은 proof posynomial의 정확한 intervention으로 정의할 수 있는가이다. 분수 지수를 허용하므로 엄밀히는 polynomial이 아니라 양의 계수와 실수 지수 monomial의 합인 posynomial이다. 현재 검색에서는 이 formulation과 직접 일치하는 provenance attack reconstruction 연구를 찾지 못했지만, 체계적 문헌 검토 전에는 최초 사용이라고 쓰지 않는다.

ProvX와 CoDy는 graph counterfactual을 생성하지만 root-owned proof capital을 사용하지 않는다. ORTHRUS와 PIDSMaker는 provenance dependency와 anomaly attribution을 제공하지만 conditional proof account를 정의하지 않는다. 이 차이는 잠재적 novelty 경계이지 성능 우월성 근거가 아니다.

현재 replay에서 root, topology, endpoint e-value가 같은 telemetry에 의존하므로 e-process의 conditional-validity 가정을 자동으로 만족하지 않는다. RAVEL의 unit test와 benchmark는 ledger 대수와 selection 결과를 검증한다. Anytime false-alarm control을 논문 claim으로 올리려면 root 선택과 후속 evidence를 시간적으로 분리하거나 selection-aware conditional calibration을 별도로 증명해야 한다.

2026-07-31 최신 검색에서는 직접 인접한 네 연구를 추가로 감사했다. TPPR(arXiv:2510.22191)은 TTP 순차 패턴, edge threat score와 path confidence로 공격 경로를 선택·병합한다. ProGQL(arXiv:2510.22400)은 analyst 지식을 constrained traversal과 value propagation query로 표현한다. ATEX-CF(arXiv:2602.06240)는 일반 GNN 예측을 뒤집기 위해 제한된 edge 추가·삭제를 최적화한다. GridPRISM(DOI `10.1016/j.ijcip.2026.100849`)은 CPU SLO 아래 subgraph expansion과 semantic masking의 계산 예산을 명시한다. 어느 연구도 detector root마다 한 개의 analyst slot을 공급하고 exact UUID proof deletion을 utility로 삼아 여러 alert 사이의 node 중복을 전역 capacity로 막지는 않는다. 특히 GridPRISM의 budget은 window별 계산·masking 자원이고 RAVEL의 budget은 detector가 연 distinct investigation target 수이므로 같은 “budgeted provenance” 표면에도 최적화 대상이 다르다. 이 감사는 “직접 일치하는 formulation을 찾지 못했다”는 경계만 지지하며 최초성의 완전한 증명은 아니다.

## 공격 조사 방법과 RAVEL의 경계

다음 표는 각 논문의 주된 최적화 대상을 1차 논문과 공개 코드 기준으로 대조한 것이다. 빈 칸은 그 연구의 결함이 아니라 문제 정의가 다르다는 뜻이다.

| 방법 | 출발점 | 체인·그래프 평가 | 고정 조사 예산 | exact node intervention | root별 slot·node capacity |
|---|---|---|---|---|---|
| NoDoze | threat alert | 과거 빈도와 network diffusion | 없음 | 없음 | 없음 |
| ATLAS | attack symptom | 학습한 attack/non-attack sequence | 없음 | 없음 | 없음 |
| DEPIMPACT | POI event | backward impact와 forward causality | top entry, graph 축약 | 없음 | 없음 |
| KAIROS | anomalous event | 시간창 anomaly graph | 없음 | 없음 | 없음 |
| ORTHRUS | anomalous node | dependency reconstruction | compact output | 없음 | 없음 |
| TPPR | anomalous subgraph | TTP-guided path score·merge | confidence threshold | 없음 | 없음 |
| ProGQL | analyst query | constrained traversal·value propagation | query별 제한 | 없음 | 없음 |
| GridPRISM | event window | utility-cost subgraph routing | CPU·masking budget | 없음 | 없음 |
| ProvX | malicious GNN subgraph | prediction-flipping edge mask | top-\(K\) explanation | model prediction 개입 | 없음 |
| ATEX-CF | GNN instance | prediction-flipping edge add/delete | perturbation budget | model prediction 개입 | 없음 |
| RAVEL v6 | detector root | 조건부 proof capital | root 수와 동일 | proof posynomial의 UUID 삭제 | root supply 1, node capacity 1 |

NoDoze는 alert dependency graph에 이상도를 전파해 경보를 triage하고, ATLAS는 symptom과 후보 node 사이의 sequence를 분류해 attack story를 합친다. DEPIMPACT는 POI에서 dependency impact를 역전파한 뒤 상위 entry의 forward causality로 큰 그래프를 줄인다. KAIROS와 ORTHRUS는 anomaly detector 뒤에 attack footprint 또는 dependency reconstruction을 둔다. 이들은 모두 RAVEL보다 넓고 실용적인 탐지·복원 시스템이지만, 여러 detector root가 동일 node를 중복 소비하지 못하게 하는 fixed-budget allocation을 목적함수로 삼지 않는다.

ProvX는 가장 가까운 반사실 선행연구다. ProvX의 개입은 GNN 예측을 뒤집는 최소 edge subset을 찾는 연속 mask이고, RAVEL의 개입은 detector와 독립적인 조건부 proof posynomial에서 UUID 하나를 제거했을 때 사라지는 route capital이다. RAVEL은 설명 sparsity보다 root-owned analyst slot의 전역 배정을 풀며, 한 node를 여러 root가 동시에 보고하지 못하게 한다.

따라서 방어 가능한 novelty 문장은 “반사실, e-value, chaining 또는 matching을 처음 사용했다”가 아니다. 더 좁은 기여는 detector root마다 열린 조건부 provenance proof account의 exact UUID intervention을 transport utility로 정의하고, 고정된 analyst budget과 중복 금지를 하나의 bipartite allocation으로 푼 formulation이다. Exact matching은 표준 계산 도구이며 기여가 아니다.

## 인증형 abstention의 선행연구 경계

V6 외부 실패 뒤 추가한 certified abstention은 selective classification의 일반적 “낮은 confidence면 예측 거절”과 다르다. 별도 confidence estimator, risk-coverage calibration 또는 label 기반 threshold를 학습하지 않고, v6의 전체 root--node 후보가 모든 양의 proof route를 완전히 끊는지에 대한 필요충분 구조 조건만 검사한다. 인증 후보와 private hold로 제한한 exact matching은 인증 transport 수를 먼저 최대화하고, 동률 해에서 v6 assignment 왜곡을 최소화한 뒤 동결된 conformal evidence를 최대한 유지한다. \((B+1)^2,B+1,1\) 우선순위 상계 때문에 하위 목적이 상위 목적을 바꿀 수 없다. 따라서 인증은 actorID 정확도나 회수율의 안전성이 아니라 proof-posynomial fracture의 완전성에만 붙는다.

H051의 `4→3` 실패는 이 경계를 실제로 드러낸다. Top-\(B\) detector root를 같은 예산에서 root 밖 후보로 바꾸면 monotone detector evidence를 높이는 비자명한 교체는 존재하지 않는다. Label을 사용하지 않는 다른 \(B\)-원소 집합은 대칭차의 어느 쪽을 악성으로 두느냐에 따라 baseline보다 좋거나 나빠질 수 있다. 따라서 구조 certificate를 recall certificate로 부르는 것은 불가능하며, 추가 tier, disjoint risk model 또는 명시적 risk--coverage 예산이 필요하다.

Graph counterfactual explanation은 보통 예측을 바꾸는 최소 node·edge·feature perturbation을 찾는다. Robust GCE는 edge subset 제거가 GNN 결정을 바꾸는지와 잡음 안정성을 다루고, ProvX·ATEX-CF도 model prediction을 oracle로 사용한다. RAVEL 인증 규칙은 학습 모델을 다시 질의하지 않고 root-owned clause의 양의 합·곱 구조에서 UUID 하나가 모든 route를 0으로 만드는지를 판정한다. 이는 일반 graph dominator나 cut 개념과 인접하므로 “cut을 처음 사용했다”고 주장하지 않는다. 차이는 endpoint 대안과 continuity bridge를 가진 proof hyperclause에서 full fracture를 판정한 뒤, 여러 root의 fixed assignment를 private hold로 안전하게 사영한다는 데 있다.

VCAUSE는 authenticated data structure로 outsourced provenance query와 causally related component 결과의 무결성을 검증한다. 본 연구의 witness는 데이터나 원격 계산의 무결성을 증명하지 않고, 이미 동결된 proof clause에서 선택 UUID의 algebraic cut 성질을 재생한다. 두 verification 목표는 직교한다.

2026-07-31 검색에서는 provenance attack investigation, graph counterfactual, selective prediction과 verifiable causality 중 universal singleton-cut witness를 root-slot transport의 abstention 조건으로 쓰는 직접 일치 formulation을 찾지 못했다. 이는 검색 범위 내 경계이며 최초성의 증명이 아니다.

## 설계에 반영한 원칙

- CAGE의 무작위 topology를 매 episode 관측에서 재구성한다.
- 정적 decoy 전개가 아니라 체인의 다음 전이에 동적 허니팟을 배치한다.
- TC에서는 탐지 점수와 공격 체인 복원을 분리해 각각 평가한다.
- coarse neighborhood label과 fine node-level ground truth 결과를 섞지 않는다.
- test threshold와 test epoch 선택을 금지한다.
- 복잡한 GNN만 비교하지 않고 단순 규칙과 시간 인접 체인을 포함한다.
