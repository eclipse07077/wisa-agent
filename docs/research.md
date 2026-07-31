# 참고한 논문이랑 공개 코드

최종 방법 설계할 때 실제로 본 것만 정리. 논문 이름만 나열한 게 아니라 어떤 부분을 참고했고 우리 방법이 어디서 다른지도 같이 적었음. 정확한 BibTeX는 `paper/references.bib`, commit은 `paper/artifacts.json` 기준.

## 1. CAGE Challenge 4

### 확인한 자료

- 공식 환경: `cage-challenge/cage-challenge-4`
- Commit: `8c3c50ca54b176c2de199847944e8dcc035497e3`
- 전체 결과 논문: Molina-Markham et al. AI Magazine 2025
- 공개 MARL agent: `cybermonic/cage-4-submission`
- Cybermonic commit: `2afd652d80ce9d4051a07c23c2538f3dec6bb6c6`
- 계층형 MARL 비교: Singh et al. Reinforcement Learning Journal 2025

상위 팀이 전부 복잡한 RL은 아니었음. Team UC랑 Lancer랑 Punch는 topology 상태랑 process·connection·file flag를 계속 추적하는 heuristic 비중이 컸음. Cybermonic은 관측을 temporal attributed graph로 유지하고 PPO랑 GNN을 사용.

공식 평균 reward는 Team UC -113±35, Lancer -118±40, Punch -142±44, Cybermonic -193±84. 공식 숫자는 우리 결과랑 직접 비교하면 안 됨. 실행 환경이랑 agent package랑 평가 조건이 다름.

여기서 가져온 건 세 가지.

- 부분 관측을 한 step짜리 입력으로만 보지 않고 누적 상태로 유지
- 행동을 host·subnet·global 수준으로 나눠서 생각
- `Analyse`·`Remove`·`Restore`·`DeployDecoy` 효과를 서로 다르게 처리

PPO weight나 학습 분포나 action index는 가져오지 않았음. 우리 v12는 결정론적 scope policy.

공식 결과 논문에서 피싱 사용자 권한 session은 `Analyse` 뒤에도 제거 가능한 파일이 충분히 안 잡힐 수 있다고 분석함. 그래서 `Analyse → Remove`를 많이 하는 것 자체를 개선으로 보지 않았고 process랑 connection이 같이 남는지 확인하는 쪽으로 바꿈.

H-MARL은 Investigate·Recover·Control Traffic 하위 정책이랑 master policy를 사용. 역할 분해 아이디어는 참고했지만 그 논문의 학습 결과에 맞춰 우리 risk 구간을 조정하진 않았음.

## 2. MAGIC

- 공식 코드: `FDUDSDE/MAGIC`
- Commit: `aa0b647eea74b6faa0e52eb444370c4411a32cbe`
- 논문: Jia et al. USENIX Security 2024
- 데이터: CADETS·THEIA·TRACE

MAGIC은 정상 provenance graph를 masked graph autoencoder로 학습하고 KNN distance를 anomaly score로 사용.

공개 quick evaluation은 재현했음. 다만 공개 entity F1은 test label로 만든 precision-recall curve에서 목표 recall 지점을 고름. 이 값은 참고용으로만 보고 공정 비교 결과로 안 씀.

MAGIC이 쓰는 ThreaTrace label은 공격 주변을 넓게 잡음. CADETS 12,846개랑 THEIA 25,319개처럼 fine actor attribution보다 훨씬 큼. 우리 fine UUID 결과랑 합치면 안 됨.

정적 graph adapter도 확인했는데 THEIA랑 TRACE에서 anomaly score는 나와도 시간·session 정보가 없어서 유효 chain이 안 만들어졌음. 이 결과 때문에 grounded trace 입력 계약에 temporal order를 남겼음.

## 3. ORTHRUS랑 PIDSMaker

- ORTHRUS 코드: `ubc-provenance/orthrus`
- ORTHRUS commit: `e7f25dfee1ddd182a955b88f8a90a8cbd4a8e543`
- PIDSMaker 코드: `ubc-provenance/PIDSMaker`
- Velox commit: `54f687c54aa03e5519cf44953d5ee44f5f6a4a28`
- ORTHRUS 논문: Jiang et al. USENIX Security 2025
- PIDSMaker 논문: Bilot et al. USENIX Security 2025

ORTHRUS는 word2vec node feature랑 temporal graph attention이랑 edge type prediction loss로 anomaly를 찾고 DEPIMPACT로 공격 경로를 복원. 데이터별 fine UUID가 41~123개 수준이라 node attribution 평가에 적합.

공개 README도 완전 재현 한계를 적어둠. 누락된 `PYTHONHASHSEED` 때문에 논문 결과가 정확히 안 나올 수 있음. 현재 attack reconstruction code에는 test MCC로 epoch를 고르는 경로도 있음. 우리 쪽에서는 validation으로 epoch를 고정하고 test label을 선택에 안 씀.

PIDSMaker는 전처리·split·ground truth·metric이 다르면 PIDS 비교가 크게 흔들린다는 문제를 다룸. 그래서 detector의 원래 node universe랑 split을 유지했고 fine label은 출력 고정 뒤 같은 evaluator에서만 읽었음.

Velox score를 쓸 땐 detector feature랑 학습이랑 score를 수정 안 함. `nodes`랑 `pred_scores`만 label-free interface로 전달. 우리 체인은 detector를 새로 학습하는 게 아니라 고정된 detector 뒤 조사 head로 붙음.

ClearScope E5 공개 기대값은 전체 방법 TP 4·FP 8·FN 47, anomaly-only TP 2·FP 5·FN 49. 이 숫자를 우리 목표값이나 threshold로 쓰진 않았음. E5 attribution을 실제로 평가한 외부 기준으로만 확인.

## 4. 수정 OpTC

- 논문: Majorczyk et al. A New Hope for DARPA OpTC
- Venue: CSET 2025
- 원문: HAL `hal-05474126`
- 수정 데이터: DOI `10.57745/UXCWOC`
- 코드: `fmajorcz/a_new_hope_for_darpa_optc`
- Commit: `644f41fb0a955e471f34bed016fb2bfd9c74dc04`

원본 OpTC는 process랑 entity UUID timeline 오류가 큼. 논문 기준 약 40% process랑 4.22% event가 영향받았음. 세 번 고친 뒤 event 오류는 1.6%로 줄지만 process 약 28.24%는 여전히 영향받음.

수정했다고 모든 방법 점수가 같이 오르는 것도 아님. Flash는 거의 유지되거나 오르고 GAE랑 KAIROS는 일부 떨어짐. 데이터 정정이 성능을 자동으로 높여주는 게 아니라 label coverage랑 attack segment 정의를 바꾼다는 뜻.

H501이랑 H201은 이 corrected label로 평가했지만 최종 RAVEL-C 만들 때 이미 확인했음. 그래서 개발 데이터로만 분류. H051만 label barrier 뒤 holdout으로 사용.

## 5. ThreaTrace랑 KAIROS

ThreaTrace 공개 코드는 CADETS·THEIA·TRACE·FiveDirections parser랑 coarse ground truth를 제공. MAGIC 재현용 보조 평가에만 사용.

KAIROS는 temporal graph network의 edge type prediction loss를 anomaly score로 쓰고 시간 창별 이상 edge를 attack graph로 묶음. 시간 순서 보존이랑 attack-instance 단위 평가를 참고했음.

재현성 연구에서 공개 E5 code가 필요한 `attack_list`를 만들지 못해서 ClearScope graph가 전부 정상으로 처리되는 문제가 보고됐음. 그래서 공개 script 출력만 믿지 않고 fine UUID coverage를 별도로 확인.

## 6. 공격 경로 조사 관련 방법

| 방법 | 시작점 | 주로 푸는 문제 |
|---|---|---|
| NoDoze | Threat alert | 과거 빈도랑 network diffusion으로 경보 triage |
| ATLAS | Attack symptom | 공격 sequence 분류랑 story 결합 |
| DEPIMPACT | POI event | Backward impact랑 forward causality로 graph 축약 |
| KAIROS | Anomalous event | 시간창 anomaly graph 생성 |
| ORTHRUS | Anomalous node | Dependency reconstruction |
| TPPR | Anomalous subgraph | TTP-guided path score랑 merge |
| ProGQL | Analyst query | 제한 traversal이랑 value propagation |
| GridPRISM | Event window | CPU budget 안에서 subgraph expansion |

이 방법들은 RAVEL-C보다 넓고 실용적인 탐지·복원 시스템. 다만 detector root마다 analyst slot 하나를 두고 node 중복을 전역 capacity로 막는 fixed-budget allocation을 직접 목적함수로 삼진 않음.

우리가 처음으로 attack graph를 만들었다고 주장하면 안 됨. 차이는 이미 나온 여러 detector root 사이에서 같은 조사 예산을 어떻게 다시 배정하는지에 있음.

## 7. Counterfactual이랑 flow

ProvX는 provenance GNN 예측을 뒤집는 연속 edge mask를 학습. ATEX-CF도 GNN instance의 edge add·delete로 prediction을 뒤집음.

FlowSub에서 했던 node 삭제 responsibility는 학습 모델을 다시 질의하지 않고 이미 만들어진 typed chain을 직접 지웠을 때 reliability가 얼마나 사라지는지 계산. Counterfactual 개념 자체는 새 게 아님.

Axiomatic effect propagation이랑 recursive Shapley도 path별 effect 배분을 이미 다룸. Submodular feature selection의 greedy `1-1/e` 보장도 기존 결과.

개발 ablation에선 conserved flow를 추가해도 full 선택이 responsibility-only랑 같았음. 그래서 flow를 최종 novelty로 밀지 않음. FlowSub 문서를 따로 남길 이유도 없음.

## 8. E-process랑 proof account

E-value랑 e-process랑 Ville inequality는 기존 순차 검정 이론. Alternative route를 더하고 serial requirement를 곱하는 sum-product 구조도 semiring이랑 attack tree에서 이미 쓰임.

RAVEL이 이 이론을 처음 썼다고 주장하면 안 됨.

RAVEL-C에서 구분되는 부분은 더 좁음.

- Detector root마다 proof account 하나 생성
- Typed predicate endpoint랑 continuity bridge를 clause로 구성
- UUID 하나를 지웠을 때 account 전체가 깨지는지 exact intervention
- Root마다 slot 하나를 두고 node 중복을 capacity 1로 제한
- Certified transport 수랑 proposal distortion이랑 evidence를 exact matching으로 순서대로 최적화

현재 telemetry는 root랑 topology랑 endpoint evidence가 서로 의존. 그래서 conditional e-validity나 anytime false-alarm control까지 주장 못 함. Unit test가 검증하는 건 ledger 대수랑 selection 결과.

## 9. Certified abstention이랑 가까운 연구

일반 selective classification은 confidence가 낮으면 예측을 거절. RAVEL-C는 label 기반 confidence threshold를 학습하지 않음. UUID 하나가 모든 양의 proof route를 완전히 끊는지 구조 조건만 검사.

Graph counterfactual은 보통 GNN 예측을 바꾸는 최소 perturbation을 찾음. RAVEL-C는 모델 prediction을 다시 질의하지 않고 동결된 proof clause에서 UUID 삭제가 account를 0으로 만드는지만 봄.

VCAUSE는 outsourced provenance query랑 causally related component 결과의 무결성을 검증. RAVEL-C witness는 데이터 무결성 증명이 아니라 동결 proof clause의 algebraic cut 재생. 검증 대상이 다름.

TPPR·ProGQL·ATEX-CF·GridPRISM까지 확인했지만 detector root slot이랑 exact UUID proof deletion이랑 cross-root node capacity를 같이 푸는 formulation은 못 찾았음. 그래도 체계적 문헌 검토가 끝난 건 아니라서 최초라고 단정 안 함.

## 10. 지금 방어 가능한 novelty

공통 체인 자체가 novelty는 아님. Best-first search도 novelty 아님. Exact matching도 표준 도구.

방어 쪽에서 가져갈 수 있는 건 evidence scope보다 action scope가 커지지 않게 만드는 제약이랑 effect 확인 전 강한 행동 반복을 막는 구조. CAGE 두 Red에서 실제 개선도 나왔음.

공격 쪽에서 가져갈 수 있는 건 root-owned proof account의 complete UUID fracture를 인증하고 같은 analyst budget 안에서 중복 없이 배정하는 formulation. 거기에 actor recall safety가 자동으로 안 따라온다는 불가능성 정리랑 H051 반증까지 포함.

지금 쓸 수 있는 novelty 문장.

> 서로 다른 계층에서 모인 evidence를 chain으로 연결한 뒤 의사결정 범위를 evidence 범위에 맞추는 오케스트레이션 구조를 제안했다. 방어에서는 이 제약이 불필요한 강한 행동을 줄였고 공격 조사에서는 구조적 complete fracture를 인증하는 fixed-budget projection을 만들었다. 다만 구조적 인증만으로 actor 의미가 보존되지는 않았다.

쓰면 안 되는 문장.

- Attack chaining을 처음 제안했다
- Counterfactual explanation을 처음 사용했다
- E-value나 sum-product proof를 처음 사용했다
- Exact matching 자체가 새 알고리즘이다
- 모든 provenance detector보다 성능이 좋다
- RAVEL-C certificate가 malicious actor를 인증한다

## 11. 설계에 실제로 반영한 것

- CAGE topology를 매 episode 관측에서 다시 구성
- 정적 decoy 전개보다 현재 threat랑 coverage 빈칸을 보고 배치
- TC detector score랑 chain reconstruction을 분리
- Coarse label이랑 fine UUID 결과를 분리
- Test threshold랑 test epoch 선택 금지
- Detector output 수를 조사 budget으로 고정
- 실패한 외부 결과 뒤 같은 holdout에서 방법 수정 금지

논문에 넣을 참고문헌 원문이 필요하면 `paper/references.bib`부터 확인하면 됨.
