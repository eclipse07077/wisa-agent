# BEAR

BEAR는 Branching E-process for Attack Reconstruction의 약자다. 기존처럼 detector score, counterfactual score, flow와 coverage를 별도 항으로 만든 뒤 합하지 않는다. 모든 관측을 evidence capital로 바꾸고, 계층의 대안은 자본을 나누며, 시간 체인은 자본을 순차 재투자한다. Node 점수와 오케스트레이터 우선순위는 이 하나의 장부에서 node를 제거했을 때 사라지는 자본으로 정의한다.

## 원자 evidence

정상 validation에서 공식 Velox와 같은 방식으로 incident edge loss의 node별 최댓값을 만든 집합을 \(\mathcal Z\)라 한다. Test node score \(s_v\)의 upper-tail conformal value는

\[
p_v=
\frac{
1+\left|\{z\in\mathcal Z:z\ge s_v\}\right|
}{
|\mathcal Z|+1
}.
\]

고정된 \(\kappa=1/2\)를 사용해 node의 원자 e-capital을

\[
e_v=(1-\kappa)p_v^{-\kappa}
\]

로 정의한다. \(\kappa\)는 데이터셋별로 선택하지 않는다.

**정리 1.** \(p_v\)가 super-uniform이면 \(e_v\)는 \(\mathbb E_0[e_v]\le1\)을 만족하는 e-variable이다.

**증명.** \(u\mapsto(1-\kappa)u^{-\kappa}\)는 감소 함수이고 super-uniform \(p_v\)는 uniform 변수보다 작은 값을 덜 자주 가진다. 따라서

\[
\mathbb E_0[e_v]
\le
\int_0^1(1-\kappa)u^{-\kappa}du
=1.
\]

\(\square\)

**정리 2.** Calibration과 test score 모두에 strictly increasing 함수 \(f\)를 적용해도 \(p_v\)와 \(e_v\)는 변하지 않는다.

**증명.** \(z\ge s_v\)와 \(f(z)\ge f(s_v)\)가 동치이므로 conformal rank가 같다. \(\square\)

## 분기와 직렬 장부

후보 \(V\)는 official strict-threshold seed와 모든 동결 trace chain endpoint 중 공식 score universe에 속한 node의 합집합이다. Route family \(\mathcal R\)는 각 후보 node의 length-one route와 모든 typed trace chain으로 구성한다.

길이 \(\ell\)에 배정되는 prior mass는

\[
q_\ell=
\frac{2^{-\ell}}
{\sum_{k\in L}2^{-k}}
\]

이고, 같은 길이의 \(N_\ell\)개 route에는 \(q_\ell/N_\ell\)를 균등 배정한다. 긴 설명에 더 긴 prefix code를 부여하는 고정 complexity prior다.

Chain \(c=(p_1,\ldots,p_m)\)에서 predicate \(p_i\)의 endpoint를 \(E_i\)라 한다. Node \(v\)가 이 chain의 predicate endpoint에 등장하는 횟수를 \(m_{vc}\)라 하면 predicate capital은

\[
P_i(c)=
\frac{1}{|E_i|}
\sum_{v\in E_i}
e_v^{1/m_{vc}}.
\]

같은 UUID가 모든 등장 위치에서 선택되더라도 총 승수는

\[
\prod_{i:v\in E_i}e_v^{1/m_{vc}}=e_v
\]

이므로 같은 detector evidence가 chain 길이만큼 복제되지 않는다.

동결 edge confidence를 \(a_i\in[0,1]\)라 하면 chain capital은

\[
E(c)=
\left(\prod_{i=1}^{m}P_i(c)\right)
\left(\prod_{i=1}^{m-1}a_i\right).
\]

Length-one route의 capital은 \(e_v\)다. 전체 장부는

\[
\mathcal E=
\sum_{r\in\mathcal R}
\frac{q_{|r|}}{N_{|r|}}E(r).
\]

대안 route는 prior 안에서 더하고, 한 route의 순차 단계는 곱한다. 새로운 branch를 추가해도 해당 길이의 총 prior \(q_\ell\)는 증가하지 않으므로 기존 evidence가 복제되지 않는다.

## 개입으로 유도한 node score

Node \(v\)를 제거한 장부 \(\mathcal E^{\setminus v}\)는 \(v\)의 모든 원자 항을 0으로 바꾸되 다른 branch로 자본을 재분배하지 않고 계산한다. Absolute intervention loss와 normalized responsibility는

\[
\Delta_v=\mathcal E-\mathcal E^{\setminus v},
\qquad
\rho_v=\frac{\Delta_v}{\mathcal E}.
\]

BEAR는 별도의 anomaly·chain 혼합식을 만들지 않고 \(\Delta_v\) 하나로 node를 정렬한다.

**정리 3.** \(\Delta_v\)는 장부의 sum-of-products 전개에서 \(v\)를 포함하는 모든 route realization의 weight 합과 정확히 같다.

**증명.** 각 predicate 평균을 전개하면 장부는 비음수 monomial의 합이다. \(v\)를 0으로 두면 \(v\)가 포함된 monomial만 0이 되고 나머지는 변하지 않는다. 원래 장부와 개입 장부의 차이는 제거된 monomial의 합이다. \(\square\)

**정리 4.** 양의 weight를 가진 모든 sequential realization이 \(v\)를 포함하면 \(\rho_v=1\)이다.

**증명.** \(v\)를 제거하면 모든 monomial이 0이므로 \(\mathcal E^{\setminus v}=0\)이다. \(\square\)

**정리 5.** 총 capital이 같은 \(k\)개 병렬 대안 중 하나에만 \(v\)가 나타나고 그 대안 안에서는 필수라면 \(\rho_v=1/k\)다.

**증명.** 전체 장부를 \(kA\)라 하면 \(v\)의 개입은 한 대안의 \(A\)만 제거한다. 따라서 \(\rho_v=A/(kA)=1/k\)다. \(\square\)

정리 4와 5는 직렬 병목과 병렬 중복을 같은 규칙으로 구별한다. 개별 chain마다 계산한 책임도를 사후 결합하는 방식과 달리, 대체 경로가 많으면 node 책임도가 자동으로 감소한다.

## 통계적 유효성의 조건

**정리 6.** 각 원자 항이 과거에 조건부인 e-variable이고 branch allocation이 다음 원자 값을 보기 전에 정해지면, predictable convex alternative와 sequential product로 구성한 running ledger는 test supermartingale이다. 따라서

\[
\Pr_0\left(
\sup_t\mathcal E_t\ge\frac1\alpha
\right)\le\alpha.
\]

**증명.** 조건부 e-variable의 순차 곱은 test supermartingale이고, 합이 1 이하인 predictable branch allocation의 비음수 가중합도 조건부 기대값을 증가시키지 않는다. Ville inequality를 적용한다. \(\square\)

현재 replay는 독립 profile이 만든 topology 위에 official detector score를 결합하지만 같은 telemetry에서 두 view가 만들어진다. 또한 한 UUID의 score가 여러 predicate에 분수 승수로 재사용된다. 따라서 정리 6은 조건부 유효성 및 predictable allocation을 만족하는 온라인 BEAR의 보장이고, replay 결과만으로 그 가정이 성립했다고 주장하지 않는다. Replay에서 직접 확인되는 것은 calibration rank, 장부 대수와 label-free 선택 순서다.

## 오케스트레이션

온라인 오케스트레이터는 다음 순서로 동작한다.

1. 정상 calibration으로 관측을 e-capital로 변환한다.
2. 새로운 predicate가 들어오면 현재 stage에서 가능한 branch에 prior capital을 배정한다.
3. 시간·context·stage 조건을 만족하는 branch만 다음 단계로 재투자한다.
4. 전체 장부와 node intervention loss를 갱신한다.
5. 조사 budget \(B\)에서 \(\Delta_v\)가 큰 node를 선택한다.
6. 장부가 \(1/\alpha\)를 넘으면 조건부 가정 아래 anytime-valid chain alert를 낸다.

Offline benchmark에서는 \(B\)를 official strict-threshold seed 수로 고정한다. 동일 \(\Delta_v\)는 UUID 내림차순으로 처리한다.

## 기존 방법과의 경계

- E-value와 conformal martingale 자체는 기존 통계 이론이다.
- Semiring과 sum-product path evaluation 자체도 weighted automata, trust path, attack tree와 evidence logic에서 사용된다.
- Graph counterfactual intervention 자체는 기존 explainability 연구에 존재한다.
- BEAR의 후보 기여는 typed provenance hierarchy를 branching evidence-capital process로 정의하고, 공격 chain reconstruction과 exact global node intervention을 같은 ledger에서 유도한 것이다.
- FlowSub의 counterfactual·flow·부분모듈 항은 BEAR에 사용하지 않는다.

현재 검색으로 같은 formulation을 찾지 못했지만, 체계적 문헌 검토가 끝나기 전에는 최초 사용이라고 주장하지 않는다.

## 계산량

현재 명시적 구현은 후보 수를 \(|V|\), chain 수를 \(|\mathcal C|\), 평균 predicate 수를 \(m\)이라 할 때 \(O(|V||\mathcal C|m)\) 시간이다. Node-to-chain incidence를 미리 만들면 개입 계산은 실제 endpoint incidence에 비례하도록 줄일 수 있다. 메모리는 chain endpoint와 선택 node 값을 포함해 \(O(\sum_{c,p}|E_{cp}|+|V|)\)다.

## 개발 결과와 종료 판정

| 방법 | CADETS TP / 1,103 | THEIA TP / 503 |
|---|---:|---:|
| official/local | 23 | 16 |
| chain-only v1 | 23 | 17 |
| full v1 | 26 | 16 |
| full v2 unit-growth | 22 | 미실행 |

v1은 CADETS에서 local-only와 chain-only가 각각 23인데 full이 26이라 단일 ledger 상호작용이 실제 추가 node를 회수했다. 그러나 같은 수식을 적용한 THEIA에서는 full이 local과 같은 16으로 돌아가 전이에 실패했다.

THEIA v1의 label-free ledger는 local 22.7750, chain 0.5657이었다. Route 길이에 따른 곱셈 감쇠를 제거하기 위해 \(m\)-th root의 단위 단계 성장률을 v2로 별도 등록했다. 이 변환은 Jensen inequality 아래 e-validity와 exact intervention identity를 보존하지만 CADETS TP가 22로 악화됐다.

BEAR는 단일 algebra 가능성을 보여준 형식적 선행 실험으로 남긴다. 성능 방법으로 선택하지 않으며 이후 root-conditioned proof account인 RAVEL로 연구 질문을 좁혔다.
