# RAVEL

RAVEL은 Root-Anchored Verification and Evidence Ledger의 약자다. 핵심 문제는 anomaly 점수, 체인 점수, 책임도, coverage를 각각 만든 뒤 합치는 것이 아니라 공격 조사 자체를 하나의 조건부 증명 과정으로 정의하는 것이다.

## 출발점

공식 detector가 strict validation threshold를 넘긴 node 집합을 \(V_0\)라 한다. RAVEL에서는 각 \(s\in V_0\)가 공격 가설의 root 계정을 연다. Root와 연결되지 않은 정상 provenance chain은 공격 자본을 만들 수 없다.

Validation node loss 집합을 \(\mathcal Z\), test node score를 \(s_v\)라 할 때

\[
p_v=
\frac{1+|\{z\in\mathcal Z:z\ge s_v\}|}
{|\mathcal Z|+1},
\qquad
e_v=\frac12p_v^{-1/2}
\]

로 원자 evidence를 만든다. \(\mathcal Z\)는 공식 Velox와 같은 source·destination 최대 loss reduction으로 구성한다.

## Root-anchored proof

Chain \(c=(P_1,\ldots,P_k)\)의 predicate endpoint 집합을 \(E_i\)라 하고 인접 predicate의 bridge를

\[
J_i=E_i\cap E_{i+1}
\]

라 한다. 다음 조건을 모두 만족할 때만 root \(s\)의 proof로 인정한다.

1. \(s\in\bigcup_iE_i\)
2. 모든 \(E_i\)가 비어 있지 않음
3. 모든 \(J_i\)가 비어 있지 않음

Proof clause는 root gate, 모든 \(E_i\), 모든 \(J_i\)다. Endpoint 선택은 clause 안의 대안이고, clause 사이는 모두 성립해야 하는 직렬 관계다.

한 proof에 clause가 \(m\)개 있고 UUID \(v\)가 \(r_{vc}\)번 나타나면 각 출현의 evidence는

\[
e_v^{1/(mr_{vc})}
\]

다. 따라서 같은 detector score를 여러 predicate에서 반복 사용해도 증거가 복제되지 않는다. Root는 이미 관측됐다는 조건이므로 값 1의 gate로 사용한다. Root를 제거하면 계정 전체가 0이지만 root score의 크기를 다시 likelihood로 곱하지 않는다.

각 endpoint 대안을 균등하게 전개한 realization을 \(h\), edge confidence를 \(a_j\)라 하면 proof capital은

\[
G_{sc}
=
\sum_{h\in\mathcal H_{sc}}
\pi(h)
\left(
\prod_{v\in h\setminus\{s\}}
e_v^{1/r_{vc}}
\prod_ja_j
\right)^{1/m}.
\]

구현은 이 합을 clause별 평균의 곱으로 인수분해한다.

## 조건부 ledger와 node 평가

Root \(s\)에 연결된 proof 집합을 \(\mathcal C_s\)라 한다. RAVEL v2의 ledger는

\[
\mathcal L(x)
=
\frac1{|A|}
\sum_{s\in A}
\frac1{|\mathcal C_s|}
\sum_{c\in\mathcal C_s}G_{sc}(x),
\qquad
A=\{s:\mathcal C_s\ne\varnothing\}.
\]

\(x_v=0\)은 UUID \(v\)를 모든 proof clause에서 제거하는 개입이다. Node 점수는

\[
\Delta_v=\mathcal L(\mathbf1)-\mathcal L(\mathbf1_{-v})
\]

하나뿐이다. Detector term과 chain term을 더하지 않고, flow와 coverage 목적함수도 사용하지 않는다. \(\Delta_v\)가 정확히 같을 때만 원래 \(e_v\), UUID 내림차순으로 동점을 푼다. 공식 seed 수 \(B\)와 같은 수의 node를 선택한다.

## 성질

**Root 조건 불변성.** Root \(s\)의 detector score 크기를 바꿔도 조건부 proof ledger는 변하지 않는다. Root는 likelihood가 아니라 계정의 존재 조건이기 때문이다.

**비연결 불변성.** Root와 겹치지 않거나 인접 bridge가 없는 chain을 추가해도 후보, ledger, node 점수는 변하지 않는다.

**증거 비복제.** UUID가 \(r\)개 clause에서 반복될 때 각 출현 지수의 합은 \(1/m\)이다. 같은 관측은 realization의 단위 단계 성장률에서 한 번만 기여한다.

**정확한 개입.** Ledger를 endpoint 대안별 realization의 비음수 합으로 전개하면 \(\Delta_v\)는 \(v\)를 포함해 제거된 realization capital의 합과 정확히 같다.

**조건부 e-validity 경계.** 서로 다른 원자 evidence가 과거에 조건부로 유효하고 branch allocation이 다음 관측 전에 고정되면 product와 \(m\)-th root의 오목성으로 각 proof realization은 e-variable이다. 현재 replay는 같은 telemetry에서 root와 topology를 만들므로 이 조건이 자동으로 성립하지 않는다. 실험은 선택 대수와 attribution을 검증할 뿐 anytime false-alarm 보장을 입증하지 않는다.

## 보존형 v3

v2가 THEIA에서 chain과 무관한 강한 seed를 너무 쉽게 교체한 뒤, 각 root 계정을 한 단위로 정규화한 보존형을 별도 등록했다.

\[
\mathcal L_3(x)
=
\frac1B
\sum_{s\in V_0}
\frac{Z_s(x)}{Z_s(\mathbf1)}.
\]

분모는 개입 전에 고정하며 제거된 자본은 다른 route에 재분배하지 않는다. 따라서 \(\mathcal L_3(\mathbf1)=1\)이고 모든 root는 최소 \(1/B\)의 개입 손실을 갖는다. 이 성질은 합성 검사에서 성립했지만 CADETS에서는 유효한 교체까지 막아 baseline과 같은 23개만 회수했다. v3는 수학적 음성 결과로 보존하고 최종 성능 방법으로 선택하지 않는다.

## Proof-mass transport v4

V3의 root floor는 모든 root를 최종 보고에 남겨 유효한 proof node 교체까지 막았다. V4는 root를 보존하는 대신 root가 소유한 조사 슬롯을 자기 singleton proof 또는 연결된 chain proof node 하나로 운반한다.

Root 집합을 \(R\), 공식 seed 예산을 \(B=|R|\), root \(s\)의 admitted route를 \(\mathcal C_s\)라 한다. V2의 조건부 route capital을 \(G_{sc}\), node \(v\) 제거 뒤의 capital을 \(G_{sc}^{-v}\)라 하면 간선 utility는

\[
u_{ss}
=
\frac{e_s}{1+|\mathcal C_s|},
\qquad
u_{sv}
=
\frac{1}{1+|\mathcal C_s|}
\sum_{c\in\mathcal C_s}
\left(G_{sc}-G_{sc}^{-v}\right)
\]

이다. 첫 식은 detector root 하나만 포함하는 singleton proof이고 두 번째 식은 root를 조건으로 고정한 route들의 정확한 intervention loss다. 다른 공식 root는 \(s\)의 비root 후보에서 제외한다.

각 root는 \(1/B\)의 질량을 공급하고 각 node의 용량도 \(1/B\)다. 선택은 다음 최대가중 matching이다.

\[
\max_{x\in\{0,1\}^{R\times V}}
\sum_{s\in R}\sum_{v\in V}u_{sv}x_{sv}
\]

\[
\text{s.t.}\quad
\sum_v x_{sv}=1,\qquad
\sum_s x_{sv}\le1.
\]

구현은 모든 비음수 간선을 utility 내림차순으로 처리하는 greedy maximal matching을 사용한다. 모든 root에는 다른 계정이 사용할 수 없는 양의 singleton 간선이 있으므로 결과는 정확히 \(B\)개의 서로 다른 node를 반환한다.

**질량 보존.** 각 root의 유출 질량은 \(1/B\)이고 각 node의 유입 질량은 최대 \(1/B\)이므로 전체 운반 질량은 정확히 1이다.

**Root 비소외성.** 모든 root는 matching 간선 하나를 소유한다. Chain이 없거나 모든 확장 utility가 0이면 해당 root의 singleton proof가 선택된다.

**조사 비중복성.** Node capacity 때문에 같은 UUID가 여러 root의 최종 증거 슬롯을 동시에 소비할 수 없다. Proof 내부의 반복 evidence는 기존 지수 보정으로, proof 사이의 조사 중복은 matching으로 각각 차단한다.

**예산 정확성.** 모든 root의 공급이 하나의 서로 다른 node에 배정되므로 선택 수는 공식 root 수 \(B\)와 같다.

**근사 보장.** 비음수 최대가중 matching에서 내림차순 greedy가 선택한 각 간선은 최적해 간선 최대 두 개와 충돌한다. 각 충돌 간선의 가중치는 greedy 간선보다 크지 않으므로 greedy utility는 최적 utility의 최소 \(1/2\)이다. 이는 악성 node 회수율 보장이 아니라 등록된 proof utility 최적화의 계산 보장이다.

**단조변환 불변성.** Test score와 validation calibration에 같은 엄격 단조변환을 적용하면 conformal rank와 \(e_v\)가 동일하므로 모든 route, 간선 utility와 matching이 동일하다.

### V4 label-free 구조 판정

V4는 CADETS와 THEIA에서 예산, degree와 질량 보존을 모두 만족했지만 비root transport를 하나도 만들지 못했다. Root singleton utility와 조건부 proof utility가 서로 다른 scale에 있었기 때문이다. Label evaluator를 실행하지 않고 v4를 구조적으로 기각했다.

## Conditional transport v5

Root는 이미 공식 detector의 top-\(B\) 선택을 통과해 account를 연 조건이다. V5는 이 관측을 transport 단계에서 다시 점수화하지 않는다. 자기 간선은 chain proof가 없을 때의 hold fallback이고 utility는 0이다. 비root 간선은 account route capital의 상대 intervention loss다.

\[
u^{(5)}_{ss}=0,
\qquad
u^{(5)}_{sv}
=
\frac{
\sum_{c\in\mathcal C_s}
(G_{sc}-G_{sc}^{-v})
}{
\sum_{c\in\mathcal C_s}G_{sc}
}.
\]

따라서 \(0\le u^{(5)}_{sv}\le1\)이고 root score 크기를 바꿔도 그 root가 소유한 account와 transport edge는 변하지 않는다. Utility가 1이면 해당 node를 삭제했을 때 account의 모든 양의 proof realization이 사라지고, 역도 성립한다. Utility가 0이면 그 node를 포함하는 양의 realization이 없다. 다른 root가 해당 account의 proof endpoint로 등장하면 그 node의 calibrated evidence는 유지되므로 전역 transport graph와 matching의 불변성은 root-separated account에서만 성립한다. Matching과 질량 제약은 v4와 동일하다. V5는 proof가 존재하면 detector root의 조사 슬롯을 가장 큰 조건부 fracture를 만드는 node로 운반하고, proof가 없으면 root를 그대로 유지한다. 이 우선순위는 별도 mixing weight가 아니라 root conditioning의 직접적인 결과다.

비root UUID 집합 \(A\)를 한꺼번에 삭제한 fracture를 \(F_s(A)\)로 확장하면, 각 양의 proof realization은 support가 \(A\)와 교차할 때만 제거된다. 따라서 \(F_s\)는 realization capital을 가중치로 갖는 weighted coverage 함수이며 정규화·단조·submodular다. V5와 V6의 간선 utility는 그 singleton 값 \(F_s(\{v\})\)다. 이 성질은 다중 node 선택의 가능한 확장을 설명하지만, 최종 등록 selector는 root마다 한 slot만 배정하므로 singleton utility만 사용한다.

Label-free 구조 검사에서 CADETS는 1,103개 슬롯 중 9개, THEIA는 503개 중 13개를 proof node로 운반했다. 두 manifest 모두 root degree 1, node degree 최대 1, 정확한 예산과 총 질량 1을 만족했다. 이 검사는 선택이 비자명하다는 것만 확인하며 malicious-node metric은 계산하지 않았다.

## Exact transport v6

V5의 greedy matching은 비음수 최대가중 matching의 \(1/2\) 근사를 보장하지만, 먼저 선택한 proof node가 다른 root의 더 좋은 조합을 막을 수 있다. V6는 utility와 feasible set을 그대로 두고 다음 정수계획의 최적해를 계산한다.

\[
x^\star\in\arg\max_x
\sum_{s\in R}\sum_{v\in V}u^{(5)}_{sv}x_{sv}
\]

\[
\text{s.t.}\quad
\sum_vx_{sv}=1,\qquad
\sum_sx_{sv}\le1,\qquad
x_{sv}\in\{0,1\}.
\]

모든 root에 고유한 0-utility hold node가 있으므로 크기 \(B\)의 matching은 항상 존재한다. \(u_{\max}=\max_{sv}u^{(5)}_{sv}\)와 \(c_{sv}=u_{\max}-u^{(5)}_{sv}\)를 두면 모든 feasible 해가 정확히 \(B\)개 간선을 가지므로 utility 최대화와 cost 최소화가 동치다. 구현은 sparse successive shortest augmenting path로 \(B\) 단위 흐름을 완전히 보내며, 간선 비용이 같을 때 정렬된 root와 node 순서를 사용한다.

합성 3-root 그래프의 729개 weight 조합에서 전수조사 optimum과 모두 일치했다. Root 2–15개와 공유 node 1–20개를 갖는 seeded random sparse graph 2,000개에서도 SciPy의 독립 linear assignment 목적값과 모두 일치했다. 실제 label-free 구조 검사에서 CADETS objective는 `3.176187`에서 `3.178597`로 증가했고 proof transport 수는 9개로 같았다. THEIA objective는 `4.130598`로 같고 proof transport 수는 13개였다. 실행 시간은 각각 6.10초와 12.18초였다. 이 수치는 등록된 proof utility의 계산 최적성만 보이며 악성 node 회수 최적성을 뜻하지 않는다.

## Certified abstention

V6 실패의 핵심은 0-valued hold 때문에 작은 양의 fracture도 detector root를 교체한다는 점이다. 이를 label이나 조정 계수 없이 제한하기 위해 각 비root 후보 간선이 모든 route의 완전 fracture를 구조적으로 증명하는지 검사한다.

Root \(s\)의 route \(c\)에서 root gate를 제외한 endpoint·bridge clause family를 \(\mathcal Q_{sc}\)라 한다. 선택 node \(v\)의 universal-cut 조건은

\[
\Gamma(s,v)
=
\bigwedge_{c\in\mathcal C_s}
\bigvee_{Q\in\mathcal Q_{sc}}
[Q=\{v\}]
\]

이다. 구현은 각 route마다 singleton clause의 index를 모두 출력한다. 모든 route ID가 적어도 하나의 index를 가지는지가 독립 verifier의 판정 조건이다.

**완전 fracture의 필요충분조건.** 모든 원자 evidence와 admitted route edge capital이 양수이면

\[
\Gamma(s,v)=1
\quad\Longleftrightarrow\quad
u^{(5)}_{sv}=1.
\]

삭제 뒤 route 곱이 0이 되려면 clause 평균 중 하나가 0이어야 한다. 원자 evidence가 양수이고 삭제 대상이 하나뿐이므로 이는 삭제 전 clause가 정확히 \(\{v\}\)였을 때와 동치다. Account utility가 1이려면 양의 모든 route가 0이 되어야 하므로 route별 조건의 논리곱이 된다.

첫 v1은 v6가 root \(s\)를 \(v\ne s\)에 배정했을 때 \(\Gamma(s,v)=1\)인 간선만 유지하고 나머지를 \(s\mapsto s\)로 되돌렸다. 그러나 v6는 fractional fracture 합을 최대화하므로 node 충돌 때문에 후보 그래프의 완전-fracture 간선을 선택하지 않을 수 있다. V1은 선택 뒤 필터이므로 이 간선을 복구하지 못한다.

V2는 인증 후보 그래프

\[
E^\Gamma
=
\{(s,s):s\in R\}
\cup
\{(s,v):v\ne s,\ \Gamma(s,v)=1\}
\]

를 먼저 만든다. V2는 proof 간선 utility를 1, hold utility를 0으로 둔 exact matching으로 인증 transport 수만 최대화했다. 그러나 같은 최대 개수 해가 여러 개면 UUID 순서가 어느 이상 증거를 유지할지 임의로 결정한다.

V3는 후보 node의 conformal evidence를 동률 해의 2차 목적으로 추가했지만, 개발 데이터에서 원래 v6 해와의 불필요한 교환을 막지 못했다. 인증은 v6 해를 구조 feasible set으로 사영하는 연산이므로 V4는 최소왜곡 원리를 명시한다. 후보 node의 conformal evidence를 \(e_v\ge0\), 후보 그래프의 최댓값을 \(e_{\max}\), v6 exact matching을 \(M_6\)라 하고

\[
\bar e_v=
\begin{cases}
e_v/e_{\max} & e_{\max}>0,\\
0 & e_{\max}=0
\end{cases},
\qquad
\rho_{sv}
=(B+1)^2[v\ne s]
+(B+1)[(s,v)\in M_6]
+\bar e_v
\]

를 간선 순위로 사용한다. Exact matching은 \(\sum_{(s,v)\in M}\rho_{sv}\)를 최대화하지만 출력 certificate의 proof 값은 1, hold 값은 0으로 유지해 구조 목적과 tie-break를 분리한다.

**실행 가능성 보존.** 모든 root는 자기 private hold를 가지며 detector root는 다른 account의 proof 후보에서 제외된다. 따라서 \(E^\Gamma\)에는 항상 크기 \(B\)의 matching이 있고, exact 해의 root degree는 1, node degree는 최대 1, 예산은 정확히 \(B\), 질량은 1이다.

**비부분적 transport.** 최종 출력의 모든 비root 간선은 상대 fracture가 정확히 1이다. 인증되지 않은 계정은 detector root를 유지하므로 양수지만 불완전한 fracture가 root를 교체하는 경로가 없다.

**사전식 최적성.** 크기 \(B\)인 두 matching 사이에서 정규화 evidence 합의 차이는 절댓값이 최대 \(B\)이므로 agreement 하나의 \(B+1\) 차이를 뒤집을 수 없다. Agreement 하위 목적 전체의 최대 차이는 \(B(B+1)+B=(B+1)^2-1\)이므로 인증 간선 하나의 \((B+1)^2\) 차이도 뒤집을 수 없다. 따라서 V4는 ① 인증 transport 수, ② v6 assignment 일치 수, ③ 선택 UUID의 conformal evidence 합을 정확한 사전식 순서로 최대화한다. 두 상계는 조정한 mixing coefficient가 아니라 우선순위를 증명하는 최소 정수 상계다. 이는 악성 UUID 최적성 주장이 아니라 fractional fracture 해를 proof-carrying feasible set에 최소왜곡으로 사영하는 abstention 연산이다.

**Projection 일관성.** V6가 이미 선택한 인증 간선들의 수가 \(E^\Gamma\)에서 가능한 최대 인증 수와 같다면, 그 간선들과 admissible source hold를 모두 유지하는 해가 2차 agreement의 상계를 달성한다. V4는 이들을 버릴 수 없으며 V1의 filter-and-hold 출력과 같아진다. 반대로 전체 인증 그래프에 더 큰 cardinality 해가 있을 때만 1차 목적이 source agreement를 희생한다.

**고정 예산 안전성의 불가능성.** Root가 detector top-\(B\)이면 root 밖의 모든 후보 evidence는 모든 root evidence 이하이므로 비자명한 교체는 detector evidence를 약하게 낮춘다. 더 일반적으로 label을 사용하지 않는 동일 크기 출력 \(S\ne R\)에 대해 악성 집합을 \(Y=R\setminus S\)로 두면 baseline은 \(|Y|>0\)개, \(S\)는 0개를 회수한다. \(Y=S\setminus R\)로 두면 방향이 반대다. 따라서 proof fracture와 actor label 사이의 추가 가정 없이 비자명한 fixed-budget selector가 모든 label에서 baseline recall 비감소를 보장할 수 없다.

검사는 label이나 scalar threshold를 사용하지 않는다. 구조 인증은 score 크기와 무관하고, 2차 tie-break만 이미 동결된 validation conformal evidence를 사용한다. 모든 proof candidate에 대해 admitted route와 endpoint·bridge clause를 인덱싱하고, 인증된 희소 그래프에서 \(B\)번 증강하므로 최악 시간은 후보-account clause incidence 검사와 exact matching 비용의 합이다. Witness 검증은 직렬화된 route·clause index 수에 선형이다.

## 개발 결과

| 방법 | CADETS, \(B=1103\) | THEIA, \(B=503\) |
|---|---:|---:|
| 공식/local | 23 | 16 |
| FlowSub | 29 | 25 |
| BEAR v1 | 26 | 16 |
| RAVEL v2 | 28 | 17 |
| RAVEL v3 | 23 | 실행 중단 |
| RAVEL v4 | label 미사용 구조 검사만 허용 | label 미사용 구조 검사만 허용 |
| RAVEL v5 | label 미사용 구조 검사만 허용 | label 미사용 구조 검사만 허용 |
| RAVEL v6 | label 미사용 구조 검사만 허용 | label 미사용 구조 검사만 허용 |

RAVEL v2는 CADETS의 세 공격 파일에서 `2,17,5→3,21,7`로 모두 개선했다. THEIA에서는 aggregate가 `16→17`이지만 공격별로 `12,4→5,12`라서 강건한 전이라고 볼 수 없다. CADETS와 THEIA는 이미 앞선 방법 개발에서 label을 관측했으므로 모두 개발 진단이다.

최종 미관측 H051에서 Velox, FlowSub, v6, V4의 512-node 악성 UUID 회수는 각각 `4, 8, 2, 3`이다. V4는 v6의 손실을 일부 복구했지만 Velox보다 1개 적어 등록한 네 조건을 모두 실패했다. 네 인증 이동 중 세 개는 benign→benign이고 하나는 malicious root→unlabeled target이다. Singleton witness는 이 마지막 target이 두 proof route를 완전히 끊음을 인증하지만 actorID 안전성은 인증하지 못한다.

## Novelty 경계

Conformal e-value, evidence semiring, graph intervention, attack-tree 계산은 각각 기존 연구가 있다. RAVEL의 후보 기여는 이 요소들의 병렬 결합이 아니라 다음 단일 정의다.

> Detector alert가 소유한 조건부 증명 계정에서 typed provenance hierarchy를 대안과 직렬 clause로 전개하고, 공격 체인 복원과 node 우선순위를 동일 proof ledger의 정확한 개입 손실로 정의한다.

동일 formulation의 선행 연구가 없다는 결론은 현재 검색 범위의 결과일 뿐 최초 사용 주장은 아니다. 새로운 performer에서 수정 없는 검증이 끝나기 전에는 RAVEL을 최종 성능 방법으로 주장하지 않는다.

V4의 추가 novelty 경계는 detector와 chain 점수의 새 가중합이 아니라, root-conditioned exact intervention을 uniform-capacity transport edge로 바꾸어 공격별 조사 슬롯 보존과 UUID 중복 방지를 하나의 matching constraint로 정의한 데 있다. Maximum-weight matching과 greedy 근사 자체는 기존 결과이며 최초 알고리즘으로 주장하지 않는다.

V6의 exact matching도 표준 최적화 알고리즘이므로 독립적인 novelty로 주장하지 않는다. 역할은 RAVEL의 새 formulation과 계산 근사를 분리해, 외부 성능 실패를 greedy 오차가 아니라 proof utility와 malicious-node utility의 불일치로 해석할 수 있게 하는 것이다.
