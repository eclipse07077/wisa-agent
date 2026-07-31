# 공·방 에이전트 개발 및 실험 정리

예선 보고서 이후에 진행한 공·방 에이전트 개발이랑 실험을 정리한 문서. 지금 결과가 어디까지 나왔는지 먼저 적고, 앞으로 더 해야 할 것도 같이 넣었음. 마지막엔 이 상태로 논문에서 어디까지 주장 가능한지랑 예선 보고서에서 뭐가 달라졌는지 정리해뒀음.

한 줄 요약하면 방어는 성공, 공격은 절반만. 방어는 논문 중심 결과로 써도 될 만큼 나왔고, 공격은 E3에서만 괜찮았고 E5랑 RAVEL-C holdout에서는 다 깨졌음. 그래서 방어는 성능 개선을 주장할 수 있는데 공격은 전체적으로 더 좋다고 말하기 어렵다. 대신 계층형 체인이 언제 먹히고 언제 실패하는지는 설명 가능함.

## 1. 현재까지 한 것과 나온 결과

### 1.1 전체 진행 상태

| 작업 | 상태 | 현재 결과 |
|---|---|---|
| 공통 체인 코어 | 완료 | 로그를 evidence·predicate로 바꾼 뒤 계층형 체인 생성 |
| 방어 에이전트 v12 | 최종 평가 완료 | CAGE 두 Red 정책에서 LayerChain보다 좋게 나옴 |
| Grounded trace | 이전 평가 완료 | CADETS·THEIA E3는 개선, ClearScope E5는 악화 |
| RAVEL-C | 이론·holdout 평가 완료 | 수학적 인증은 성공, holdout 성능은 기존 방법보다 낮음 |
| 능동 공격 에이전트 | 미구현 | 실제 공격 행동을 실행하는 red agent는 아직 없음 |
| 실험 자료 | 대부분 정리 완료 | 코드·테스트·raw result·실험 기록 저장소에 정리 |

지금 TC 쪽 공격 코드는 공격을 직접 실행하지 않음. 발생한 로그에서 공격 체인이랑 조사할 노드를 찾는 정도임. 예선에서 설계한 공격 에이전트는 실제 공격을 고르고 실행하는 구조였으니까, 지금 구현은 공격 에이전트가 아니라 공격 조사 에이전트에 가깝다.

### 1.2 공통 체인 구조

예선에서는 L0~L6까지 계층을 고정해서 썼음. RF에서 시작해 네트워크, DDS, MAVLink 거쳐 임무랑 AI까지 올라가는 구조. 근데 이걸 CAGE랑 TC에 그대로 못 올림. 두 벤치마크엔 그런 계층 이름 자체가 없으니까.

지금은 로그 하나를 typed evidence로 변환함. Evidence에 발생 시각, 출처, 주체, 대상, 둘 사이 관계, confidence, provenance가 들어감. 데이터에 없는 정보는 정상으로 가정하지 않고 `unknown`으로 남겨둠.

Evidence는 다음 다섯 predicate로 변환.

- `ingress`
- `trust_break`
- `lifecycle`
- `mission_effect`
- `response`

외부 진입 → 신뢰 손상 → 내부 상태 변화 → 실제 영향 → 대응으로 이어지는 구조. 예선 L0~L6을 없앤 건 아니고, 벤치마크마다 이름이 달라도 같은 역할로 해석되게 바꾼 거임.

Predicate 사이 edge는 이 식으로 계산.

\[
E_{ij}=0.30T_{ij}+0.30J_{ij}+0.25G_{ij}+0.15M_{ij}.
\]

`T`는 시간 근접성, `J`는 shared context, `G`는 공격 단계가 앞으로 진행되는 정도, `M`은 실제 영향과의 연결.

가중치는 예선이랑 동일. 시간 창 18초, edge threshold 0.58, 최대 체인 길이 5도 그대로 씀.

달라진 것도 있음. 특정 정보가 데이터에 없으면 그 항목을 0점 처리하지 않고, 관측 가능한 항목끼리 가중치를 다시 나눔. UGV bonus랑 특정 hostname 규칙은 뺐음. 벤치마크 하나에만 맞는 규칙이 공통 코어에 들어가면 안 되니까.

### 1.3 방어 에이전트 설계

방어 에이전트는 `Perceive → Detect → Decide → Respond → Recover` 순서로 돌아감.

기본 위험도는 confidence, severity, chain correlation, asset criticality로 계산.

\[
R_{\mathrm{rule}}=0.35q+0.25v+0.25c+0.15k.
\]

정상 상태에서 벗어난 정도를 계산할 수 있으면 이 식도 같이 씀.

\[
R_{\mathrm{deviation}}=0.50a+0.30c+0.20k.
\]

처음엔 위험도 계산 중심으로 정책을 짰음. 근데 실제 CAGE 실험 돌려보니까 같은 `Analyse`랑 `Remove`만 계속 반복됐음. 판단 근거는 설명이 되는데 reward는 계속 떨어짐.

초기 v6은 LayerChain보다 564.72점 낮았고, v9은 2,738.65점, v10도 457.45점 낮았음. 가중치만 만져서는 답이 안 나옴.

그래서 v12에서는 점수 말고 행동 구조를 바꿨다. 네 가지.

첫 번째, evidence scope랑 action scope 맞추기. 확인된 증거가 connection 수준이면 그보다 넓은 범위의 행동은 바로 실행 안 함. 증거가 약하면 `Analyse`나 `DeployDecoy`로 한 번 더 확인하고, process랑 connection이 같이 확인된 다음에 강한 행동을 검토함.

두 번째, 강한 행동의 반복 방지. 행동 API가 성공을 반환해도 바로 해결된 걸로 안 봄. 이후에 process나 connection이 다시 나타나는지 확인하고, 확인 끝나기 전까진 같은 대상에 같은 행동 반복 안 함.

세 번째, decoy 배치 방식. 시작할 때 전 위치에 다 깔지 않음. 위협이 있으면 다음 이동 후보를 먼저 막고, 없으면 역할별 coverage가 비어 있는 곳을 채움.

네 번째, 복구 방식. 공격 영향이 이미 발생한 상황에서는 `Remove` 반복 안 하고, 정상 서비스를 되돌리는 `Restore`를 먼저 씀.

### 1.4 방어 실험 결과

CAGE Challenge 4에서 episode당 500 step으로 평가. 공식 `FiniteStateRedAgent`랑 따로 구현한 chain-aware Red를 같이 썼고, 각 Red 정책마다 seed 100개. LayerChain이랑 v12는 같은 seed끼리 비교했음.

| Red 정책 | 방어 방법 | 평균 reward | privileged host | impacted host | 성공한 Impact |
|---|---:|---:|---:|---:|---:|
| 공식 Red | LayerChain | -3110.39 | 35.12 | 8.30 | 8.31 |
| 공식 Red | v12 | **-2641.74** | **32.28** | **7.41** | **7.46** |
| chain-aware Red | LayerChain | -3703.61 | 35.50 | 6.58 | 6.64 |
| chain-aware Red | v12 | **-3108.22** | **33.35** | **5.53** | **5.56** |

공식 Red에서 reward 468.65점 상승. 95% bootstrap 구간은 [276.24, 656.89]. Privileged host 2.84개, impacted host 0.89개, 성공한 Impact 0.85개 감소.

chain-aware Red에서는 595.39점 상승, 구간은 [410.39, 784.28]. Privileged host 2.15개, impacted host 1.05개, 성공한 Impact 1.08개 감소.

reward만 오른 게 아니라 두 Red 정책 전부에서 공격 영향 지표가 같은 방향으로 줄었음. 여기까진 깔끔하게 나왔다.

근데 LayerChain은 어디까지나 내부 baseline임. CAGE 대회 상위 제출물을 같은 환경에서 다시 돌린 게 아니니까, 이 결과만으로 CAGE SOTA는 못 함.

### 1.5 Grounded trace 공격 조사

TC 로그엔 READ, WRITE, CONNECT 같은 이벤트가 지겹게 반복됨. 모든 이벤트를 체인 후보로 쓰면 흔한 이벤트가 결과를 거의 다 먹어버림.

Grounded trace는 정상 profile에서 크게 벗어난 이벤트를 먼저 찾음. 그 이벤트랑 같은 process의 18초 구간을 하나의 session으로 복원하고, 그 안에서 공격 단계가 이어지는 이벤트만 predicate로 묶음.

이상 점수 계산식.

\[
A(e)=0.50A_{\mathrm{struct}}(e)+0.30A_{\mathrm{trace}}(e)+0.20A_{\mathrm{path}}(e).
\]

Threshold는 validation score의 0.995 quantile로 고정. Test label은 threshold 결정에도 체인 생성에도 안 씀.

체인 점수랑 node 점수도 분리했음. 긴 session 하나에 들어갔다는 이유만으로 모든 endpoint가 공격 후보 되는 걸 막으려고.

| 데이터 | 방법 | AUROC | AP | 조사 노드 | 찾은 악성 노드 |
|---|---|---:|---:|---:|---:|
| CADETS E3 | anomaly-only | 0.78705 | 0.126001 | 530 | 10 |
| CADETS E3 | grounded trace | **0.79144** | 0.125996 | 530 | **17** |
| THEIA E3 | anomaly-only | 0.83723 | 0.028519 | 1,218 | 8 |
| THEIA E3 | grounded trace | **0.84664** | **0.028947** | 1,218 | **17** |
| ClearScope E5 | anomaly-only | 0.52672 | 0.023037 | 522 | **11** |
| ClearScope E5 | grounded trace | **0.54243** | **0.023052** | 522 | 4 |

CADETS 10 → 17개, THEIA 8 → 17개. 같은 조사 예산 안에서 실제 공격 노드를 더 많이 찾았음.

CADETS AP는 아주 조금 낮아짐. 전체 ranking까지 좋아졌다고 보긴 어렵고, 상위 조사 대상 고르는 쪽만 좋아진 걸로 봐야 함.

근데 E5는? 반대로 나옴. AUROC랑 AP는 조금 올랐는데 악성 노드 회수가 11 → 4개로 줄었고, THEIA의 공격 없는 구간에서도 노드가 196개 튀어나왔음. E3 결과가 다른 데이터 표현까지 그대로 이어지진 않는다는 뜻.

Path 빼고 CADETS 진단 돌렸더니 17/530이 3/1,220으로 떨어짐. Path가 체인에서 중요한 건 확실함. 그렇다고 E5 실패가 path 하나 때문이라고 단정하긴 어렵다. CDM 버전 차이랑 relation 표현 차이도 남아 있으니까.

### 1.6 RAVEL-C

Grounded trace 다음엔 체인의 각 노드를 수학적으로 평가하는 방법을 만들었음. 경험적인 점수만으로 node 고르면 왜 그 node를 골랐는지 정확히 설명이 안 되니까.

RAVEL-C는 detector가 고른 root를 입력으로 받고, 조사 예산은 `B`로 고정. 같은 예산 안에서 체인의 핵심 근거를 완전히 끊는 node를 찾음.

root마다 proof account가 있고, 체인의 각 구간은 UUID 후보를 가진 clause로 바뀜. UUID 하나 뺐을 때 모든 route의 근거가 무너지면 complete fracture.

\[
\Gamma(s,v)=\bigwedge_{c\in\mathcal C_s}\bigvee_{Q\in\mathcal Q_{sc}}\mathbf 1[Q=\{v\}].
\]

모든 factor가 양수일 때 `Γ=1`이랑 complete fracture가 필요충분이라는 걸 증명했음. UUID 직접 제거한 계산이랑 route index 계산이 같은지도 테스트로 확인함.

그 다음 root마다 조사 node를 하나씩 배정. 같은 node가 여러 root에 중복 배정되진 않음. 목표는 세 단계.

1. 인증 가능한 이동 수를 최대화
2. 기존 proposal과 달라지는 선택 수를 최소화
3. 앞의 두 조건이 같으면 evidence가 큰 node 선택

이 가중치로 세 목표의 순서를 고정.

\[
\omega_{sv}=(B+1)^2\mathbf 1[v\neq s]+(B+1)\mathbf 1[(s,v)\in M_6]+\bar e_v.
\]

Exact matching 결과는 작은 그래프 brute-force 결과랑 일치함.

여기까진 의도한 대로 다 구현됐다. 문제는 그 다음임. complete fracture랑 실제 악성 actor가 같은 의미가 아니라는 것. Label이랑 evidence 사이에 추가 가정이 없으면 root를 다른 node로 바꾸면서 actor recall을 항상 유지하는 게 불가능함. 이것도 정리로 증명했음.

H051 holdout 결과. 조사 예산 512.

| 방법 | 찾은 악성 UUID |
|---|---:|
| Velox | 4 |
| FlowSub | **8** |
| Fractional proposal | 2 |
| RAVEL-C | 3 |

RAVEL-C가 fractional proposal의 2개를 3개로 올리긴 했음. 딱 거기까지. Velox 4개보다 낮고 FlowSub 8개랑은 차이가 큼.

사전에 정한 성공 조건은 전부 미달. Primary safety, secondary efficacy 둘 다 실패. FlowSub noninferiority랑 전체 비교군 strict superiority도 실패.

H501 개발 데이터에선 Velox 7개 RAVEL-C 8개, H201은 둘 다 2개 나왔음. 근데 이 두 데이터는 최종 방법 만들면서 label을 이미 봐버려서 외부 검증 결과로는 못 씀.

RAVEL-C에서 지금 건질 수 있는 건 이 정도.

- Complete fracture 검사 가능
- 조사 예산이랑 node 중복 제약을 정확히 지킴
- 세 단계 목적의 우선순위를 exact matching으로 지킴
- 구조적 인증만으로 actor recall을 못 지킨다는 걸 이론이랑 holdout 양쪽에서 확인

성능 우월성은 주장 불가.

### 1.7 실험 기록과 재현성

CAGE는 개발/검증/최종 seed를 분리했고, 최종 평가는 두 Red 정책에서 각각 100 paired seed로 돌렸음.

TC는 출력 고정하고 나서 test label을 읽었음. RAVEL-C H051도 선택 결과랑 code hash 먼저 고정한 다음에 label 평가함.

실패한 버전이랑 불리한 결과도 안 지우고 그대로 남겨뒀음. 지금 단위 테스트랑 통합 테스트는 150개 통과.

남은 문제 하나. Windows랑 Linux 사이에서 line ending 바뀌면 결과 파일 SHA-256이 달라질 수 있음. 계산이 틀린 게 아니라 checker 이식성 문제인데, 제출 전엔 고쳐야 함.

## 2. 아직 부족한 것

### 2.1 공격 방법 통합

지금 통합 원고는 grounded trace, 공격 전용 원고는 RAVEL-C를 씀. 두 방법을 연결하는 건 가능한데 아직 하나의 pipeline으로 평가해본 적이 없음.

Grounded trace는 raw log에서 체인을 만들고, RAVEL-C는 detector root랑 체인을 받아서 조사 node를 다시 배정함.

둘을 하나로 쓰려면 `grounded trace → RAVEL-C` 전체를 새 holdout에서 평가해야 함. 지금은 서로 다른 실험에서 따로 평가한 상태라, 결합하면 좋아지는지 나빠지는지 아직 모름.

그래서 지금 자료로 논문 쓸 거면 두 방법은 분리하는 게 맞다. Grounded trace는 통합 원고에, RAVEL-C는 공격 조사 전용 방법으로 빼는 쪽.

### 2.2 능동 공격 에이전트

예선 공격 에이전트는 실제로 공격을 실행하는 구조였음. LLM commander가 공격 고르고, RL tactician이 parameter 조정하고, 실행 모듈이 수행.

지금 TC 코드는 사후 조사 도구임. 논문에서 자율 공격 에이전트라고 부르면 실제 구현이랑 안 맞음. 공격 조사 에이전트가 정확한 표현.

능동 공격 에이전트를 넣으려면 이 순환을 새로 구현해야 함.

`상태 관측 → 공격 가설 생성 → 행동 선택 → 실행 → 방어 반응 확인 → 체인 갱신`

### 2.3 방어 ablation

v12에서 네 개가 한꺼번에 바뀌었음.

- Evidence scope와 action scope 제약
- 강한 행동의 반복 방지
- 동적 decoy coverage
- `Restore` 중심 복구

그래서 지금 결과는 v12 전체가 좋아졌다는 것만 보여줌. 각 요소가 얼마나 기여했는지는 모름.

논문 중심 기여를 scope constraint로 잡을 거면 이 실험들이 필요함.

- v12에서 scope constraint 제거
- v12에서 recurrence watch 제거
- v12에서 adaptive decoy 제거
- v12에서 recovery 전환 제거

### 2.4 비교 baseline

방어는 내부 LayerChain, 공격은 anomaly-only랑 Velox, FlowSub랑 비교했음.

CAGE 공개 상위 agent랑 같은 환경에서 붙여보진 못했음. TC도 ORTHRUS, KAIROS, DEPIMPACT, ProvX, VCAUSE를 같은 전처리·같은 예산으로 돌린 게 아님.

그래서 지금 상태로 SOTA는 못 함. 논문 심사에서도 비교군 부족을 제일 먼저 물고 늘어질 가능성이 큼.

### 2.5 RAVEL-C의 actor 의미

RAVEL-C는 구조적으로 중요한 node를 찾는 거지, 그 node가 실제 악성인지까지 보장하진 않음. H051에서 악성 root가 unlabeled node로 바뀐 게 딱 이 문제.

다음 방법에서 구조 점수만 더 복잡하게 만드는 건 답이 아님. Actor risk를 따로 다뤄야 함. Root를 추가 tier로 유지하는 방법도 있고, 구조적 완전성·악성 위험·조사 비용을 같이 보여주는 frontier 방식도 가능.

고치면서 H051에 맞추는 것도 안 됨. H051은 이미 label을 봐버렸으니까 새 방법은 새 holdout에서 평가해야 한다.

### 2.6 E5 실패 원인

E3는 좋아지고 E5는 나빠졌는데, path 제거 진단만으로 원인이 다 설명되진 않음.

추가로 확인할 것들.

- CDM 버전이 바뀌면서 사라진 relation과 path
- E5에서 process session이 같은 의미를 가지는지
- 18초 창에 대한 민감도
- Chain score와 actor attribution이 갈라지는 지점
- Structure, trace, path 중 이전에 실패한 항목

목표는 E5 label에 점수 맞추기가 아님. 이 방법이 어떤 조건에서 깨지는지 확인하는 것.

### 2.7 문서와 artifact

통합 원고랑 공격 원고에서 공격 방법 이름이랑 역할을 맞춰야 함. 공격 / 공격 조사 / attribution도 구분해서 쓰기.

CAGE의 `DeployDecoy`를 예선 독립 허니팟처럼 설명하면 안 됨. LLM이랑 RL도 지금 구현된 것처럼 쓰면 안 됨. 이 둘은 특히 주의해야 하는 부분.

Checker는 line ending 영향 안 받게 수정, 최종 표랑 raw result 연결도 다시 확인해야 함.

## 3. 지금 논문에서 할 수 있는 주장

### 3.1 현재 가장 맞는 프레임

지금 결과를 하나로 묶을 때 계층 탐색 자체를 novelty로 잡긴 어려움. 계층 탐색이랑 provenance graph는 관련 연구가 이미 많음.

중심으로 잡을 만한 건 evidence scope랑 decision scope를 맞추는 방식.

방어에선 이 정렬이 먹혔음. 좁은 증거만 있는 상황에서 넓은 범위의 행동을 막았고, 강한 행동도 결과 확인 전엔 반복 안 했음. 그 결과 두 Red 정책에서 reward랑 공격 영향 지표가 같이 좋아짐.

공격 조사에선 정반대 한계가 나왔음. 구조적으로 완전한 chain fracture를 인증해도 그 node가 실제 악성 actor라는 보장이 없음. H051에서 이게 그대로 터짐.

그래서 중심 주장은 이렇게 정리 가능함.

> 계층형 evidence chain은 서로 다른 관측을 연결하는 공통 표현으로 쓸 수 있다. 다만 체인을 만들었다는 것만으로 좋은 의사결정이 보장되지는 않는다. 온라인 방어에서는 evidence 범위에 action 범위를 맞추면서 성능이 좋아졌지만, 오프라인 공격 조사에서는 structural certificate만으로 actor correctness를 보장할 수 없었다. 공격 조사에는 별도의 semantic alignment가 필요하다.

이 프레임이면 방어 성공이랑 공격 실패를 억지로 같은 성공으로 묶을 필요가 없음. 같은 체인 코어가 어디까지 되고 어디서부터 한계가 생기는지 같이 보여주면 됨.

### 3.2 방어 중심 논문

지금 결과만 놓고 보면 방어 중심이 제일 강함.

부분 관측 환경에서 탐지 점수를 바로 강한 행동으로 안 바꿈. 확인된 evidence 범위 안에서만 행동하고, 행동 효과도 다시 관측하고, 동적 decoy 배치도 같이 씀. 이게 내부 LayerChain보다 reward를 높이고 공격 영향을 줄였음.

이 방향이면 grounded trace랑 RAVEL-C는 배경이나 추가 분석으로 줄이는 게 맞음. 대신 v12 ablation이랑 강한 CAGE baseline은 반드시 추가해야 함.

### 3.3 공격 중심 논문

공격은 성능 우월 논문으론 못 씀. H051에서 RAVEL-C가 Velox랑 FlowSub보다 낮게 나왔으니까.

대신 fixed-budget provenance 조사에서 complete fracture를 인증하고 exact allocation을 수행하는 방법으로 정리는 가능함. Label-free structural certificate가 actor recall safety를 보장 못 한다는 정리도 같이 넣고, H051은 그 한계가 실제로 나타난 결과로 쓰면 됨.

성격상 성능 논문이 아니라 이론 + negative result. 투고처도 그런 성격을 받아주는 데로 잡아야 한다.

### 3.4 주장 가능 범위

| 가능한 주장 | 현재 불가능한 주장 |
|---|---|
| v12가 두 Red 정책에서 내부 LayerChain보다 reward가 높았다 | v12가 CAGE SOTA다 |
| v12가 세 공격 영향 지표를 두 Red 정책 모두에서 낮췄다 | v12의 각 요소가 독립적으로 성능을 높였다 |
| Grounded trace가 CADETS·THEIA E3에서 악성 node 회수를 늘렸다 | Grounded trace가 TC 전체에 일반화된다 |
| Grounded trace가 E5에서는 악성 node 회수를 줄였다 | E5 실패 원인이 path 하나다 |
| RAVEL-C가 complete fracture와 fixed-budget allocation을 인증한다 | RAVEL-C가 actorID 정확성을 인증한다 |
| Label 가정 없이 recall 비감소를 보장할 수 없음을 증명했다 | RAVEL-C가 기존 방법보다 성능이 좋다 |
| 예선 체인 원리를 실제 benchmark용으로 다시 구현했다 | 예선의 LLM·RL 구조 전체를 구현했다 |
| CAGE에서 동적 decoy 배치 정책을 사용했다 | 독립 허니팟 인프라를 구현했다 |

## 4. 예선 보고서와 달라진 점

### 4.1 유지한 부분

단일 경보보다 여러 계층의 변화가 이어지는 과정을 체인으로 본다는 방향은 그대로.

정상 상태랑 공격 상태의 차이를 먼저 확인하는 것도 유지. 예선의 baseline differential mining이 지금 normal profile이랑 anomaly seed로 이어짐.

Edge 점수 네 요소도 그대로고 가중치도 동일. 시간 창 18초, threshold 0.58, 최대 길이 5도 유지.

한 detector가 바로 차단을 결정하지 않는 방어 구조도 같음. 여러 evidence 모은 다음 중앙 정책이 행동을 고르고, 불확실하면 분석이랑 deception 먼저.

대응 이후 다시 관측하는 폐루프도 유지. 지금은 effect watch랑 recurrence guard로 구현돼 있음.

### 4.2 크게 변경한 부분

| 항목 | 예선 | 현재 |
|---|---|---|
| 환경 | UAV·UGV 임무 시스템 | CAGE 방어 + DARPA TC 조사 |
| 계층 | L0~L6 고정 | 데이터에 맞춘 5단계 predicate |
| 공격 역할 | 공격을 계획하고 실행 | 로그 기반 공격 조사 |
| 공격 평가 | 경험적 chain score | Normal profile + attribution + certificate |
| 방어 판단 | Detector + LLM + 정책 | 결정론적 risk + scope 정책 |
| LLM | Commander·tool 선택에 사용 | 지금 실험에서는 미사용 |
| RL | 공격 세기·threshold 조절에 사용 | 미사용 |
| Self-play | PSRO-lite 계획 | 미수행 |
| 허니팟 | Fake ROS2·DDS·shell·mission server 구성 | CAGE `DeployDecoy` 배치 위치만 결정 |
| 복구 | Checkpoint·rollback·safe mode | `Remove`·`Restore`·effect watch |
| 평가 | 설계·시연 중심 | Holdout·paired seed·실패 결과 보존 |

예선은 전체 시스템 설계가 중심이었고, 지금은 실제 benchmark에서 확인 가능한 것만 남겼음.

범위는 예선이 훨씬 넓음. LLM commander, RL tactician, RAG, self-play에 fake service랑 checkpoint recovery까지 다 들어감. 대신 각 요소의 효과를 분리한 실험이 없었음.

지금은 범위가 좁아진 대신, 어떤 코드랑 데이터가 그 숫자를 만들었는지는 추적 가능함.

### 4.3 체인 평가 방식

예선 최종 체인 점수는 이 식이었음.

\[
S_{\mathrm{pre}}(C)=55\bar E+20\bar q+5\bar v+6|\mathcal S_C|+b_{\mathrm{mission}}+b_{\mathrm{UGV}}.
\]

시뮬레이터에서 중요한 체인을 먼저 고르는 용도였음. 가중치의 최적성이나 node 선택 결과까지 보장하는 식은 아니었음.

지금은 두 개로 쪼갰음.

Grounded trace엔 normal profile이랑 label 분리를 넣었음. 실제 raw log에서 체인을 만들고 node 순위를 계산함.

RAVEL-C는 중요한 node를 complete fracture랑 exact matching 문제로 다시 정의했음. 필요충분조건이랑 목적 우선순위도 증명.

예선의 경험적 체인을 그대로 가져온 게 아니라, 실제 로그용 체인 생성이랑 수학적으로 검사 가능한 조사 결정을 따로 구현한 것.

### 4.4 허니팟과 decoy

예선 허니팟이랑 지금 decoy는 같은 물건이 아님.

예선에선 공격자를 fake ROS2 node, fake DDS topic, fake shell, fake RAG, fake mission server로 유인하는 구조를 계획했음. 공격자 행동도 따로 수집하는 구조였음.

지금 v12는 CAGE의 `DeployDecoy`를 씀. 어느 host에 언제 배치할지만 결정. 별도 fake service를 직접 구현한 건 없음.

그래서 허니팟 시스템이 아니라 동적 decoy 배치 정책이라고 쓰는 게 정확함.

### 4.5 LLM과 RL

지금 핵심 실험엔 LLM이랑 RL 안 들어감.

둘 다 쓰면 결과가 좋아질 수는 있음. 근데 그러면 체인 설계 덕분인지 모델이랑 학습 덕분인지 분리가 안 됨.

지금 정책은 같은 입력이면 같은 출력이 나오고 실패 원인 추적도 쉬움. 대신 예선처럼 LLM 기반 자율 공·방 시스템이라고 부를 수는 없음.

나중에 LLM을 다시 붙인다면 가설 생성이나 설명부터 맡기는 게 맞음. 최종 안전 행동을 바로 맡기는 건 아님. RL도 전체 정책 말고 decoy timing 같은 제한된 parameter부터 대보는 게 안전함.

### 4.6 예선에 없던 부분

예선에 없다가 새로 들어간 건 네 개.

1. Typed evidence와 5단계 predicate
2. Evidence scope와 action scope 제약
3. RAVEL-C의 certificate와 exact allocation, 불가능성 정리
4. Holdout, paired seed, hash, 실패 결과 보존

큰 방향은 예선 그대로임. 근데 실제 구현된 역할은 많이 달라졌다. 방어는 예선 폐루프를 CAGE 행동 공간에 맞게 줄였고, 공격은 능동 공격에서 로그 조사로 바뀌었고, LLM이랑 RL은 통째로 빠짐. 대신 체인 표현이랑 수학적 검증, 실험 분리를 강화했음.

논문에서는 이 차이를 분명하게 구분해야 함. 예선 전체를 구현했다고 쓰면 안 됨. 실제로 구현하고 검증한 것만 써야 한다.
