# RAVEL-C 공격 조사 논문 요약

## 연구 질문

Provenance detector가 상위 \(B\)개 node를 제시했을 때, 같은 조사 예산으로 어떤 \(B\)개의 서로 다른 node를 조사해야 하는가?

RAVEL은 detector 점수와 chain 점수를 합치는 방법이 아니다. 각 detector root가 조건부 proof account를 열고, UUID-continuous typed chain을 factorized proof capital로 표현한다. UUID 하나를 계정 전체에서 삭제했을 때 사라지는 상대 capital이 fractional proposal utility다. Exact matching은 root마다 한 slot, node마다 최대 한 slot을 배정한다.

## 인증형 최종 방법

RAVEL-C는 fractional proposal을 그대로 사용하지 않는다. Root \(s\)의 모든 route \(c\)에 대해 UUID \(v\)만으로 이루어진 singleton clause가 하나 이상 존재할 때

\[
\Gamma(s,v)=
\bigwedge_{c\in\mathcal C_s}
\bigvee_{Q\in\mathcal Q_{sc}}
\mathbf 1[Q=\{v\}]=1
\]

로 인증한다. 모든 atomic evidence와 edge factor가 양수이므로 이 조건은 \(v\)를 삭제했을 때 account capital 전체가 사라지는 \(\rho_{sv}=1\)과 필요충분이다.

최종 matching은 모든 인증 edge와 private hold를 대상으로

\[
\omega_{sv}
=(B+1)^2\mathbf 1[v\ne s]
+(B+1)\mathbf 1[(s,v)\in M_6]
+\bar e_v
\]

를 정확히 최대화한다. 이 한 식은 순서대로 인증 transport 수 최대화, fractional proposal과의 Hamming 왜곡 최소화, conformal evidence 최대화를 보장한다. 가중치 튜닝은 없다.

## 수학적 기여

- Singleton-hyperclause 조건은 등록된 factorized account의 complete fracture와 필요충분이다.
- Full certified graph를 사용해야 proposal의 partial edge가 다른 root의 complete edge를 가리는 문제를 막을 수 있다.
- 위의 bounded rank는 세 단계 목적을 정확히 lexicographic하게 구현한다.
- Proposal의 certified edge가 이미 최대 cardinality면 최종 결과는 filter-and-hold와 정확히 같다.
- Detector top-\(B\)에서 바깥 node로 교체하면 detector evidence는 증가할 수 없다.
- 서로 다른 같은-크기 label-free 집합 \(R,S\)에 대해 \(R\setminus S\) 또는 \(S\setminus R\)를 positive label로 잡을 수 있으므로, label과 evidence를 잇는 가정 없이 비자명한 교체가 actor recall을 항상 보존한다는 보장은 불가능하다.

이 보장은 proof semantics에 대한 것이다. Malicious actorID 정확성, recall, detector calibration 또는 anytime-valid false-alarm control을 뜻하지 않는다.

## 개발 결과

H501과 H201 label은 최종 방법을 만드는 동안 이미 관측했으므로 둘 다 개발 데이터다.

| Host | Velox | FlowSub | Fractional \(M_6\) | RAVEL-C | 인증 이동 | 감소 interval |
|---|---:|---:|---:|---:|---:|---:|
| H501 | 7 | 11 | 10 | 8 | 7 | 0/65 |
| H201 | 2 | 4 | 1 | 2 | 11 | 0/216 |

H501에는 92,670개 proof candidate 중 34개 인증 edge가 있고 conflict 뒤 7개가 선택된다. H201은 298,021개 중 19개, 최종 11개다. 두 데이터에서 proposal의 certified edge가 이미 최대 cardinality라 RAVEL-C는 filter-and-hold를 재현한다. 이는 설계 검증이지 외부 일반화 근거가 아니다.

## H051 홀드아웃

H051은 label을 읽거나 hash하기 전에 method, budget 512, Velox, FlowSub, \(M_6\), 네 성공 조건을 고정했다. Score, route, proposal, certified output과 plan을 동결한 뒤 별도 감사가 source matching, certified matching, 모든 cut witness, 목적값과 code hash를 재계산했다. 감사가 통과한 뒤 처음 label을 열었다.

| Method | 회수 | Precision | Covered recall | MCC |
|---|---:|---:|---:|---:|
| Velox | 4 | .00781 | .03509 | .01640 |
| FlowSub | 8 | .01563 | .07018 | .03296 |
| Fractional \(M_6\) | 2 | .00391 | .01754 | .00812 |
| RAVEL-C | 3 | .00586 | .02632 | .01226 |

RAVEL-C는 113,495개 proof edge 중 네 개를 인증하고 모두 이동했다. Fractional proposal은 \(2\rightarrow3\)으로 일부 복구했지만 Velox의 4와 FlowSub의 8보다 낮다. Velox 대비 네 slot을 바꾸면서 malicious root 하나를 잃고 malicious target을 추가하지 못했다. 사전등록한 primary safety, secondary efficacy, FlowSub noninferiority, 모든 비교군 strict superiority는 전부 실패했다.

## 결론

이 결과는 SOTA나 성능 우월성 논문이 아니다. 논문의 핵심은 chain reconstruction, UUID intervention, cross-alert orchestration을 하나의 인증 가능한 fixed-budget projection으로 만든 formulation, 그 exact lexicographic solver와 검증 가능한 witness, 그리고 actor safety가 자동으로 따라오지 않는다는 불가능성 정리와 홀드아웃 반증이다.

동결·감사·label 접근 기록은 `results/frozen-051.json`, `results/audit-051.json`, `results/label-051.json`에 있고, 최종 결과는 `results/eval-cert-051.json`, 논문은 `output/pdf/attack.pdf`에 있다.
