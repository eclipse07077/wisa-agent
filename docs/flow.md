# FlowSub

## 문제 정의

공식 detector가 만든 node score만 상위에서 자르면 서로 관련 없는 고점 node가 남고, 체인의 모든 endpoint를 합치면 긴 process session이 조사 집합을 팽창시킨다. FlowSub는 detector가 정한 조사 예산을 늘리지 않으면서, 그 예산 안에서 anomaly evidence와 causal-chain evidence를 함께 보존하는 node 집합을 선택한다.

Detector score universe를 \(U\), strict validation threshold를 넘은 seed 집합을 \(V_0\), seed와 겹치는 동결 체인을 \(\mathcal C\)라 한다. 후보 집합은

\[
V=V_0\cup\bigcup_{c\in\mathcal C}\bigcup_{p\in c}E_p
\]

에서 공식 score universe 밖의 node를 제외한 집합이고 예산은 \(B=|V_0|\)로 고정한다. \(E_p\)는 predicate \(p\)의 실제 provenance endpoint다.

## Noisy-OR 체인 신뢰도

체인 \(c=(p_1,\ldots,p_m)\)에서 node \(v\)가 predicate \(p_i\)에 제공한 local anomaly evidence를 \(x_{vi}\in[0,1]\)라 한다. Predicate reliability는 독립 evidence 중 하나 이상이 유효할 확률로 해석한 noisy-OR다.

\[
r_i=1-\prod_{v\in E_i}(1-x_{vi})
\]

연속 predicate의 endpoint 교집합이 모두 비어 있지 않을 때, edge confidence \(e_i\)를 포함한 chain reliability를

\[
R(c)=\left(\prod_{i=1}^{m}r_i\right)
\cdot\left(\prod_{i=1}^{m-1}e_i\right)
\]

로 정의한다.

Node \(v\)를 모든 predicate endpoint에서 제거한 반사실 체인을 \(c\setminus v\)라 한다. 제거로 predicate가 비거나 연속 endpoint 교집합이 사라지면 \(R(c\setminus v)=0\)이다. Counterfactual responsibility는

\[
n_{vc}=
\begin{cases}
1-\dfrac{R(c\setminus v)}{R(c)},&R(c)>0,\\
0,&R(c)=0
\end{cases}
\]

이다.

**정리 1.** 모든 node와 chain에 대해 \(0\le n_{vc}\le1\)이다.

**증명.** Node 제거는 noisy-OR의 입력 항을 제거하거나 chain compatibility를 끊는다. 따라서 \(0\le R(c\setminus v)\le R(c)\)이고, \(R(c)>0\)이면 비율은 \([0,1]\)에 있다. \(R(c)=0\)인 경우 정의에 의해 0이다. \(\square\)

## 보존 causal flow

연속 predicate의 공유 endpoint를 \(J_i=E_i\cap E_{i+1}\)라 한다. 공유 node의 양쪽 local evidence 기하평균을

\[
z_{vi}=\sqrt{x_{vi}x_{v,i+1}}
\]

로 두고, edge confidence를 공유 node에 다음과 같이 배분한다.

\[
\phi_{vi}
=
e_i\frac{z_{vi}}{\sum_{u\in J_i}z_{ui}}.
\]

분모가 0이면 \(J_i\)에 균등 배분한다. Node의 정규화된 chain flow는

\[
h_{vc}
=
\frac{\sum_{i:v\in J_i}\phi_{vi}}
{\sum_{i=1}^{m-1}e_i}.
\]

**정리 2.** 유효 체인에서 \(h_{vc}\ge0\)이고 \(\sum_vh_{vc}=1\)이다.

**증명.** 각 edge에서 \(\sum_{v\in J_i}\phi_{vi}=e_i\)다. 모든 edge에 대해 합산하고 \(\sum_ie_i\)로 나누면 1이다. 각 항이 비음수가 아니므로 \(h_{vc}\ge0\)이다. \(\square\)

**정리 3.** 양의 \(z_{vi}\)를 가진 endpoint 사이의 배분 비율이 local evidence 비율과 같고, edge evidence가 보존되며, 영 evidence endpoint에 양의 질량을 주지 않는 배분은 \(\phi_{vi}\)로 유일하다. 모든 \(z_{vi}=0\)인 경우 endpoint 대칭성을 추가하면 균등 배분이 유일하다.

**증명.** 양의 evidence를 가진 임의의 \(u,v\)에 대해 비율 조건은 \(\phi_{vi}/\phi_{ui}=z_{vi}/z_{ui}\)이므로 공통 상수 \(k\)에 대해 \(\phi_{vi}=kz_{vi}\)다. 보존 조건 \(\sum_v\phi_{vi}=e_i\)에서 \(k=e_i/\sum_vz_{vi}\)가 강제된다. 모든 evidence가 0이면 대칭성에 의해 모든 질량이 같고 보존 조건에 의해 각각 \(e_i/|J_i|\)다. \(\square\)

이 보존식은 endpoint가 많은 session에서 edge evidence를 복제하지 않고 나누므로 dependency explosion을 직접 억제한다.

## Axiomatic node utility

Official detector score \(s_v\)를 같은 test universe 안의 empirical percentile로 바꾼다.

\[
a_v=\frac{|\{u\in U:s_u\le s_v\}|}{|U|}.
\]

이는 label을 사용하지 않으며 score의 단조 변환에 대해 순위를 보존한다.

**정리 4.** Official score에 임의의 strictly increasing 함수 \(f\)를 적용해도 \(a_v\)와 FlowSub의 선택 결과는 변하지 않는다.

**증명.** \(f\)가 strictly increasing이면 \(s_u\le s_v\)와 \(f(s_u)\le f(s_v)\)가 동치다. 따라서 empirical CDF의 분자와 분모가 모든 node에서 같고 \(a_v\)가 보존된다. 나머지 causal evidence와 tie-break는 official score의 수치 크기가 아니라 동결 체인에만 의존하므로 모든 marginal gain과 선택 순서가 같다. \(\square\)

Counterfactual responsibility와 causal flow 중 하나 이상이 node를 지지할 확률을 noisy-OR로 결합한다.

\[
c_{vc}=1-(1-n_{vc})(1-h_{vc}).
\]

Detector evidence와 causal evidence를 같은 중요도로 만족시키는 Nash product의 단조변환으로 node-chain utility를

\[
q_{vc}=\sqrt{a_vc_{vc}}
\]

로 둔다. 이 식에는 benchmark별 학습 가중치가 없다.

## 부분모듈러 선택

\(A_B\)를 후보 중 상위 \(B\)개 anomaly percentile의 합으로 두고 detector 보존 항을

\[
D(S)=\frac{\sum_{v\in S}a_v}{A_B}
\]

로 정의한다. Chain coverage는

\[
G_c(S)=
\frac{
1-\exp\left(-\sum_{v\in S}q_{vc}\right)
}{
1-\exp\left(-\sum_{v\in V}q_{vc}\right)
}
\]

이고, \(\omega_c=score(c)/\sum_{d\in\mathcal C}score(d)\)다. 최종 목적함수는

\[
F(S)=D(S)+\sum_{c\in\mathcal C}\omega_cG_c(S),
\qquad |S|\le B.
\]

두 항은 각각 \([0,1]\)로 정규화되어 별도 혼합 가중치가 필요 없다.

**정리 5.** \(F\)는 normalized, nonnegative, monotone submodular set function이다.

**증명.** \(D\)는 nonnegative modular function이다. 각 \(G_c\)에서 \(Q_c(S)=\sum_{v\in S}q_{vc}\)는 nonnegative modular이고 \(g(x)=1-e^{-x}\)는 nondecreasing concave다. 직접 marginal을 쓰면

\[
\Delta_vG_c(S)
=
\frac{
e^{-Q_c(S)}(1-e^{-q_{vc}})
}{
1-e^{-Q_c(V)}
}.
\]

\(S\subseteq T\)이면 \(Q_c(S)\le Q_c(T)\)이므로 \(\Delta_vG_c(S)\ge\Delta_vG_c(T)\)다. 따라서 \(G_c\)는 monotone submodular다. 비음수 가중합과 modular 항의 합도 같은 성질을 가지며 \(F(\varnothing)=0\)이다. \(\square\)

**정리 6.** 매 단계 최대 marginal gain을 선택하는 greedy 해 \(S_g\)는 최적해 \(S^\star\)에 대해

\[
F(S_g)\ge(1-1/e)F(S^\star)
\]

를 만족한다.

**증명.** 정리 5의 normalized monotone submodular 함수와 cardinality constraint에 대한 표준 greedy 근사 정리를 적용한다. \(\square\)

## 결정론과 복잡도

동일 marginal gain은 UUID 내림차순으로 결정한다. 후보 수를 \(|V|\), budget을 \(B\), node가 참여하는 평균 chain 수를 \(\bar d\)라 하면 현재 명시적 greedy 구현은 \(O(B|V|\bar d)\) 시간과 \(O(|V||\mathcal C|)\) 이하의 sparse membership 메모리를 사용한다. Candidate가 수천 개를 넘으면 같은 목적함수에 lazy greedy를 적용할 수 있으며 근사 보장은 변하지 않는다.

## 기존 방법과의 경계

- ProvX는 GNN prediction을 뒤집는 continuous edge-mask perturbation을 학습한다. FlowSub responsibility는 detector gradient 없이 동결된 typed chain에서 정확히 계산된다.
- Recursive Shapley Value는 structural causal model의 effect propagation을 공리화한다. FlowSub는 관측된 predicate endpoint 교집합에 edge confidence를 보존 배분한다.
- 일반 submodular explanation은 feature나 region을 선택한다. FlowSub는 official detector budget, provenance-chain counterfactual, conserved flow를 하나의 label-free 목적함수로 결합한다.
- ORTHRUS DEPIMPACT는 이상 node 주변의 dependency를 재구성한다. FlowSub는 보고량을 늘리지 않는 cardinality-constrained attribution 문제를 푼다.

따라서 novelty는 counterfactual, flow, submodularity 중 하나를 최초로 사용했다는 데 있지 않다. 세 요소를 detector-independent provenance chaining에 결합하고, 동일 alert budget에서 수학적 보장과 fine-node attribution을 함께 평가하는 데 있다.

## Ablation

- anomaly-only: \(q_{vc}=0\)
- responsibility-only: \(q_{vc}=\sqrt{a_vn_{vc}}\)
- flow-only: \(q_{vc}=\sqrt{a_vh_{vc}}\)
- full: \(q_{vc}=\sqrt{a_v[1-(1-n_{vc})(1-h_{vc})]}\)

모든 ablation은 같은 후보, budget, split, detector score와 tie-break를 사용한다.

## 고정 예산 결과

수식, tie-break, 예산 규칙을 CADETS label 평가 전에 고정하고 label-free 선택 파일을 먼저 해시했다. THEIA에는 어떤 항도 바꾸지 않고 동일 코드를 적용했다.

| 데이터 | 공식 Velox seed | anomaly-only | flow-only | responsibility-only | full |
|---|---:|---:|---:|---:|---:|
| CADETS E3, \(B=1{,}103\) | 23 | 23 | 23 | 29 | 29 |
| THEIA E3, \(B=503\) | 16 | 16 | 17 | 25 | 25 |

숫자는 fine-label 악성 node 회수 수다. Full은 두 데이터에서 responsibility-only와 같은 집합을 선택했다. 따라서 성능 기여는 정확한 반사실 책임도와 부분모듈 예산 교환에 귀속한다. 보존 flow는 유일성·효율성·비음수성은 만족하지만 이 두 데이터에서 추가 성능 기여가 없거나 매우 약했다. 이를 제거하거나 결과를 본 뒤 가중치를 조정하지 않고 음성 ablation으로 보고한다.

CADETS에서 precision·recall·MCC는 `0.02085/0.33824/0.08318`에서 `0.02629/0.42647/0.10514`로, THEIA에서는 `0.03181/0.13559/0.06536`에서 `0.04970/0.21186/0.10231`로 변했다. 두 실행 모두 공식 seed 수와 같은 node만 보고하므로 개선은 경보량 증가가 아니라 예산 안의 교환에서 발생했다.
