# RAVEL-C 주장 감사표

이 표는 본문이 수학적 보장이나 실험 결과보다 강해지는 것을 막기 위한 내부 검증 기록이다.

| 주장 | 직접 근거 | 판정 |
|---|---|---|
| \(\Gamma(s,v)=1\)은 등록된 account의 complete fracture \(\rho_{sv}=1\)과 필요충분이다. | 양의 route product는 UUID 삭제 뒤 어떤 clause가 공집합일 때만 0이고, 단일 UUID 삭제에서 이는 \(Q=\{v\}\)와 동치다. `tests/test_cert.py`가 direct deletion과 route-index 구현의 동치를 검사한다. | 대수·구현으로 지지 |
| Proposal edge만 거르는 것으로는 최대 certified transport를 보장할 수 없다. | Partial proposal edge가 다른 root의 certified edge를 가리는 반례와 full-graph 회귀 검사가 있다. | 반례·테스트로 지지 |
| \((B+1)^2,(B+1),\bar e_v\) rank는 certified cardinality, proposal agreement, evidence를 순서대로 정확히 최적화한다. | 하위 두 항의 최대 차이가 각각 상위 한 단위보다 작다는 Theorem 2와 tuple-valued brute-force oracle 검사가 있다. | 대수·구현으로 지지 |
| RAVEL-C는 정확히 \(B\)개의 고유 node와 총 mass 1을 반환한다. | Private hold의 feasibility, unit-capacity matching, structural certificate와 회귀 검사. | 지지 |
| Proposal의 certified edge가 최대 cardinality면 RAVEL-C는 filter-and-hold를 재현한다. | Corollary 1, H501/H201 node-set 일치와 독립 감사. | 지지 |
| 비자명한 fixed-budget label-free 교체는 label 가정 없이 actor recall non-decline를 균일하게 보장할 수 없다. | 같은 크기의 서로 다른 \(R,S\)에 대해 \(Y=R\setminus S\)와 \(Y=S\setminus R\)를 구성하는 Theorem 3. | 대수로 지지 |
| Complete proof fracture는 malicious actorID 정확성을 인증한다. | Structural witness는 label을 읽지 않으며 H051에서 malicious root 하나를 unlabeled target으로 교체했다. | 기각 |
| H501/H201은 최종 방법의 외부 검증 데이터다. | 두 label이 certified projection 개발에 사용됐다. | 기각; 개발 데이터로만 사용 |
| H501에서 RAVEL-C는 Velox \(7\rightarrow8\), H201에서는 \(2\rightarrow2\)이고 interval 감소가 없다. | `results/eval-cert-501.json`, `results/eval-cert-201.json`. | 개발 결과로 지지 |
| H051 selection과 endpoint는 label 전에 고정됐다. | `results/cert-plan.json`, `results/frozen-051.json`, `results/audit-051.json`, `results/label-051.json`의 순서·hash·timestamp. | 지지 |
| H051 독립 감사가 source와 certified assignment, cut witness와 세 단계 목적을 재현했다. | `results/audit-051.json`: source 59, certified 4, agreement 457, changed 55, witnessed routes 5. | 지지 |
| H051에서 Velox, FlowSub, \(M_6\), RAVEL-C 회수는 각각 4, 8, 2, 3이다. | `results/eval-cert-051.json`, exact budget 512, malicious UUID 114개 모두 score universe에 포함. | 홀드아웃 결과로 지지 |
| H051 primary safety가 성립한다. | RAVEL-C 3 대 Velox 4. | 기각 |
| H051 secondary efficacy가 성립한다. | RAVEL-C가 Velox보다 높지 않다. | 기각 |
| H051 FlowSub noninferiority가 성립한다. | RAVEL-C 3 대 FlowSub 8. | 기각 |
| H051 모든 비교군 strict superiority가 성립한다. | RAVEL-C 3, 비교군 최고 8. | 기각 |
| RAVEL-C가 fractional \(M_6\)의 H051 실패를 일부 복구한다. | \(2\rightarrow3\), 55 slot 변경. | 기술적으로 지지; baseline safety 근거 아님 |
| 본 방법이 ORTHRUS, KAIROS, DEPIMPACT, ProvX 또는 VCAUSE보다 성능이 높다. | 동일 전처리·학습·metric의 직접 비교가 없다. | 주장 금지 |
| 본 결과는 공식 OpTC dump reproduction이다. | Corrected projection과 공개 label 형식을 사용했고 paired official dump 재현은 없다. | 주장 금지 |
| H201 TGN은 input-matched architecture ablation이다. | Window, Word2Vec seed, 표현 차원과 산출물 hash가 다르다. | 기각; pipeline sensitivity로만 허용 |
| RAVEL-C는 SOTA actor attribution 방법이다. | H051에서 Velox와 FlowSub보다 낮다. | 기각 |
| 본 공격 조사 시스템이 LLM 호출로 성능을 얻었다. | 선택·평가 과정에서 LLM API를 사용하지 않았다. | 기각 |

## 허용되는 핵심 결론

RAVEL-C는 root-owned proof account, singleton-hyperclause certificate, fixed-budget cross-root uniqueness와 exact minimum-distortion projection을 결합한다. 수학적 보장은 등록된 proof objective의 feasibility, complete fracture와 lexicographic allocation에 한정된다. H051 홀드아웃은 actor-recall safety를 반증했으며 성능 우월성, SOTA, 공식 dump 재현 또는 actor label 정확성으로 확대하지 않는다.

## 고정 영수증

- Freeze: `af72b40f0552ad0b368161ffd1b10c379d7c2cee838debfa919dbf72f9d829b1`
- Audit: `474b793467a7adabf2d486ddb880e79799975331c80bd904440193838595b942`
- Label: `ff8af2562c6746b48f81445fa36a5860ebd9a4402fa6b83cd47ddda35bfdeb3b`
- Evaluation: `cee25b17dc9310feaf81d7a35da7732e96e189aa1175284b508570742de98ca8`
