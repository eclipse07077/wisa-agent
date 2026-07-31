# 최종 공·방 에이전트 방법

지금 실제 코드랑 실험에 들어간 방법만 정리한 문서. 예선에서 계획만 했던 LLM commander나 RL tactician은 제외했고 개발 중간에 버린 FlowSub·BEAR·RAVEL 구버전도 최종 방법 설명에선 뺐음.

현재 최종 구성은 세 개.

1. 공통 evidence–predicate–chain 코어
2. CAGE 방어 v12
3. TC grounded trace랑 RAVEL-C 공격 조사

## 1. 공통 코어

### Evidence

모든 관측을 같은 구조로 바꿈.

| 필드 | 의미 |
|---|---|
| `timestamp` | 관측 시각이나 순서 |
| `layer` | 데이터에서 확인된 역할 계층 |
| `source` | 관측을 만든 수집기 |
| `subject` | 행동 주체 |
| `relation` | 관측된 동작이나 관계 |
| `object` | 대상 자산 |
| `context` | 세션·구역·프로세스 같은 연결 정보 |
| `confidence` | 관측 신뢰도 |
| `provenance` | 출처랑 신뢰 경계 |

데이터에 없는 필드는 정상으로 채우지 않고 `unknown`으로 둠. 외부 payload가 자기가 안전하다고 주장해도 그 값은 신뢰 안 함. 신뢰 경계는 인증된 adapter가 정함.

공통 코어에는 데이터셋 이름이나 performer 이름이나 정답 UUID나 고정 hostname이나 CAGE action index가 없음. CAGE랑 TC 차이는 adapter에서만 처리.

### Predicate

Evidence를 다섯 단계로 바꿈.

1. `ingress`: 접근점이나 통신 경로가 생김
2. `trust_break`: 신원·권한·정책·무결성 관계가 깨짐
3. `lifecycle`: 실행·세션·권한 상승·지속성 변화가 생김
4. `mission_effect`: 서비스나 임무에 실제 영향이 생김
5. `response`: 탐지·decoy·격리·복구 행동이 생김

예선 L0~L6을 그대로 복사한 건 아님. 계층 이름을 고정하지 않고 관측이 하는 역할로 바꾼 것. CAGE에서는 zone·host·service·session이 들어가고 TC에서는 process·file·netflow 관계가 들어감.

### Normal profile

정상 구간에서 세 가지를 만듦.

- 개체랑 relation이 얼마나 자주 나오는지
- 어떤 시간 순서랑 동시 발생이 정상인지
- 어떤 상태 전이가 허용되는지

공격 label은 정상 profile이랑 계층을 만들 때 안 씀. TC raw event도 곧바로 공격 predicate로 보지 않음. 정상 profile을 벗어난 event만 seed로 쓰고 같은 process의 18초 session에서 주변 전이를 다시 모음.

### Chain

Predicate 두 개 사이 edge는 예선 가중치를 그대로 씀.

\[
E_{ij}=0.30T_{ij}+0.30J_{ij}+0.25G_{ij}+0.15M_{ij}.
\]

- `T`: 시간 근접성
- `J`: shared context Jaccard
- `G`: 공격 단계가 앞으로 진행되는 정도
- `M`: 실제 영향이랑 연결되는 정도

관측 불가능한 항목은 0점으로 안 넣음. 남은 항목끼리 가중치를 다시 나눔. Edge threshold는 0.58이고 최대 길이는 5. 시간 창은 18초.

일반 체인은 predicate 세 개 이상이 필요하고 서로 다른 단계도 세 개 이상이어야 함. 끝은 `mission_effect`나 `response`여야 함.

체인 점수랑 node 점수는 분리. 좋은 체인에 우연히 들어갔다는 이유만으로 모든 node를 공격 후보로 올리지 않음. Node 기여도는 그 node가 실제로 들어간 predicate confidence로 제한함.

## 2. Grounded trace 공격 조사

Grounded trace는 raw provenance log에서 공격 체인이랑 조사 node를 만드는 front-end.

처리 순서는 이렇다.

1. 정상 structure·trace·path profile 생성
2. Validation 0.995 quantile로 anomaly threshold 고정
3. Threshold를 넘은 event를 seed로 선택
4. 같은 process의 18초 session 복원
5. Session 안 event를 5단계 predicate로 집계
6. `ingress`나 `trust_break`에서 bounded best-first search 시작
7. 유효 chain만 남김
8. Chain attribution이랑 node ranking을 따로 출력

Event anomaly는 이 식.

\[
A(e)=0.50A_{\mathrm{struct}}(e)+0.30A_{\mathrm{trace}}(e)+0.20A_{\mathrm{path}}(e).
\]

Test label은 threshold나 chain 생성에 안 들어감. 최종 출력이 고정된 다음 metric 계산에만 씀.

CADETS랑 THEIA E3에선 같은 조사량에서 악성 node를 더 많이 찾았음. ClearScope E5에선 반대로 줄었음. 이 방법은 path랑 temporal session이 보존된 로그에선 쓸 만했지만 CDM20 표현 이동까지 버티진 못했음.

코드는 `src/wisa_agent/tc/cdm_agent.py`. 공통 chain 로직은 `src/wisa_agent/method/`에 있음.

## 3. 방어 v12

방어는 `Perceive → Detect → Decide → Respond → Recover` 순서.

### Risk

규칙 기반 위험도는 confidence `q`와 severity `v`와 chain correlation `c`와 asset criticality `k`를 사용.

\[
R_{\mathrm{rule}}=0.35q+0.25v+0.25c+0.15k.
\]

정상 범위 이탈 `a`를 계산할 수 있으면 이 값도 같이 봄.

\[
R_{\mathrm{deviation}}=0.50a+0.30c+0.20k.
\]

둘 중 큰 값을 사용. 기본 구간은 아래처럼 시작하지만 실제 행동은 scope 제약을 한 번 더 통과해야 함.

| 위험도 | 기본 행동 |
|---|---|
| 0.00~0.49 | monitor |
| 0.50~0.69 | `Analyse`나 `DeployDecoy` |
| 0.70~0.84 | 임시 격리 검토 |
| 0.85~1.00 | `Remove`나 `Restore` 검토 |

### Evidence scope와 action scope

v12 핵심. 강한 행동 범위가 확인된 evidence 범위보다 커지면 안 됨.

- 한 계층 근거만 있으면 `Analyse`나 decoy로 정보 더 모음
- 두 계층 이상이 연결되면 부분 조치가 체인을 실제로 끊는지 확인
- Process랑 connection이 같이 확인되면 `Remove` 반복보다 `Restore` 우선
- Mission effect가 생긴 뒤엔 정상 상태 복구를 먼저 봄
- 중요 자산일수록 강한 행동 전에 독립 evidence를 더 요구

v6~v11이 실패한 가장 큰 이유는 위험 점수보다 행동 범위였음. Process 일부만 지웠는데 connection이 남거나 같은 대상에 `Remove`가 반복됐음. v12는 점수 재튜닝이 아니라 이 구조를 바꾼 버전.

### Recurrence watch

API ACK만 보고 대응 성공으로 처리 안 함. 행동 뒤 일정 시간 동안 같은 process랑 connection이 다시 나오는지 확인. Effect 확인이 끝나기 전엔 같은 대상에 같은 수준의 강한 행동을 반복하지 않음.

공격자가 약한 evidence를 일부러 만들어서 방어의 고비용 복구를 계속 유도하는 recovery-reflex도 여기서 막음.

### Dynamic decoy

Episode 시작할 때 decoy 전부 배치 안 함.

- 위협이 있으면 같은 zone에서 다음 전이 후보에 먼저 배치
- 위협이 없으면 역할별 coverage 빈칸을 하나씩 채움
- Decoy 접촉은 `trust_break` predicate로 다시 입력

이건 예선의 fake ROS2·DDS·shell 허니팟 전체를 구현한 게 아님. CAGE `DeployDecoy` 안에서 위치랑 시점만 고르는 정책.

### Recovery

강한 행동 뒤 정상 상태가 돌아왔는지 확인. Process 제거만 반복하지 않고 서비스 복원이 필요한 상황에선 `Restore` 사용. 약한 후속 신호 하나만으로 보호 상태를 바로 낮추지도 않음.

코드는 `src/wisa_agent/cage/report.py`. Agent 등록은 `src/wisa_agent/cage/teams.py`.

## 4. RAVEL-C 공격 조사

RAVEL-C는 detector root랑 grounded chain을 받아서 고정 조사 예산 안에서 node를 다시 배정하는 head. 공격 실행기는 아님.

### Proof account

Detector root 하나가 account 하나를 엶. Root랑 겹치는 typed chain만 받음. Chain predicate endpoint랑 인접 predicate를 이어주는 continuity bridge를 clause로 만듦.

Root `s`의 route family를 `C_s`라고 하고 route `c` 안에서 UUID 후보 clause를 `Q_sc`라고 둠. UUID `v` 하나를 지웠을 때 모든 route에서 singleton clause가 하나 이상 깨지면 complete fracture.

\[
\Gamma(s,v)=\bigwedge_{c\in\mathcal C_s}\bigvee_{Q\in\mathcal Q_{sc}}\mathbf 1[Q=\{v\}].
\]

모든 route factor가 양수일 때 `Γ(s,v)=1`이랑 account complete fracture가 필요충분. 직접 UUID 삭제 계산이랑 route-index 구현이 같은지도 테스트로 확인했음.

### Exact allocation

Root마다 analyst slot 하나. Node 하나는 root 하나에만 배정 가능. 총 출력은 detector budget `B`랑 정확히 같음.

목표 우선순위는 세 개.

1. Certified transport 수 최대화
2. Fractional proposal이랑 달라지는 slot 수 최소화
3. 앞이 같으면 conformal evidence 최대화

정수 weight는 이 식.

\[
\omega_{sv}=(B+1)^2\mathbf 1[v\neq s]+(B+1)\mathbf 1[(s,v)\in M_6]+\bar e_v.
\]

`(B+1)^2`랑 `B+1` 상계 때문에 아래 목표가 위 목표를 뒤집을 수 없음. Exact matching 구현은 729개 작은 전수 그래프랑 2,000개 seeded sparse graph에서 독립 solver랑 맞았음.

### 보장하는 것과 못 하는 것

보장하는 건 proof account의 complete fracture랑 예산·중복 제약이랑 목적 우선순위. ActorID 정확도나 recall은 보장 안 함.

Label을 안 보고 detector root 집합 `R`을 다른 같은 크기 집합 `S`로 바꾸면 모든 가능한 malicious set에서 recall 비감소를 보장할 수 없음. `R\S`를 정답으로 두면 교체가 나빠지고 `S\R`을 정답으로 두면 좋아짐. 추가 label–evidence 가정 없이는 nontrivial swap safety가 불가능하다는 뜻.

H051에서 실제로 Velox 4개를 RAVEL-C 3개로 낮췄음. Structural certificate는 맞았지만 actor 의미가 안 맞았던 사례.

코드는 `src/wisa_agent/tc/ravel.py`랑 `src/wisa_agent/tc/cert.py`. 실행은 `experiments/cert.py`. 평가는 `experiments/cert_eval.py`.

## 5. 오케스트레이션

지금 오케스트레이터는 LLM이 아님. 정해진 단계랑 계약으로 각 모듈을 호출하는 결정론적 구조.

공격 조사 쪽 순서.

`Profiler → Predicate Miner → Chain Builder → Detector Interface → RAVEL-C → Evaluator`

방어 쪽 순서.

`Observation Adapter → Evidence Builder → Chain Correlator → Risk Policy → Scope Guard → Action → Effect Watch`

같은 입력이면 같은 출력이 나와야 하고 중간 결과를 전부 저장함. LLM은 나중에 가설 생성이나 설명 보조로 넣을 수는 있어도 최종 행동권은 안 줌.

## 6. 개발 중 버린 방법

파일은 없애지만 왜 버렸는지는 남겨둠.

| 방법 | 해본 것 | 최종에서 빠진 이유 |
|---|---|---|
| FlowSub | Counterfactual responsibility랑 submodular fixed-budget 교환 | E3 개발 결과는 좋았지만 새 holdout 성능 근거가 없고 flow 항 추가 기여도 확인 안 됨 |
| BEAR | Branch-aware evidence allocation | 조건부 유효성 가정을 실제 telemetry가 만족한다고 증명 못 함 |
| RAVEL v1~v3 | 단일 ledger랑 root account | Root 유지랑 actor 의미가 어긋났고 THEIA에서 교체가 불안정했음 |
| RAVEL v4~v6 | Proof-mass transport랑 exact matching | 구조 최적화는 됐지만 H051 actor recall이 깨졌음 |
| 방어 v6~v11 | Risk 조정과 temporal belief와 정적 utility | 행동 범위가 evidence 범위를 덮지 못해서 reward가 나빠졌음 |

중간 방법 결과는 raw `results/`랑 git history에 남아 있음. 논문 최종 방법으로 설명할 건 grounded trace와 방어 v12와 RAVEL-C뿐.

## 7. 과적합 방지 규칙

- Test label로 threshold나 epoch나 seed나 가중치 안 고름
- 데이터셋 이름이나 정답 UUID나 고정 hostname 규칙을 공통 코어에 안 넣음
- 결과가 나쁘다고 같은 final split에서 방법 다시 고르지 않음
- 개발에 사용한 H501·H201은 외부 검증이라고 안 부름
- H051 결과 뒤 RAVEL-C 방법이나 성공 조건 안 바꿈
- CAGE는 같은 seed끼리 paired 비교
- 실패 버전이랑 불리한 결과도 보존

세부 split이랑 hash랑 재현 명령은 `docs/protocol.md`에 있음.
