# 실험 규약

이 문서는 구현과 본 실험 전에 고정한다. 변경이 필요하면 기존 내용을 덮어쓰지 않고 변경 이유, 시각, 영향을 별도 기록한다.

## 공통 규칙

- 공식 저장소 commit과 실행 환경을 결과에 기록한다.
- 개발, 검증, 최종 평가를 분리한다.
- 실패한 실행과 불리한 결과를 제외하지 않는다.
- test 라벨로 임계값, epoch, seed, 가중치, 탐색 깊이를 선택하지 않는다.
- baseline과 제안 방법에 같은 입력 범위와 계산 예산을 적용한다.
- 결과는 원시 run 단위와 집계 단위를 모두 보존한다.
- 평균뿐 아니라 표준편차, paired 차이의 bootstrap 95% 신뢰구간, 효과크기를 보고한다.

## 고정 방법 파라미터

| 항목 | 값 | 출처 |
|---|---:|---|
| 최대 체인 길이 | 5 | 예선 보고서 |
| edge 임계값 | 0.58 | 예선 보고서 |
| 시간 가중치 | 0.30 | 예선 보고서 |
| context 가중치 | 0.30 | 예선 보고서 |
| 단계 진행 가중치 | 0.25 | 예선 보고서 |
| 임무 영향 가중치 | 0.15 | 예선 보고서 |
| 체인 탐색 시간 창 | 18초 | 예선 보고서 |
| 최소 predicate 수 | 3 | 예선 보고서 구현 |
| 최소 고유 단계 수 | 3 | 예선 보고서 구현 |
| 일반 체인 종료 단계 | mission effect 또는 response | 예선 보고서 구현 |
| monitor 상한 | 0.49 | 예선 보고서 |
| honeypot 구간 | 0.50–0.69 | 예선 보고서 |
| 임시 격리 구간 | 0.70–0.84 | 예선 보고서 |
| 강한 대응 검토 | 0.85 이상 | 예선 보고서 |

관측 불가능한 edge 항목의 가중치는 나머지 항목에 비례 재분배한다.

## CAGE Challenge 4

### 환경

- 공식 저장소 commit: `8c3c50ca54b176c2de199847944e8dcc035497e3`
- episode 길이: 500 step
- 공식 Red: `FiniteStateRedAgent`
- 개발 seed: 3400–3419
- 검증 seed: 4400–4419
- 최종 seed: 5400–5499

최종 seed는 정책과 모든 임계값을 동결한 뒤 한 번만 실행한다.

### 비교군

1. Sleep
2. 단순 반응형 규칙
3. 기존 LayerChain 파일럿
4. 보고서 기반 전체 방법
5. 전체 방법에서 동적 허니팟 제거
6. 전체 방법에서 인과 체인 제거
7. 전체 방법에서 MetaMonitor·효과 검증 제거

### 지표

- 1차: 공식 cumulative reward
- 2차: Red Impact 성공 횟수, privileged session 수, 임무 서비스 실패, invalid action 비율
- 안전성: Restore와 차단 비용, 효과가 확인되지 않은 조치 비율
- 오케스트레이션: 메시지 사용량, 체인 형성 수, 동적 허니팟 접촉률
- 효율: episode 실행 시간과 최대 메모리

모든 비교는 같은 seed의 paired 실행으로 계산한다.

### 수정 규칙

개발 seed에서만 수정한다. 수정은 다음 셋 중 하나로 분류한다.

- 구현 오류
- 보고서 방법론의 누락
- 방법론 자체의 실패

검증 seed를 본 뒤에는 구현 오류만 수정할 수 있다. 방법론 변경이 필요하면 해당 검증 결과를 폐기하지 않고 새 버전으로 분리하고, 새 검증 seed 묶음을 사전에 지정한다.

### 방어 개발 변경 이력

- v6: 보고서 위험 구간, 효과 검증, recurrence 복구를 적용하고 20개 개발 seed 전체를 실행했다.
- v7: 온라인 적대 호스트 전이 빈도로 허니팟 대상을 선택했다. v6 대비 reward가 평균 272.6 낮아 기본 방법에서 비활성화했다.
- v8: 정상-이탈 위험식을 persistent process와 connection predicate에 연결했지만 reward가 v6보다 167.65 낮았다. CAGE의 이진 process·connection flag는 사전 정의 경보로 분류하고 연결을 롤백했다.

최종 개발 버전은 v6으로 동결한다. 이후에는 CAGE 개발 seed를 보고 행동 규칙이나 위험도를 더 수정하지 않는다.

### 방어 후속 실험 사전등록

2026-07-29 23:55 KST에 기존 최종 평가와 분리된 후속 실험을 등록했다.

- 목적: v6의 위험 계산, 체인 탐색, 허니팟 규칙은 고정하고 가역적 대응과 효과 확인의 행동 배분만 검증한다.
- v9 개발 seed: 6400–6419
- v9 검증 seed: 7400–7419
- v9 최종 seed: 8400–8499
- 비교군: LayerChain, 동결된 report v6, report v9
- 1차 비교: paired cumulative reward
- 2차 비교: privileged host, impacted host, successful impact, 행동별 실행 횟수
- v9 개발 허용 변경: 강한 조치 전에 같은 호스트를 분석하고 이후 관측에서 위협이 지속됐는지 확인한다. 강한 조치 뒤에는 분석 근거를 소비해 반복 조치 전에 다시 확인한다.
- 고정 항목: 위험도 식과 구간, 체인 가중치·임계값·길이·시간 창, predicate, criticality, 허니팟 대상 규칙, Red 정책, episode 길이
- 개발 판정: v9가 v6보다 reward와 공격 영향 지표를 동시에 악화시키면 H26을 기각한다. reward가 개선되더라도 LayerChain 대비 우월성은 별도로 검증한다.
- 검증 규칙: 개발 결과를 보고 최대 한 번의 방법론 수정을 허용하며 수정 시 새 버전으로 기록한다. 선택된 버전은 7400–7419에서 한 번 실행하고 이후 수정하지 않는다.
- 최종 규칙: 검증에서 v6 대비 방향이 유지된 경우에만 선택된 버전을 8400–8499에서 한 번 실행한다. 실패한 개발·검증 결과도 모두 보존한다.

### v9 개발 판정과 마지막 수정

v9은 seed 6400–6419에서 reward `-6376.85 ± 1242.34`를 기록해 v6의 `-3638.20 ± 944.75`보다 평균 `2738.65` 낮았다. paired 95% 구간은 `[-3254.83, -2251.11]`이고 20개 시드에서 한 번도 이기지 못했다. privileged host는 평균 16.30개, Impact는 7.35회 증가했다.

v9은 Analyse를 2091회에서 2815회로 늘리고 Remove·Restore를 1656회에서 152회로 줄였지만 모든 결과가 악화됐다. 따라서 단순 행동 횟수 재배분으로 설명한 H26을 기각한다.

2026-07-30 00:13 KST에 허용된 마지막 개발 수정 v10을 구현 전에 등록했다.

- 공식 소스에서 process·connection 비트가 감염 상태가 아니라 최근 이벤트 버퍼임을 확인했다.
- 다음 step의 비트 지속 여부를 요구하지 않는다.
- 같은 판단 시점의 독립 계층이 두 개 미만이면 강한 대응 대신 Analyse를 선택한다.
- process와 connection이 함께 관측된 교차계층 위협은 Recover 경로로 보내고, 단일 process 근거는 Remove 경로로 보낸다.
- 조치 직후 비트 소실을 성공으로 세지 않고 18-step 동안 같은 호스트의 재발 이벤트를 감시한다.
- 효과 감시 중에는 같은 호스트에 강한 조치를 중복 실행하지 않는다.
- 위험도, 체인, predicate, criticality, 허니팟, Red, seed, episode 길이는 v6·v9과 동일하게 유지한다.
- v10은 같은 개발 seed 6400–6419에서 v6과 비교한다. reward가 개선되고 privileged host·Impact를 동시에 악화시키지 않은 경우에만 7400–7419 검증으로 진행한다.
- v10 이후에는 개발 결과와 관계없이 추가 정책 수정이나 seed 선택을 하지 않는다.

### v10 개발 판정

v10은 seed 6400–6419에서 reward `-3674.55 ± 1184.77`를 기록했다. 같은 시드의 v6은 `-3638.20 ± 944.75`였고, paired v10 minus v6 reward는 `-36.35`, 95% 구간은 `[-367.55, 260.65]`, win rate는 `0.60`이었다.

v10 minus v6의 privileged host는 `-0.30 [-2.80, 2.25]`, impacted host와 성공 Impact는 각각 `-1.65 [-3.25, -0.05]`였다. 영향 억제는 개선됐지만 사전등록한 1차 조건인 reward 점추정 개선을 충족하지 못했다. LayerChain 대비 reward도 `-457.45 [-909.91, -35.22]`로 열세였다.

따라서 v10을 선택하지 않고 seed 7400–7419와 8400–8499는 실행하지 않는다. H28을 기각하고 방어 정책 수정을 종료한다. v9과 v10 결과는 모두 보존하며, 보고서식 대응 오케스트레이션의 CAGE 성능 우월성을 주장하지 않는다.

## DARPA Transparent Computing

### 데이터

- 개발: CADETS E3
- 검증: THEIA E3
- 중간 held-out: TRACE E3
- 최종 외부 일반화: CADETS, THEIA, ClearScope E5

THEIA E3 외부 검증 분할은 ORTHRUS 공개 설정을 그대로 사용한다.

- 정상 학습: 2, 3, 4, 5일
- 임계값 검증: 9일
- 외부 평가: 10, 12, 13일
- 정답 매핑: Firefox Backdoor는 10일, Browser Extension Dropper는 12일, 13일은 공격 없음

정답 매핑은 에이전트 실행이 끝난 뒤 평가에만 사용한다. 학습, 임계값 선택, predicate 생성, 체인 탐색에는 정답 노드나 공격 시간대를 제공하지 않는다.

TRACE E3에는 ORTHRUS와 같은 fine node ground truth가 없으므로 THEIA·CADETS 수치와 직접 합치지 않는다. MAGIC 공개 전처리 그래프와 ThreaTrace coarse label에서는 공개 anomaly score를 고정한 뒤 체인 결합 전후의 ranking과 attribution 변화만 별도 강건성 검사로 보고한다. 이 결과로 임계값이나 체인 규칙을 수정하지 않는다.

MAGIC의 ThreaTrace 기반 넓은 라벨은 재현 비교에만 사용한다. 주 결과는 ORTHRUS의 세밀한 node-level ground truth와 공격 사례 단위를 사용한다.

### ClearScope E5 사전등록

2026-07-30 00:29 KST에 원본 ClearScope E5를 열기 전에 CDM20 외부 평가를 등록했다.

- performer: ClearScope E5
- 공개 분할: 정상 학습 8·9일, validation 11일, 평가 14·15·17일
- 정답: ORTHRUS의 `E5-CLEARSCOPE` fine node ground truth를 에이전트 실행 후 metric 계산에만 사용한다.
- 입력 호환 변경: tar 안의 JSON line뿐 아니라 독립 gzip JSON line도 읽고, day boundary의 연도·월·시작일·종료일을 CLI에서 받는다.
- CDM namespace는 버전 문자열과 무관하게 기존 `datum` unwrapping을 사용한다.
- 고정 항목: 추적 relation과 역방향 relation 집합, node·event 필드 해석, 정상 profile, 0.995 validation quantile, 18초 trace, predicate 선택, 체인 가중치·임계값·길이, grounded node 기여
- 데이터셋별 파일명, UUID, 공격 시간, 앱 이름, relation 규칙은 profile·predicate·chain에 사용하지 않는다.
- 비교: anomaly-only와 grounded trace의 AUROC·AP, 같은 수의 조사 노드에서 악성 노드 수·precision·recall, 공격 없는 평가 구간의 출력
- 판정: E5에서 유효 체인이 생기고 matched-budget 악성 노드 회수가 증가하면 attribution 전이를 지지한다. AP·AUROC는 별도 지표로 보고하며 둘 중 하나라도 하락하면 ranking 일반화는 지지하지 않는다.
- 원본 평가 후에는 ClearScope E5에 맞춘 임계값, relation, 시간 창, 후보 상한 또는 점수 가중치 수정과 test subset 재선택을 하지 않는다.
- 저장 공간을 위해 공식 gzip 조각은 순서대로 스트리밍 인덱싱할 수 있다. 사용 조각과 누락 조각, 레코드 수를 결과에 기록한다.

첫 공식 조각을 확인한 결과 gzip payload는 예상한 JSON-lines가 아니라 Avro Object Container였다. 이는 사전등록의 입력 형식 가정 오류로 기록한다. 평가 전에 허용한 호환 변경을 다음과 같이 정정한다.

- tar 안의 JSON-lines, gzip JSON-lines, gzip Avro Object Container를 공통 record iterator로 읽는다.
- Avro union을 디코더가 반환한 `datum` payload로 해제한 뒤 기존 `node_record`와 `event_record`에 그대로 전달한다.
- Avro 스키마, enum, union 구조를 relation·단계·위험 점수의 추가 신호로 사용하지 않는다.
- 이 정정은 원본 레코드 한 건도 점수화하기 전에 수행하며, 정정 전후의 테스트와 원본 형식 증거를 보존한다.

최종 입력은 PIDSMaker `velox` commit `54f687c54aa03e5519cf44953d5ee44f5f6a4a28`가 제공한 `clearscope_e5.dump`를 사용한다. tar 첫 멤버 범위만 내려받은 dump 크기는 `6,630,620,258` byte이고 PostgreSQL 목차와 SQLite 무결성 검사를 통과했다.

- dump의 `event_table`은 frozen method와 같은 10개 relation과 같은 역방향 간선 규칙을 사용한다.
- event table에는 원본 `predicateObjectPath`가 없다. E5에서는 path를 모두 `unknown`으로 유지하며 node path, 앱 이름 또는 정답에서 복원하지 않는다.
- 인덱스는 노드 501,006개, event 198,794,211개, 누락 endpoint 0개다.
- 선택된 event 수는 train 8·9일 61,248,915개, validation 11일 512,119개, test 14·15·17일 48,553,585개다.
- fine ground truth는 세 test day의 agent 출력이 모두 고정된 뒤 읽는다.

ClearScope E5 실행 후에는 임계값, path 처리, relation, predicate, 체인 또는 평가일을 변경하지 않는다. E5 결과에서 attribution 전이 기준이 실패했으므로 H25를 기각하고 CDM20 일반화 주장을 종료한다.

### E5 이후 원인 분리

E5 결과는 재선택이나 성능 복구에 사용하지 않는다. 2026-07-30 01:55 KST에 다음 개발 진단을 결과 확인 전에 등록했다.

- H30: public dump의 event path 손실이 attribution 실패의 주원인이다.
- falsifier: CADETS E3의 train·validation·development에서 path만 빈 값으로 바꾸고 grounded trace v4를 한 번 실행한다.
- 고정 항목: split, anomaly 식과 가중치, threshold quantile, trace window, predicate, chain, candidate·chain limit, node contribution, fine labels
- 판정: no-path CADETS가 기존 v4의 matched-budget 악성 노드 우위를 잃고 AP·AUROC 또는 attribution recall이 함께 악화되면 path 손실을 주요 표현 한계로 본다.
- H29: path 손실이 주원인이 아니라면 넓은 session endpoint를 모두 node attribution으로 투영하는 방식이 실패 원인이다.
- H29 수정 후보는 chain 형성·점수는 그대로 두고 predicate별 최고 신뢰 event의 backbone endpoint에만 node contribution을 투영한다.
- H29는 H30이 기각된 경우에만 구현하며, CADETS 개발에서 한 번 평가하고 E5 결과에는 소급 적용하지 않는다.
- H31: 두 가설이 모두 설명하지 못하면 frozen structural·trace profile 자체의 performer shift로 분류하고 방법 수정 없이 종료한다.

H30은 2026-07-30 02:01 KST에 한 번 완료했다. path를 제거하자 grounded trace AUROC는 `0.791443`에서 `0.733838`, AP는 `0.125996`에서 `0.085902`, 체인 attribution recall은 `0.25000`에서 `0.04412`로 하락했다. 체인 조사 노드는 악성 17/530개에서 3/1,220개로 악화됐고, matched anomaly-only는 10/530개에서 12/1,220개로 바뀌어 기존 attribution 우위가 역전됐다. 체인 수 192개와 predicate 수 8,192개는 같았다. 사전 판정 조건을 충족하므로 path 손실을 주요 표현 한계로 판정한다. 이는 CADETS 반사실 진단이므로 ClearScope E5 실패의 유일한 원인을 증명하지 않으며, E5는 재실행하지 않는다. H29의 실행 조건은 충족되지 않아 구현하지 않는다.

CADETS E3 내부 개발 분할은 ORTHRUS의 일자 경계를 따른다.

- 정상 학습: 3, 4, 5, 7, 8, 9, 10일
- 임계값 검증: 2일
- 개발 평가: 6, 11, 12, 13일
- 이상치 임계값: validation score의 0.995 quantile
- 체인 후보 상한: 일자별 2,048개

이 값은 첫 CADETS 원본 CDM 실행 전에 고정했다. 후보 상한이 보고서식 국소 체인을 제거하는 구현 문제로 확인되면 기존 결과를 보존하고 새 버전으로 분리한다.

### 개발 변경 이력

2026-07-29에 CADETS 개발 결과를 보고 다음 버전을 분리했다. 기존 결과 파일은 모두 보존한다.

1. event v1: 이상 이벤트를 직접 predicate로 변환했다. 유효 체인이 0개여서 표현 실패로 판정했다.
2. semantic v2: 이상 이벤트를 process/session 단계별로 집계했다. 체인 48개가 생겼지만 악성 노드가 0개여서 실패로 판정했다.
3. trace v3: 이상 seed가 있는 18초 process session에서 주변 전이를 복원했다. 고정-budget attribution은 개선됐지만 raw chain score로 node score를 덮어써 AP가 하락했다.
4. grounded trace v4: 체인과 predicate confidence의 곱으로 노드 기여를 제한한다. 임계값, 체인 가중치, 시간 창, 후보 상한은 바꾸지 않는다.

v1에서 v4까지 CADETS E3 개발 범위 안에서만 수정했다. THEIA·TRACE·E5는 열람하거나 튜닝에 사용하지 않는다.

### 체인 경보 calibration 진단

THEIA 외부 결과에서 공격 없는 13일의 체인 출력까지 이미 확인했으므로, 이후 calibration은 새로운 외부 확인이 아니라 H24의 사후 탐색 진단으로 분리한다.

- 각 performer의 정상 validation split에서 grounded trace v4를 그대로 실행한다.
- validation 체인 점수의 0.995 quantile을 `higher` 방식으로 경보 임계값으로 고정한다.
- validation 체인이 없으면 경보 임계값은 1.0으로 둔다.
- test에서는 임계값 이상 체인의 endpoint만 경보 노드로 보고한다.
- node anomaly threshold, predicate, chain 구성, 점수, 시간 창, 후보 상한은 변경하지 않는다.
- test 정답은 validation 임계값과 모든 test 출력이 고정된 뒤 metric 계산에만 읽는다.
- 공격 없는 날의 경보 노드 감소와 공격 날의 fine-label recall을 함께 보고한다.
- 이 결과로 THEIA나 CADETS의 임계값을 다시 선택하지 않으며, 낮은 오탐 경보 일반성은 미사용 E5에서 같은 규칙이 재현된 경우에만 주장한다.

실행 결과 H24를 기각했다. CADETS threshold는 `0.7169943`, THEIA threshold는 `0.7429804`였다. CADETS의 공격 없는 11일에 27개, THEIA의 공격 없는 13일에 8개 경보 노드가 남았다. THEIA day 10 공격은 경보를 하나도 만들지 못했고, 두 performer 모두 aggregate matched-budget 악성 노드 회수가 anomaly-only보다 낮았다. 이 결과를 보고 quantile이나 비교 연산을 변경하지 않는다.

### 비교군

1. MAGIC 원 점수
2. ORTHRUS anomaly-only
3. ORTHRUS full reconstruction
4. anomaly score와 시간 인접성만 사용한 단순 체인
5. 보고서 기반 전체 공격 오케스트레이터
6. 전체 방법에서 동적 계층 발견 제거
7. 전체 방법에서 정상 automaton 제거
8. 전체 방법에서 제약 게이트 제거

### 지표

- ranking: AUROC, Average Precision
- 고정 threshold: precision, recall, F1, MCC
- 공격 사례: attack detection precision과 attack detection recall
- 체인: malicious node precision·recall·F1, stage coverage, edge precision·recall·F1
- QoA: 보고 노드 수, 공격 하나당 조사 노드 수, false-positive attribution 수
- 효율: 처리 시간, peak RAM, GPU memory

F1 threshold는 validation에서만 정한다. MAGIC 공개 코드의 test recall 목표 임계값과 ORTHRUS 실행 경로의 test MCC epoch 선택은 사용하지 않는다.

### 수정 규칙

CADETS E3에서만 파라미터와 알고리즘을 수정한다. THEIA E3는 구현 검증과 단일 선택에만 사용한다. TRACE E3와 E5 결과를 확인한 뒤 성능 개선을 위한 재튜닝은 하지 않는다.

## LLM 보조 비교

LLM 비교는 비밀키가 안전한 환경 변수로 별도 제공된 뒤 수행한다. 노출된 키는 사용하지 않는다.

- 같은 모델과 모델 버전
- temperature 0
- 같은 관측, 행동 도구, 최대 step
- 같은 token 한도
- seed별 호출 실패와 비용 포함
- 프롬프트와 모델 응답 원문 보존

## 결과 판정

좋은 결과는 한 지표만 오른 경우가 아니다.

- CAGE: reward가 개선되고 Impact·서비스 실패가 악화되지 않으며 invalid action과 강한 조치 비용이 통제돼야 한다.
- TC: AP 또는 공격 사례 탐지가 개선되고, 보고 노드 수와 false-positive attribution이 감소해야 한다.
- 한 데이터셋에서만 개선되거나 held-out에서 방향이 뒤집히면 일반화 실패로 판정한다.
- 평균 개선이 있어도 paired 신뢰구간이 0을 넓게 포함하면 탐색적 결과로만 보고한다.

## 방법론 강화 연구

2026-07-30 10:24 KST에 기존 최종·외부 결과를 보존한 채 새 연구 단계를 등록했다. 이 단계는 기존 seed나 test label에 맞춘 임계값 변경이 아니라 공통 의사결정과 attribution 구조를 바꾼다.

### 방어 v11

단일 시점 위험 구간을 시간적 belief, 증거 충분성, 정보가치, 대응 비용, 가역성, deception coverage를 함께 보는 제약 효용 계획으로 교체한다.

- target belief는 직전 belief에 `0.80`을 곱한 값과 현재 위험도의 최댓값으로 갱신한다.
- 증거 충분성은 독립 계층 수와 체인 점수로 계산하며 honeypot 접촉은 독립 확인으로 취급한다.
- 증거 충분성이 `0.50` 미만이면 비가역 조치를 허용하지 않는다.
- belief `0.70` 미만에서는 강한 대응을 허용하지 않는다.
- belief `0.85` 이상이고 증거 충분성이 `0.75` 이상일 때만 restore·block 후보를 연다.
- mission effect가 확인된 상태에서는 임시 격리·차단보다 알려진 정상 상태 복구를 우선한다.
- 행동 효용은 `belief × mitigation × evidence + uncertainty × information + coverage gain - cost × (0.4 + 0.6 × criticality) - uncertainty × irreversibility`로 계산한다.
- mission effect에는 mitigation의 `0.15`를 추가한다.
- 위협 대응이 없을 때는 관측 가능한 역할 중 deception coverage가 없는 대상을 선택해 능동 관측점을 만든다. 고정 hostname이나 action index는 사용하지 않는다.
- 동일 target의 강한 대응은 효과 확인 중 중복 실행하지 않는다.
- 기존 위험도, predicate, 체인 가중치, 18초 창은 변경하지 않는다.

행동 속성은 구현 전에 다음과 같이 고정한다.

| 행동 | mitigation | information | deception | cost | reversibility |
|---|---:|---:|---:|---:|---:|
| monitor | 0.05 | 0.15 | 0.00 | 0.00 | 1.00 |
| analyse | 0.15 | 0.85 | 0.00 | 0.05 | 1.00 |
| honeypot | 0.35 | 0.70 | 1.00 | 0.10 | 0.95 |
| temporary isolate | 0.80 | 0.10 | 0.00 | 0.35 | 0.75 |
| restore | 0.95 | 0.05 | 0.00 | 0.55 | 0.45 |
| block | 0.90 | 0.05 | 0.00 | 0.50 | 0.55 |

CAGE 분할은 다음과 같이 봉인한다.

- 개발 seed: 9400–9419
- 검증 seed: 10400–10419
- 최종 seed: 11400–11499
- episode 길이: 500 step
- 개발 비교: v6, v10, LayerChain, v11
- Red 정책: 공식 `FiniteStateRedAgent`와 기존 `ChainAwareRedAgent`

9400–9419는 등록 시점까지 결과 파일과 문서에서 사용된 적이 없다. v11은 두 Red 정책 모두에서 LayerChain보다 평균 reward가 높고, privileged host·impacted host·Impact 중 어느 것도 LayerChain보다 악화되지 않을 때만 검증으로 진행한다. 조건을 충족하지 못하면 10400–10419와 11400–11499를 열지 않는다. 개발 결과를 본 뒤 v11의 상수나 행동 속성을 바꾸지 않는다.

### 방어 v11 결과와 v12 등록

v11은 9400–9419에서 공식 Red reward `-3536.80`, 체인형 Red reward `-4516.00`을 기록했다. 같은 seed의 LayerChain은 각각 `-2784.90`, `-3544.95`였다. paired v11 minus LayerChain reward는 공식 Red `-751.90 [-1139.06, -320.99]`, 체인형 Red `-971.05 [-1406.11, -571.34]`였다. impacted host는 각각 `+1.05`, `+3.95`였으며 체인형 Red 구간은 `[2.65, 5.30]`이다.

v11은 두 조건에서 Remove를 2,033회와 1,683회 실행하고 Restore는 194회와 114회만 실행했다. LayerChain의 Remove는 각 1회였다. 정적 행동 효용이 단일 프로세스 완화의 낮은 비용을 과대평가하고 교차 계층 증거의 범위를 행동 범위와 맞추지 못한 방법 실패로 판정한다. v11을 선택하지 않고 10400–10419와 11400–11499는 열지 않는다.

2026-07-30 10:57 KST에 v12를 새 개발 구간으로 등록했다. v12는 v11 점수나 상수를 조정하지 않고 다음 두 구조를 결합한다.

- deception은 위협 발생 뒤에만 배치하지 않고 평시의 관측 coverage 공백을 순차적으로 채운다.
- 대응 행동의 범위가 증거 범위를 포함해야 한다. 독립 계층이 2개 미만이면 Analyse 또는 honeypot만 허용하고, process와 connection이 함께 확인되거나 mission effect가 형성되면 부분 Remove보다 Restore를 사용한다.
- 강한 대응 이후 18-step 효과 확인 중에는 같은 target에 강한 조치를 중복 실행하지 않는다.
- 위험도, 체인, predicate, criticality, deception 대상 순서, action duration은 v11과 동일하게 유지한다.
- v11의 정적 효용 순위는 사용하지 않는다.

v12 분할은 다음과 같다.

- 개발 seed: 12400–12419
- 검증 seed: 13400–13419
- 최종 seed: 14400–14499
- 비교와 Red 정책, episode 길이, 판정 조건은 v11과 동일

12400–12419는 등록 시점까지 결과 파일과 문서에서 사용된 적이 없다. v12가 두 Red 정책 모두에서 LayerChain reward를 넘고 공격 영향 세 지표를 악화시키지 않을 때만 검증한다. 실패하면 결과를 보존하고 13400–13419와 14400–14499를 열지 않는다.

v12는 12400–12419에서 공식 Red reward `-2221.40`, 체인형 Red reward `-3374.70`을 기록했다. LayerChain은 각각 `-2980.30`, `-3626.25`였다. paired v12 minus LayerChain reward는 공식 Red `+758.90 [270.75, 1280.91]`, 체인형 Red `+251.55 [-297.35, 752.52]`였다.

공식 Red에서 privileged host는 `-4.65 [-7.45, -1.80]`, impacted host와 Impact는 각각 `-0.60 [-1.85, 0.65]`였다. 체인형 Red에서는 각각 `-0.95`, `-0.35`, `-0.40`으로 세 지표 모두 평균상 악화되지 않았다. v12는 두 조건에서 LayerChain과 같은 1,469회 deception coverage를 구성했고 reward와 공격 영향의 사전 조건을 충족했다. 체인형 Red의 reward 구간은 0을 포함하므로 우월성을 확정하지 않고 13400–13419 단일 검증으로 진행한다. 개발 결과를 보고 코드나 상수를 변경하지 않는다.

13400–13419 단일 검증에서 v12 minus LayerChain reward는 공식 Red `+214.30 [-353.91, 700.72]`, 체인형 Red `+1080.80 [652.99, 1521.00]`이었다. privileged host, impacted host, Impact의 평균 차이는 공식 Red에서 `-2.40`, `-0.65`, `-0.60`, 체인형 Red에서 `-3.15`, `-1.25`, `-1.20`으로 모두 악화되지 않았다. 공식 Red reward 구간은 0을 포함하지만 개발과 같은 양의 방향이고 win rate가 `0.70`이며 공격 영향도 같은 방향이다. 체인형 Red에서는 reward와 privileged host의 구간이 모두 개선 방향이다.

검증 결과가 사전 방향을 유지했으므로 코드와 상수를 변경하지 않고 14400–14499 최종 평가로 진행한다. 최종 평가는 LayerChain과 v12만 두 Red 정책에서 각각 100 paired seed로 한 번 실행한다. 두 Red 정책 모두에서 reward 평균 차이가 양수이고 공격 영향 세 지표가 평균상 악화되지 않을 때 최종 성능 개선으로 판정하며 모든 구간과 효과크기를 함께 보고한다.

14400–14499 최종 평가에서 v12 minus LayerChain reward는 공식 Red `+468.65 [276.24, 656.89]`, 체인형 Red `+595.39 [410.39, 784.28]`이었다. 공식 Red의 privileged host, impacted host, Impact 차이는 `-2.84 [-4.13, -1.61]`, `-0.89 [-1.55, -0.26]`, `-0.85 [-1.51, -0.21]`이었고, 체인형 Red에서는 `-2.15 [-3.24, -1.04]`, `-1.05 [-1.66, -0.45]`, `-1.08 [-1.70, -0.47]`이었다. reward와 공격 영향 네 지표의 95% bootstrap 구간이 두 Red 정책 모두에서 개선 방향이며 win rate는 각각 `0.67`, `0.72`였다. 사전 판정 조건을 충족했으므로 v12를 최종 방어 방법으로 선택하며 이 결과를 본 뒤 코드나 상수를 변경하지 않는다.

### 공격 v5

기존 trace 체인은 긴 세션의 모든 endpoint를 공격 node로 투영해 조사 footprint가 커지는 문제가 있다. v5는 정상 데이터만 사용하는 결측치 주변화, 인과 connector attribution, 중복 체인 억제를 추가한다.

- path가 없는 이벤트는 `unknown`을 관측값으로 학습하지 않고 구조·trace 가중치를 비례 재분배한다.
- 각 semantic group은 endpoint별 최대 anomaly 기여를 보존한다.
- 공격 node는 predicate target과 두 단계 이상을 연결하는 반복 endpoint로 한정한다. 한 단계에만 등장한 leaf는 원칙적으로 증거에만 남기되, 해당 predicate의 endpoint 기여 분포에서 `median + 3 × MAD`를 넘는 robust outlier는 직접 payload·target 후보로 보존한다.
- node support는 `chain score × (0.65 × local anomaly + 0.35 × connector persistence)`로 계산한다.
- 체인은 품질 점수에서 이미 선택한 체인과의 최대 footprint Jaccard 유사도에 `0.25`를 곱한 값을 빼는 MMR로 선택한다.
- anomaly 가중치, validation 0.995 quantile, 18초 trace, edge·chain 가중치, predicate·chain 상한은 변경하지 않는다.

CADETS·THEIA·ClearScope 결과는 이미 관측했으므로 v5의 외부 검증으로 부르지 않는다. 구현과 단위 검사를 완료한 뒤 CADETS E3와 THEIA E3에서 각각 한 번만 회고적으로 재평가하고, 결과를 본 뒤 v5를 수정하지 않는다. ClearScope E5는 v5 설계 동기에 포함된 관측이므로 재실행하지 않는다. v5가 두 E3 performer에서 보고 node를 줄이면서 악성 node 수를 유지하거나 늘리고 AP를 `0.001`보다 크게 악화시키지 않을 때 제한적 개선으로 판정한다. 새로운 미사용 performer에서 재현되기 전에는 일반화 개선을 주장하지 않는다.

### 공격 v5 실행 진단과 v6 등록

첫 v5 CADETS 실행은 정답 metric 계산 직전 CAGE 가상환경에 `scikit-learn`이 없어 종료됐다. agent 출력은 이미 고정됐고 일자별 보고 node는 6일 930개, 11일 142개, 12일 128개, 13일 727개였다. 실패 로그를 보존하고 방법 변경 없이 의존성이 갖춰진 환경에서 v5를 다시 실행한다.

이 시점에는 v5의 fine-label metric을 확인하지 않았다. unlabeled footprint만으로 robust leaf outlier가 희소성 계약을 만족하지 못한다고 판정하고 2026-07-30 11:49 KST에 별도 v6를 등록했다.

- path 결측 주변화, MMR, anomaly·chain 가중치와 상한은 v5와 같다.
- predicate target을 무조건 보고하지 않는다.
- 한 체인에서 서로 다른 두 predicate 이상에 등장한 endpoint만 causal cut set으로 보고한다.
- cut set이 비면 predicate target 중 local anomaly 기여가 가장 높은 하나만 fallback으로 보고한다.
- 단일 predicate의 robust leaf outlier는 보고 node에서 제외하고 증거에만 남긴다.
- support 식은 v5와 동일하다.

v6는 v5 결과를 덮어쓰지 않는다. v5 재실행이 끝난 뒤 코드를 동결하고 CADETS와 THEIA에서 각각 한 번 실행한다. 두 실행을 본 뒤 v6를 다시 수정하지 않으며 새로운 performer 없이 일반화 개선을 주장하지 않는다.

v5 CADETS 재실행은 완료됐다. 보고 node는 1,870개이고 악성 node는 11개로 v4의 530개와 17개보다 모두 나빴다. full AP는 `0.104029`로 v4의 `0.125996`보다 낮았고, 같은 v5 anomaly-only AP `0.103490`보다는 `0.000539` 높았다. robust leaf 규칙이 직접 기여 후보를 과도하게 포함했고 missing-path 주변화가 E3 ranking을 악화시켰으므로 v5를 기각한다. 실패한 환경 실행과 완성 결과를 모두 보존한다. 개발 실패가 분명하므로 v5를 THEIA에 실행하지 않는다.

v6는 이 fine-label metric을 열기 전에 위의 cut-set 규칙으로 등록됐다. v6는 CADETS에서 한 번 실행한 뒤 코드를 변경하지 않고 THEIA에서 한 번 실행한다.

v6 CADETS는 보고 node 1,708개, 악성 node 10개를 기록했다. matched anomaly-only는 같은 예산에서 12개를 찾았고 full AP는 `0.104029`였다. 두 predicate 이상 반복 조건도 긴 세션의 공용 자원을 과도하게 포함하므로 v6를 기각하고 THEIA에는 실행하지 않는다.

2026-07-30 11:57 KST에 CADETS 개발의 마지막 구조 수정인 v7을 등록했다.

- path가 있으면 relation-conditioned path surprise를 사용한다.
- path가 없으면 `unknown` path를 만들거나 해당 항목을 버리지 않고 정상 profile의 relation-conditioned path-presence surprise를 사용한다.
- 체인 attribution은 모든 predicate endpoint 집합의 교집합만 보고한다.
- 교집합이 비면 predicate target 중 local anomaly 기여가 가장 높은 하나만 보고한다.
- MMR, support 식, anomaly·chain 가중치와 상한은 유지한다.

v7을 CADETS에서 한 번 실행한다. 보고 node가 530개 이하이고 같은 예산 anomaly-only보다 악성 node를 더 많이 찾으며 full AP가 `0.124996` 이상일 때만 코드를 변경하지 않고 THEIA에서 한 번 실행한다. 조건을 충족하지 못하면 공격 방법 수정을 종료한다. THEIA 결과를 본 뒤에는 방향과 관계없이 수정하지 않는다.

v7 CADETS 실행 결과 보고 node는 183개, 악성 node는 5개였고 같은 예산 anomaly-only는 악성 node 10개를 찾았다. full AP는 `0.129095`로 기준을 넘었지만 핵심 순위 조건을 충족하지 못했다. v7은 경보량을 줄이는 데에는 성공했지만 같은 검토 예산의 악성 node 발견을 개선하지 못했으므로 기각하고 THEIA에서는 실행하지 않는다. 사전 규칙에 따라 공격 방법 수정은 여기서 종료한다.

### 공식 Velox seed 결합

기존 SQLite pairwise proxy가 공식 Velox의 process text representation을 재현하지 못한 뒤, detector 실패와 체인 실패를 분리하기 위해 PIDSMaker `velox` commit `54f687c54aa03e5519cf44953d5ee44f5f6a4a28`을 별도 공식 baseline으로 재현했다. 공식 설정, 공개 pretrained weights, PostgreSQL graph preprocessing, 분할, maximum-validation-loss threshold를 수정하지 않는다.

결합 규칙은 다음과 같이 고정했다.

- 공식 score 파일에서는 `nodes`와 `pred_scores`만 label-free manifest로 전달한다.
- 공식 validation edge loss의 정확한 최댓값에 엄격한 `>`를 적용한다.
- 동결된 grounded trace 체인 중 공식 seed가 endpoint에 포함된 체인만 확장한다.
- 확장 node는 체인 predicate의 실제 endpoint와 공식 score universe의 교집합으로 제한한다.
- hybrid와 같은 node 수의 공식 score top-k를 주 비교군으로 사용한다.
- score 동점은 label-free UUID 내림차순으로 결정하고, metric 단계에서 가능한 TP 범위를 별도 감사한다.
- detector ranking, chain weight, 18초 window, edge threshold, predicate·chain 상한은 바꾸지 않는다.

ClearScope E3는 공식 confusion matrix에서 TP 1, FP 13,813이었고, 로그에 세 자리로 반올림된 threshold를 사용한 adapter seed 13,816개와 28개 체인의 교집합도 없었다. 정확한 threshold가 보존되지 않은 이 실행은 matched-budget 주 결과로 사용하지 않는다.

CADETS E3 공식 재현은 train 2·3·4·5·7·8·9일, validation 10일, test 6·11·12·13일을 사용했다. 정확한 threshold `9.57309627532959`에서 공식 seed는 1,103개였다. 결합 규칙은 1,122개를 보고해 악성 node 30개를 회수했고 동일 예산 공식 score top-k는 23개를 회수했다. cutoff 동점 세 node는 모두 정상이었다.

CADETS 결과를 본 뒤 코드, 비교 규칙, tie-break와 체인 상수를 고정했다. THEIA E3는 공식 분할 train 2–8일, validation 9일, test 10·12·13일과 정확한 threshold `7.088447093963623`을 사용했다. 공식 seed 503개가 1,155개로 확장됐고 악성 node 회수는 동일 예산 공식 score top-k의 16개에서 27개로 증가했다. cutoff 동점 191개 중 악성은 한 개여서 어떤 tie-break에서도 비교군은 최대 17개다.

다섯 공격 파일의 차이는 `+1, +5, +3, +3, +8`이다. 파일 독립성을 가정한 정확 단측 sign test는 `p=0.03125`지만 표본이 작고 의존 가능성이 있으므로 보조 근거로만 보고한다. 이 단계는 matched-budget node attribution만 평가하며 detector AP 개선, 공격 실행 성공률, 저오탐 alert 또는 E5 일반화를 주장하지 않는다.

### FlowSub 수학적 선택

2026-07-30 KST에 새 metric을 읽기 전에 다음을 등록했다.

- 후보는 공식 strict-threshold seed와 seed-overlap 동결 체인의 실제 endpoint 중 공식 score universe에 속한 node의 합집합이다.
- 보고 예산은 공식 seed 수와 정확히 같다.
- Predicate reliability는 endpoint evidence noisy-OR, node responsibility는 삭제 후 chain reliability의 상대 감소다.
- Edge score는 연속 predicate의 공통 endpoint에 local evidence 기하평균 비율로 보존 배분한다.
- Detector percentile과 causal evidence의 기하평균을 utility로 사용한다.
- 정규화 detector 보존과 포화 chain coverage의 합을 greedy로 최대화하고 UUID 내림차순으로 동점을 처리한다.
- anomaly-only, responsibility-only, flow-only, full을 같은 후보와 예산에서 평가한다.
- CADETS는 개발 판정이고 THEIA는 이미 이전 연구에서 label을 관측했으므로 회고적 전이 검사다.
- 결과를 본 뒤 수식, 가중치, score transform, budget, tie-break 또는 chain 상수를 변경하지 않는다.

CADETS label-free manifest SHA-256은 `d24e97dd40b08f1f87055262368e7a80fc64eb125defa3857f3b0c3fa9aa57e4`다. 공식 seed와 같은 1,103개 예산에서 악성 node는 23개에서 29개로 늘었다. 세 공격 파일은 `2→3`, `17→22`, `5→7`이었다.

동일 코드를 적용한 THEIA label-free manifest SHA-256은 `e15062739c3fc46836b9f19433bed055a4d350c4b5562521332f26842bb3ece0`다. 같은 503개 예산에서 악성 node는 16개에서 25개로 늘었고 두 공격 파일은 `12→15`, `4→10`이었다.

두 데이터 모두 full과 responsibility-only가 같은 node를 선택했다. Flow-only는 CADETS에서 anomaly-only와 같았고 THEIA에서 악성 node 하나만 더 회수했다. 따라서 joint flow 성능 기여는 기각하고, 성능 주장은 exact counterfactual responsibility와 submodular budget exchange로 제한한다. 보존 flow는 결과를 본 뒤 제거하거나 재가중하지 않고 공리적 보조 항과 음성 ablation으로 유지한다. 이 회고적 전이 결과로 E5/CDM20 일반화를 주장하지 않는다.

### BEAR와 RAVEL 단일-ledger 개발

FlowSub가 기존 수학 요소의 결합이라는 한계를 분리하기 위해 BEAR를 먼저 등록했다. BEAR v1은 validation-conformal e-value, 모든 frozen trace route의 branching capital, exact global node deletion을 하나의 ledger로 정의했다. CADETS label-free manifest 해시는 `7f72f5e5b67afdffa941b1008d40be0aef12e2bd9c6d9ea3b27604743a3feccb`, THEIA는 `bdd87b1892346a591eecd290294fe1a9904207cb55a8a2182d5a8ac3fff51aa5`다.

BEAR v1은 같은 예산에서 CADETS를 `23→26`으로 개선했지만 THEIA는 `16→16`이었다. THEIA의 label-free ledger가 local 22.7750, chain 0.5657로 분해돼 곱셈 route의 길이 감쇠가 확인됐다. 단위 단계 성장률을 사용한 v2를 별도 등록했으나 CADETS가 22로 악화돼 종료했다. v1과 v2 결과를 모두 보존하고 formula를 덮어쓰지 않았다.

RAVEL은 2026-07-30 KST에 root-conditioned proof account로 별도 등록했다.

- Official strict-threshold seed만 proof account를 연다.
- Root-overlap과 모든 인접 endpoint bridge를 만족한 chain만 admit한다.
- Root gate, predicate endpoint, bridge를 proof clause로 사용한다.
- 반복 UUID evidence는 proof 길이와 출현 횟수로 나눈 지수를 사용한다.
- Node 점수는 global proof ledger의 exact intervention loss다.
- Official seed budget, candidate rule, e-value calibration, UUID tie-break는 label-free로 고정한다.

RAVEL v1 CADETS manifest 해시는 `ba31a96a24027f10076bcb6f034c238d818f5ada9440b81118a9832fde67da91`다. Hold route가 root evidence를 이중 사용해 full은 23, expansion-only는 28이었다. Root를 값 1의 조건 gate로 바꾼 v2를 별도 등록했다.

RAVEL v2 CADETS manifest 해시는 `cbf4e47bdaecabc6ad890304b6d69648dedb5e56885076bdb1322b9a64378eb4`이며 결과는 `23→28`이다. 동일 코드를 적용한 THEIA 해시는 `559199fa0522ec5a404bbf39a39add1079822c3faac31cd1779d5ba6c1197252`이고 결과는 `16→17`이다. THEIA 공격별 결과가 `12,4→5,12`여서 강건한 전이는 기각했다.

마지막으로 root 계정별 자본을 한 단위로 정규화한 v3를 등록했다. CADETS manifest 해시는 `0a1dec377ed14a8c3e9048213ce1af7e68c62e91b3c4f2f21312d1ca04eac75a`다. Unit-ledger와 root-floor 정리는 성립했지만 결과는 23으로 baseline과 같았다. 사전 규칙에 따라 THEIA를 실행하거나 수식을 더 수정하지 않았다.

CADETS와 THEIA label은 이전 방법에서 이미 관측됐으므로 RAVEL의 모든 수치는 개발 진단이다. FlowSub를 대체하는 성능 주장, 최초 사용, 외부 일반화, anytime-valid false-alarm control은 주장하지 않는다.

### OpTC H051 미관측 외부 검사

2026-07-30 KST에 H051 payload와 node label을 열기 전에 RAVEL v2, endpoint-type relation adapter, 공식 PIDSMaker split, pretrained tuned Velox 설정, `max_val_loss` threshold, strict-threshold seed 예산을 등록했다. 공식 예산이 0이거나 seed-anchored continuous proof가 없으면 threshold·top-k·adapter·RAVEL 식을 바꾸지 않고 불확정으로 종료하도록 했다.

실행 결과 validation threshold `18.091964721679688`이 test 최대 score `13.815710067749023`보다 높아 1,470,624개 score node 중 seed가 0개였다. Label-free chain은 140개였지만 root account를 연 chain은 없었다. Ordered manifest SHA-256은 `6f23c493d7e188f1e7ba62bc2efc9d4a2782747484ed8c5d49b51da80c39caea`다. 등록 규칙에 따라 RAVEL selector와 label-only evaluator를 실행하지 않았으며 결과를 `inconclusive_zero_official_budget`로 고정했다.

H051 zero-budget 결과 뒤 H051에는 다른 예산을 사후 적용하지 않았다. 2026-07-30 KST에 payload와 label을 열지 않은 H501·H201 전용 replication을 별도 등록했다. H501을 primary, H201을 mandatory replication으로 지정하고 두 데이터 모두 official top-512 대 RAVEL v2 512-node 비교를 사용한다. Adapter, proof ledger, calibration, candidate, tie-break는 H051 버전으로 동결하며 official strict threshold는 별도 calibration 진단으로 모두 보고한다. H501 결과와 무관하게 H201을 실행하고, 각 데이터의 score·route·RAVEL manifest를 label evaluator보다 먼저 해시한다.

### RAVEL v4 proof-mass transport

2026-07-30 23:30 KST에 H501·H201 payload와 label을 열기 전에 RAVEL v4를 등록했다. CADETS와 THEIA의 label은 이미 관측됐으므로 v4 수식 선택이나 외부 주장에 사용하지 않는다.

- v2의 root gate, relation adapter, proof admission, conformal calibration, route capital과 반복 evidence 보정을 변경하지 않는다.
- 각 공식 root는 정확히 \(1/B\)의 조사 질량을 공급한다.
- 각 후보 node는 최대 \(1/B\)만 받을 수 있다.
- Root의 자기 보존 간선은 singleton detector proof이고, 비root 간선은 해당 root 계정에서 그 node를 제거한 정확한 route-capital 손실이다.
- 다른 공식 root는 비root 운반 후보에서 제외하고 자기 계정에서만 보존한다.
- 모든 root-node 간선을 비음수 utility, node e-value, root UUID, node UUID 순으로 정렬한 greedy matching을 한 번 실행한다.
- Matching은 root마다 간선 하나, node마다 간선 하나를 허용하고 정확히 \(B\)개의 서로 다른 node를 반환한다.
- Budget, tie-break, utility 정규화, route 상수와 adapter는 외부 결과를 본 뒤 변경하지 않는다.

H501과 H201은 모두 official top-512, RAVEL v2, FlowSub, RAVEL v4를 같은 score universe와 512-node 예산에서 비교한다. V4의 주 성공 조건은 두 데이터에서 official top-512보다 aggregate malicious node를 더 많이 회수하고, 개별 attack segment의 회수 수가 official보다 감소하지 않는 것이다. H501 결과와 무관하게 H201을 같은 코드로 실행한다. 조건을 하나라도 충족하지 못하면 외부 강건성 주장을 기각하고 수식을 사후 수정하지 않는다.

Label을 열기 전에 다음 구조 조건을 모두 확인한다.

- 모든 root의 transport degree가 정확히 1이다.
- 모든 선택 node의 수신 degree가 최대 1이다.
- 총 운반 질량은 1이고 선택 수는 정확히 512다.
- 적어도 하나의 admitted proof와 비root transport가 존재한다.
- Score, route, v2, FlowSub, v4 ordered manifest의 SHA-256을 기록한다.

Admitted proof나 비root transport가 없으면 성능 실패가 아니라 구조적 불확정으로 종료한다. Strict-threshold alert 수, runtime, memory, attack-free 출력, precision, recall, MCC와 attack-level recovery를 별도로 보고하며 사후 composite metric은 만들지 않는다.

V4의 label-free 실제 규모 구조 검사는 CADETS와 THEIA에서 각각 정확히 1,103개와 503개의 서로 다른 node, root degree 1, node degree 1, 총 질량 1을 반환했다. 그러나 두 데이터 모두 비root transport가 0개였다. Root singleton utility는 CADETS `55.6108–166.8323`, THEIA `23.1803–92.7214`였고 proof utility 최댓값은 각각 `0.5143`, `0.4014`였다. Proof/local 최대 비율도 `0.00617`, `0.00866`에 불과했다. Ordered manifest SHA-256은 CADETS `3209cbf3b39a3d7fc8e6733772e20879368895a1015119888b6a3ac19eb5ccdc`, THEIA `e9059e485ce4f010952b6167fafaed7442263fa2eb8cc4e97ce109b4209e3c3b`다. Label evaluator는 실행하지 않았고 v4를 구조적으로 기각했다.

### RAVEL v5 conditional transport

2026-07-30 23:38 KST에 benchmark label을 열지 않고 v4의 scale 진단만 본 뒤 v5를 등록했다. V4는 root를 account gate로 조건화하면서도 singleton utility에 \(e_s\)를 다시 사용해 detector observation을 서로 다른 scale에서 재사용했다.

- Root는 이미 top-512 detector 선택을 통과한 조건이므로 transport utility에서 root score 크기를 다시 사용하지 않는다.
- 자기 간선은 utility 0인 hold fallback이다.
- 비root utility는 root account 전체 route capital에 대한 정확한 상대 intervention loss다.

\[
u^{(5)}_{ss}=0,\qquad
u^{(5)}_{sv}
=
\frac{\sum_{c\in\mathcal C_s}(G_{sc}-G_{sc}^{-v})}
{\sum_{c\in\mathcal C_s}G_{sc}}.
\]

- Route가 없거나 양의 proof utility가 없으면 자기 간선을 선택한다.
- Matching, capacity, evidence repetition correction, adapter, budget와 deterministic tie-break는 v4에서 바꾸지 않는다.
- CADETS와 THEIA에서는 label-free 구조 검사와 runtime만 허용하며 metric evaluator는 실행하지 않는다.
- H501과 H201 모두에서 exact 512 budget, root/node degree, mass, admitted proof와 비root transport를 먼저 확인하고 ordered manifest를 해시한다.
- 외부 성공 조건과 H501 결과와 무관한 H201 mandatory replication은 v4 등록과 동일하다.

V5가 기존 개발 manifest에서도 비root transport를 만들지 못하면 외부 실행 전에 기각한다. 비root transport가 생기더라도 CADETS/THEIA TP는 계산하지 않고 H501/H201에서만 성능 판정을 내린다.

V5 label-free 구조 검사는 CADETS에서 1,103개 중 9개, THEIA에서 503개 중 13개 슬롯을 비root proof node로 운반했다. 두 데이터 모두 root 수, 고유 node 수와 선택 예산이 같고 총 질량은 1이었다. Ordered manifest SHA-256은 CADETS `4cbd9dfbcb80f50f90c3f2148aa01b04d4375ed7a6483fd448b6a8111bb4977b`, THEIA `58ede116e2e8f44ec437f01ba5fc1f62a9ce819ed01371a9725c6f9786554a7a`다. Metric evaluator와 label 파일은 열지 않았다. H67의 구조 조건이 충족돼 v5 수식과 코드를 외부 실행용으로 동결한다.

동결 코드 SHA-256은 `src/wisa_agent/tc/ravel.py` `303dd8c29326d30a3924e8316a3e5cdc5413494f8e8f12911eab13807ceba596`, `experiments/ravel.py` `71c46ffc74922a9cd1be7fc9f0ec539c50bc6b0adef0493a039715f5cfe9a59e`, `tests/test_ravel.py` `8a99dfc3d07609fecf0abb38c17de7b05aba072ed72af59bce6e980276ed6113`이다.

H201 공개 encoder와 Word2Vec 가중치도 label 접근 없이 확보했다. SHA-256은 각각 `68ae33ffe9ae05671388cb8db70032d2f8fa938cdb5e0fe0b779c8b62a3e6c1e`, `3a97e6c8e21e4e7734343413945ac632f4891389ba72c6ae15341ccfc830dcbf`다. H501·H201 database dump의 익명 요청은 Google Drive shared-file quota로 중단됐고 partial payload는 생성되지 않았다. 공식 `drive.readonly` OAuth 경로로만 재개한다.

### RAVEL v6 exact transport

2026-07-31 00:20 KST에 H501·H201 payload와 label을 열기 전에 v6를 등록했다. V5의 proof admission, 조건부 route capital, 상대 intervention utility, 후보, 예산과 모든 tie 입력은 변경하지 않는다. 유일한 방법 변경은 greedy matching을 sparse successive-shortest-augmenting-path로 계산하는 exact maximum-weight matching으로 교체하는 것이다.

\[
x^\star\in\arg\max_x
\sum_{s\in R}\sum_{v\in V}u^{(5)}_{sv}x_{sv}
\quad
\text{s.t.}\quad
\sum_vx_{sv}=1,\quad
\sum_sx_{sv}\le1,\quad
x_{sv}\in\{0,1\}.
\]

각 root의 고유한 0-utility hold 간선 때문에 항상 크기 \(B\)인 feasible matching이 존재한다. 모든 간선 비용을 \(c_{sv}=u_{\max}-u^{(5)}_{sv}\)로 바꾸면 크기 \(B\)의 최대 utility matching은 최소비용 흐름과 동치다. V6는 이 흐름을 완전히 augment하며 근사 오차를 제거한다.

- V5 파일과 해시는 수정하지 않고 v6를 별도 모듈과 실행 파일로 구현한다.
- 합성 그래프에서 exhaustive optimum과 일치하고 root degree 1, node degree 최대 1, 정확한 예산과 질량 1을 검사한다.
- CADETS·THEIA에서는 label-free 구조, objective와 runtime만 비교하고 malicious-node evaluator를 실행하지 않는다.
- Exact objective가 v5 greedy보다 작거나 실행이 30분 또는 16 GiB를 넘으면 v6를 구현 실패로 보존하고 v5를 대체하지 않는다.
- H501·H201에서는 v6를 primary로 고정하고 결과와 무관하게 두 데이터 모두 실행한다. V5는 등록된 근사 ablation으로만 보고한다.
- 외부 성공 조건은 두 데이터 모두 official top-512보다 aggregate malicious node를 더 많이 회수하고 어떤 attack segment도 감소시키지 않는 것이다. 실패 시 exact proof utility와 malicious-node utility의 정렬 가설을 기각하며 v5로 사후 선택하지 않는다.

Label-free 실제 규모 검사는 CADETS와 THEIA에서 각각 6.10초와 12.18초가 걸렸다. CADETS objective는 greedy `3.176186755806323`에서 exact `3.178596548868447`로 증가했고 THEIA는 두 방법 모두 `4.130597958185422`였다. Proof transport 수는 각각 9개와 13개였다. 모든 root/node degree, 예산과 질량 검사를 통과했으며 metric evaluator는 실행하지 않았다.

Ordered manifest SHA-256은 CADETS `48470cf2087ebddfe912a20f8d78a869f6a23f5f79a1d0d185858070149b8e55`, THEIA `190d48b221c4892b96eda8627648812d0758da8b32222fe53d28d4f44b041e30`이다. V6 코드 SHA-256은 `src/wisa_agent/tc/transport.py` `97b24bb8822247fab322944a9624e953b109bdc7737b21099e0e173998604c73`, `experiments/transport.py` `e18382dafd0fd64e38fa86f2759ba8285e7888cc3d01041e0c25cae8da726904`, `tests/test_transport.py` `d02086f9d83aa1330a52695d87b20b40af092efbe796e80df407b2864e3d37e7`이다.

### V6 외부 진단 대조군

2026-07-31 01:50 KST에 H501·H201의 수정 ground truth를 열기 전에 exact matching과 후보 그래프는 그대로 두고 utility만 바꾸는 두 진단 대조군을 등록했다.

- `topology`: proof edge utility를 1, private hold를 0으로 두어 연결 가능한 proof slot 수만 최대화한다.
- `rank`: proof edge utility를 \(1-p_v=1-1/(4e_v^2)\), private hold를 0으로 두어 exact intervention 없이 validation rank만 사용한다.
- 두 대조군은 v6와 같은 root, route, 후보, 예산 512, node capacity와 tie-break를 사용한다.
- 외부 성공 조건은 계속 v6 대 official Velox 비교만으로 판정한다. 대조군이 더 좋더라도 주 방법으로 사후 교체하지 않으며, topology·rank·exact deletion 중 어느 요소가 결과를 만든 것인지 진단하는 데만 사용한다.
- H501·H201의 score, route, v5, v6와 두 대조군 manifest를 모두 해시한 뒤에만 label evaluator를 실행한다.

Label-free E3 구조 검사에서 CADETS는 세 방법 모두 9개, THEIA는 모두 13개의 proof transport를 만들었다. V6와 비교한 선택 변경 수는 topology가 CADETS 2, THEIA 12이고 rank가 CADETS 2, THEIA 10이다. 이는 proof transport 수가 utility 선택보다 root-anchored 후보 그래프의 reachability에 의해 제한된다는 사전 진단이다. Label metric은 계산하지 않았다.

코드 SHA-256은 `experiments/transport_ablation.py` `abd60b9906690b97777d70aa9791a43993b69fcbdb1f4f233fe7d7bb060f4716`, `tests/test_transport_ablation.py` `031401677d7996057e5e9084da455a24b994c4c2959d46ba44ded8cd7973dc8e`이다. Label-only 진단 evaluator와 테스트 SHA-256은 `experiments/optc_ablation_eval.py` `0471229cdc5d4b9b3e58014bb68343690a06260c74e2453ee769c58d40074eac`, `tests/test_optc_ablation_eval.py` `cd6ef48bcab11437aeb4c991f2beb93572bd960eb72759d88d916c0cf7adb8a9`이다. E3 manifest SHA-256은 CADETS `89cc606f0fa16b99742f1440148520c71d8448038bb27a13b6a46bc73cb6f650`, THEIA `7e7aaa053ca61c4d121c90c6a30a0926eb53a0292f7342b4d3c6bc55d4435264`이다.

### 수정 OpTC 독립 재현

2026-07-31 01:08 KST에 H201·H501의 수정 raw payload와 ground-truth 내용을 열기 전에 독립 재현을 등록했다. 데이터는 Majorczyk et al.의 수정 OpTC 공개본 DOI `10.57745/UXCWOC`, 라벨·정정 코드는 GitLab commit `644f41fb0a955e471f34bed016fb2bfd9c74dc04`를 사용한다.

- 2026-07-31에 조회한 일별 TAR 7개의 H201·H501 멤버 14개는 총 `3,361,000,242` byte다.
- Range로 스캔한 ordered archive index SHA-256은 `7e6c6121ef812bb9129f68826d4c1ca6b58586d0cbb5622bb1b15516b67dff6e`다.
- 공식 코드 archive SHA-256은 `e7edb1411f22856f81df643314ec2fac12295f803dd136e8747e29e1ae7e0e5e`, 논문 PDF SHA-256은 `dfec5193ce493596b121da0a994b64b21133d1b5bd81c034a3e32bdf1edd60f1`다.
- 원래 등록한 PIDSMaker PostgreSQL dump 평가는 primary로 유지한다. 수정 raw 평가는 이를 대체하거나 같은 수치로 합치지 않는 독립 robustness replication이다.
- 분할은 두 경로 모두 19–21일 train, 22일 validation, 23–25일 test로 고정한다.
- H501을 primary host, H201을 mandatory replication host로 유지하며 H501 결과와 관계없이 둘 다 실행한다.
- RAVEL v6, endpoint relation adapter, exact matching, root budget 512, 후보 규칙과 tie-break를 수정하지 않는다.
- Detector는 PIDSMaker `velox`의 host별 tuned 설정과 `--from_weights` 경로를 사용한다. 공개 Word2Vec와 encoder를 불러온 뒤 공식 코드가 정한 정상 train 1 epoch를 그대로 실행하며 test label로 epoch나 threshold를 선택하지 않는다.
- H201 encoder, Word2Vec, tuned YAML SHA-256은 각각 `68ae33ffe9ae05671388cb8db70032d2f8fa938cdb5e0fe0b779c8b62a3e6c1e`, `3a97e6c8e21e4e7734343413945ac632f4891389ba72c6ae15341ccfc830dcbf`, `0a9b29ed4ed201f55639076da3e6ee87acae784d8570096563aeeda6a6a1e736`이다.
- H501 encoder, Word2Vec, tuned YAML SHA-256은 각각 `1e4cb8d12575a91fa0f3572e8d261af843f7ba622e62af42c239ddd825ddda13`, `f927d4f02268d2fbc6262da349a7fa956139cebb941941283bdb68804efaefc1`, `ddfd61a074d9d56d87f955d4dd508df9ae96afed39bf09791bbea5e07c08ae27`이다.
- 수정 raw를 PIDSMaker의 세 node type과 열 relation으로 투영할 때 버려진 object type·relation과 event 수를 모두 보고한다. 이 투영 결과를 공식 dump 재현이라고 부르지 않는다.
- 각 host의 score, route, v5, v6 ordered manifest를 먼저 생성하고 SHA-256을 기록하기 전까지 ground-truth 파일 내용을 읽지 않는다.
- 수정 라벨의 malicious node set은 저자들이 공개한 host별 corrected ground-truth event에서 `actorID`로 등장하는 process UUID의 집합으로 고정한다. PIDSMaker·ORTHRUS node UUID 라벨과 합치지 않고 별도 결과로 보고한다.
- H201은 저자 scenario 1의 23일 파일, H501은 scenario 2의 24–25일 파일에 대응한다. Host별 `ground_truth_corrected_sc?_updated.csv`의 각 `hostname,pid,start,end` 행을 process-interval segment로 고정하고, 해당 구간의 corrected event에 나타난 `actorID` UUID를 segment label로 사용한다.
- Segment별 전체 label 수, detector score universe와의 교집합, official top-512와 v6 회수 수를 모두 보고한다. Score universe와 교집합이 비어 있는 segment도 누락하지 않되 no-decrease 판정에서는 비어 있지 않은 segment만 사용한다.
- 성공 조건은 두 host 모두에서 동일한 512개 공식 detector root보다 v6가 aggregate malicious node를 더 많이 회수하고, 어떤 저자 정의 attack segment도 감소시키지 않는 것이다.
- 하나라도 실패하면 외부 성능 우월성 주장을 기각한다. 수정 라벨을 본 뒤 raw projection, 예산, 수식, transport 버전이나 host를 선택하지 않는다.

라벨 디렉터리명과 파일명은 코드 archive의 계보 확인을 위해 열람했지만 압축된 ground-truth payload와 CSV 내용은 열지 않았다. 다운로드·무결성 검증·label-free 변환·manifest 해시 순서가 완료된 뒤에만 evaluator가 라벨을 연다.

동결 projection·stream·route 코드는 `experiments/optc.py` `b67e080f448fcea9a38207cea25ddf783684e75fa5280b989721b318af12e141`, `experiments/pg_events.py` `dc1919cc07f2ac4d5e34e34aa1654dbb3272ae848720e6e9d3edba7f249e1145`, `experiments/flow.py` `a3abce692e7ae0f8c219ffdeed65bae2780d512159a077b54b5f12ad89de49b3`, `experiments/velox_chain.py` `0e7fb0d4cee7893672d97ff52692ba756e13452f21e7919d8fc545f279612765`이다. 마지막 변경은 selection 계산을 바꾸지 않고 root manifest에 `velox` 또는 `ravel_tgn` detector identity를 기록한다.

2026-07-31 01:52 KST에 label을 열기 전 evaluator의 사전 명시된 precision·covered recall·MCC 보고를 완성하고, 같은 universe에서 512개를 균등 비복원 추출했을 때의 기대 회수 수와 관측값 이상 hypergeometric tail probability를 기술적 sanity reference로 추가했다. 이 확률은 외부 일반화 검정이나 성공 조건으로 사용하지 않는다. 최종 evaluator SHA-256은 `experiments/optc_eval.py` `3202cd2cd02ab7666066d5fa92065a59c63e309216c8d71df63d98e7ccd63444`, 테스트는 `tests/test_optc_eval.py` `aa187bb4c3caec469fd25da13234f345e3ff2866e3897648801136573bffb5ba`이다.

Label 접근 전 산출물 목록을 단일 ordered hash manifest로 묶는 도구와 테스트 SHA-256은 `experiments/freeze.py` `48887776cbc30dbe9e03f1a587cbdbb87711a961c06794991b3a068600c6b8de`, `tests/test_freeze.py` `38bc83d45b07b7345c1a5a5b0a670f0e50fcbf16a169ff830c5f8a1f3d7bf4b3`이다.

### 수정 OpTC matched-backbone 진단

2026-07-31 02:12 KST에 corrected H501·H201 label을 열기 전에 detector-interface 의존성을 검사할 secondary backbone을 등록했다. `ravel_tgn`은 tuned Velox와 graph construction, transformation, 64차원 feature Word2Vec, seed 16, edge decoder, learning rate와 node output dimension을 동일하게 두고, 비활성 encoder를 PIDSMaker의 TGN과 graph-attention block으로 바꾼다. GNN은 seed 0으로 8 epoch를 모두 실행한다. 공개 코드에서 patience 3은 설정돼 있지만 early-stop 조건이 비활성화돼 있으므로 사용하지 않으며, label-free final epoch 7의 validation/test loss를 고정 사용한다. Label task는 차단한다.

- 이 대조군은 ORTHRUS 전체를 복제했다는 주장이 아니라, feature와 decoder를 맞춘 learned temporal-graph backbone이다.
- Velox와 같은 preprocessing·embedding task hash를 사용하고 GNN training hash만 달라 저장공간과 입력 표현을 통제한다.
- 각 host에서 `ravel_tgn` top-512와 그 root로 연 RAVEL v6 512개를 비교한다. Route, utility, exact matching, 대조군과 evaluator는 Velox 실험과 동일하다.
- 이 결과는 detector-interface 강건성 진단이며 Velox 기반의 주 성공 조건을 대체하거나 합산하지 않는다. 더 잘 나온 backbone을 사후 primary로 선택하지 않는다.
- H501의 Velox·TGN score, route, v5, v6와 utility 대조군 manifest를 모두 해시한 뒤 H501 label을 열고, H201도 이미 고정된 동일 설정으로 결과와 무관하게 반복한다.

Config SHA-256은 `config/tgn.yml` `263a0767291c765a8da8605a8b1604d83b3ceb79f724abccea5ff885edfa235d`이다. H501에서 Velox와 TGN이 공유하는 label-free task hash는 build graph `d50fabc62606116eba14c7c6804209a1c29e99f777c25e889c652d0da3e07823`, transformation `16eb81e473a1d9b9709850731a43c1462fff39b31a5aedf1d2adcae912a1a913`, node embedding `ac325f95bb92da6a45f4ec0a68551104b0fb09d70af8314873a0adcce34e30db`, edge embedding `be01c4c3d7146d66c756c5f3cc8a5a8c31a5c2d2994c9d3690995d2b7e70dc38`이다. GNN task hash는 Velox `b40930393cc41ce1873e5408195b91e2bd7cafe689463a212b8f628081c1a485`, TGN `0d906db11edd2efc663b57c51f4fbcd359c1435c6d7cda64c53a06a3dd1e9bcc`로 분리된다.

### 수정 OpTC 짝지은 기술 통계

2026-07-31 02:34 KST에 H501·H201 수정 ground truth를 열기 전에 label evaluator v2를 등록했다. 기존 exact-budget precision, covered recall, MCC와 무작위 budget hypergeometric 진단은 유지한다. 여기에 Velox와 RAVEL의 같은 크기 대칭차를 조건으로, 바뀐 slot의 악성 actorID가 어느 선택에 집중되는지 one-sided와 two-sided exact hypergeometric 확률을 보고한다. 이는 두 동결 선택의 기술 통계이며 일반화 검정이나 성공 조건으로 사용하지 않는다. 주 성공 조건은 기존 aggregate improvement와 segment no-decline의 결합을 그대로 유지한다.

Evaluator와 테스트 SHA-256은 각각 `experiments/optc_eval.py` `3d3ac65f464077459ab3ba8023bddde510ae342d83670776adcb465f434ee2e6`, `tests/test_optc_eval.py` `08af41a585f325cb0e34be2f1d17cd7dd27ea36e468a6f9a54005333841e4f89`이다.

### Root-score 불변성 명세 정정

2026-07-31 02:40 KST에 H501 수정 ground truth를 열기 전에 논문의 root-score 불변성 범위를 구현과 다시 대조했다. 구현은 각 root를 자기 account에서 값 1의 gate로 조건화하므로 그 root가 소유한 utility는 자기 score 크기에 불변이다. 그러나 한 detector root가 다른 root의 typed proof endpoint로 등장하면 그 다른 account에서는 calibrated provenance evidence로 남는다. 따라서 전역 transport graph와 matching의 root-score 불변성은 root-separated account에서만 성립한다. 논문 정리를 own-account 불변성으로 좁히고 cross-account 경계 테스트를 추가했다. 수식, selector, 외부 manifest와 성공 조건은 바꾸지 않았다.

경계 테스트 SHA-256은 `tests/test_ravel.py` `37f07fa7510152ad23cc128e5618967bb9113ce345d079187c9bc2b5dd3528c2`, `tests/test_transport.py` `0e9760d8e812b1b2110b48d2e407131ef346e72cff6fe30d07e5412d88d411f5`이다.

### Secondary backbone 해석 경계

2026-07-31 02:50 KST에 H501 수정 ground truth를 열기 전에 `ravel_tgn`의 비교 범위를 명확히 했다. TGN과 Velox는 graph, public feature Word2Vec, decoder, learning rate와 representation dimension을 공유한다. 그러나 primary Velox는 public pretrained encoder를 불러 등록된 one-epoch inference path를 실행하고 TGN은 corrected train split에서 label 없이 8 epoch 학습한다. 따라서 secondary 결과는 input-matched architecture-sensitivity 진단이며 통제된 encoder-only ablation으로 주장하지 않는다. Primary 선택, 성공 조건과 합산 금지는 그대로다.

### FlowSub 선택 동치 최적화

2026-07-31 04:18 KST에 H501 수정 ground truth를 열기 전, route manifest에 함께 보존하는 FlowSub 네 모드의 전수 greedy가 실제 규모에서 40분 이상 걸리는 병목을 확인했다. 목적함수의 marginal은 선택된 node가 속한 chain에서만 변하므로, 현재 gain을 heap에 저장하고 영향을 받은 chain의 후보만 다시 계산하는 exact lazy update로 교체했다. 원래 전수 scan은 `lazy=False` 경로로 보존했다.

네 모드와 모든 가능한 budget의 단위 사례에서 node 순서, gain과 objective가 전수 scan과 정확히 같았고, 동률에서 UUID 역사전식 선택도 같았다. 11,058개 동률 후보와 budget 512인 synthetic anomaly 선택에서는 같은 출력으로 73.0배 빨랐다. 이 변경은 chain 생성, route admission, RAVEL utility, exact matching, root budget, 성공 조건과 label evaluator를 바꾸지 않는다. 동결 코드와 테스트 SHA-256은 각각 `src/wisa_agent/tc/flow.py` `92b94bd631ec7eca9f6d0cb78fa11dcc905fdea186b443b12aa768e3c23b3cc2`, `tests/test_flow.py` `5058e5612855f809c6967253f6346123dd524d60f8fe4a21fb063aef89ead6a8`이다.

같은 시각에 conditioned·non-conserved v5에서 정의와 구현상 동일한 `chain`과 `full` ledger·삭제 손실을 두 번 계산하는 중복도 제거했다. `full`은 이미 계산한 `chain`의 같은 부동소수 값을 복사하며, 비조건부와 conserved 경로는 바꾸지 않는다. 이어서 transport가 전역 `ledger.losses`와 membership을 출력·utility·matching 어디에도 사용하지 않으면서 계산하던 dead work를 제거했다. 직접 ledger selector는 기본값으로 기존 loss와 membership 계산을 유지하고, `RavelTransport`만 `compute_losses=False`, `compute_memberships=False`를 사용한다. 두 계산을 수행한 ledger와 생략한 ledger의 e-value, account, route value와 ledger 값이 완전히 같음을 별도 회귀 테스트로 확인했다. 24개 RAVEL·transport 회귀 테스트가 통과했다. 코드와 테스트 SHA-256은 각각 `src/wisa_agent/tc/ravel.py` `6513c6a2e96b82dfd14ababf51a850fa2428f0d361dea45c6f7f84a4ea8e4ea9`, `tests/test_ravel.py` `3be3e76a6aea8eefb0cbec847fdd4c7cf6b3cd143ac67bd0d21ec16c9d92e6c0`이다.

Label barrier를 사람이 파일명만 보고 통과시키지 않도록 frozen bundle 감사기를 추가했다. 감사기는 manifest의 byte 수와 SHA-256을 다시 계산하고, score→route→v5/v6/ablation 입력 해시 연결, 512개 고유 root와 선택 node, score universe 포함 관계, predicate endpoint 중복, exact certificate의 root·node degree·mass·objective·optimal flag를 검사한다. 완전 bundle과 변조 파일 회귀 테스트를 포함한 관련 24개 테스트가 통과했다. 감사기와 테스트 SHA-256은 각각 `experiments/frozen_check.py` `b9ea6038bf637fe0e438aa7ba7f2ca9f8ddd20dc32f8d82ae4d7771193ac2424`, `tests/test_frozen_check.py` `9958ba333887f33b27561607c971fbda972b94132562a3a9465100a3c3a50381`이다.

### H501 최종 라벨 장벽

2026-07-31 06:58 KST에 수정 H501 ground truth 내용을 열기 전 최종 score·route·v5·v6·utility 대조군을 Velox와 TGN 백본 모두에서 동결하고 감사했다. Ordered frozen manifest SHA-256은 `4b7f3134ebe845b81ea5f150c2f37e80346228168a9767657148bcb04faa3179`, 감사 결과 SHA-256은 `36af313d3bba121e1258f28465ce3c378afcb9e4d6aaae1c68835debdb824566`이다.

- 두 백본 모두 score universe `1,488,666`, root와 출력 예산 `512`, root degree 1, node degree 최대 1, 질량 1과 `optimal=true`를 만족했다.
- Velox는 root-anchored chain 122개, v5 objective `15.696854851405314`, v6 objective `15.721660347192163`, proof transport 59개다. Topology와 rank 대조군도 각각 59개를 transport했다.
- TGN은 root-anchored chain 93개, v5 objective `18.325090085229455`, v6 objective `18.325096640375612`, proof transport 57개다. Topology와 rank 대조군도 각각 57개를 transport했다.
- 최종 Velox route, v5, v6와 ablation SHA-256은 각각 `23d94b390aff07de91f6161cada90b5a0dc8fd0e60ffc3257904a68e372c8cb4`, `533d5e55c18ee37e3db2af3c7392bc0cb0dd5b95cd206743a105ca516628fce1`, `5ef8a938cf3f6b84ed3af41159f0328c8c4c25c35bc6594748a4d0be39f0c13c`, `d9e5179a763c189481c9ffb4ec95b30aa46929728258d4c03ca1975c8064a410`이다.
- 최종 TGN score, route, v5, v6와 ablation SHA-256은 각각 `82c7aec8e1876f98dfecc847271638d068f9eae14e6d2e06fee13fab816df306`, `92517fe4f7d311c635688c03c08da19670270778b8e2677c26f62887b2b1a2c1`, `23f11044b372607e223943dd28c3e514b257dc7208c4bff40f8eb26ac9333320`, `844e7071e5eda9c09c69337b0a70dd8f1d89b4de51884a2e77b06608ccf51b11`, `dd33b5ee44b5ae406aa8c6f6ea2384aee4db0cd53c0a800ec6f957c2f45ff995`이다.

FlowSub lazy 경로로 다시 만든 Velox route는 runtime을 제외한 모든 field가 최적화 전 보존본과 byte-normalized 비교에서 같았다. V5, v6와 두 대조군도 입력 route hash와 runtime을 제외한 chain·selection·transport·certificate가 같았다. 그러나 Velox 실제 runtime은 최적화 전 `3746.35`초, 최종 `3743.83`초로 사실상 개선되지 않았고 TGN은 `525.58`초였다. 합성 동률 사례의 73배 가속은 실제 H501 가속으로 일반화하지 않는다.

### H501 라벨 공개 후 결과

최종 장벽을 통과한 뒤 공식 GitLab commit `644f41fb0a955e471f34bed016fb2bfd9c74dc04`에서 H501 수정 event label과 scenario 2 segment CSV만 sparse fetch했다. SHA-256은 각각 `302b849b2e462abadaef8987b21d34c363c4e4f84ec6abf44f861dffbb71bada`, `17d8286004e141db6b034f6acca4bf282429d32d092442b3188a3af0563fdba4`다. Labeled result manifest SHA-256은 `34822440cab5bbfe4acb2a32b8f2aebc32e776a94e638e7c20342a6478e889f7`이다.

- Corrected event 60,025개에서 score universe에 포함된 고유 악성 actorID는 86개였다.
- Velox top-512는 7개, v6는 10개를 회수해 precision `0.01367→0.01953`, covered recall `0.08140→0.11628`, MCC `0.03322→0.04752`로 증가했다.
- 같은 59개 변경 slot에서 baseline-only 악성 node는 4개, v6-only는 7개였다. 조건부 기술 통계의 one-sided 값은 `0.26425`이며 일반화 검정으로 사용하지 않는다.
- Topology-only는 3개, rank-only는 7개, exact deletion v6는 10개를 회수했다. H501 Velox 경로에서는 topology나 validation rank만으로 aggregate 이득을 설명할 수 없고, 등록한 node intervention utility가 추가 이득을 만들었다.
- TGN top-512는 2개, v6는 4개를 회수해 precision `0.00391→0.00781`, covered recall `0.02326→0.04651`, MCC `0.00939→0.01893`으로 증가했다. Topology-only는 1개, rank-only와 v6는 각각 4개였다.
- Velox 경로는 3개 segment에서 감소했고 TGN 경로는 1개 segment에서 감소했다. 따라서 aggregate improvement는 두 백본에서 모두 성립하지만 사전 등록한 `segment_no_decline`과 `host_success`는 모두 거짓이다.

H501은 엄격 성공 조건을 통과하지 못했다. 수식, candidate, detector, budget, utility, matching, segment 정의와 evaluator를 수정하지 않으며, 이 결과와 관계없이 H201 mandatory replication을 같은 코드와 설정으로 실행한다.

### H201 secondary-backbone fingerprint 경계

2026-07-31 08:01 KST에 H201 corrected event label과 segment CSV가 여전히 워크스테이션에 존재하지 않는 상태에서 secondary backbone의 실제 task lineage를 다시 감사했다. Primary Velox와 TGN은 같은 corrected raw host, 19--21/22/23--25 split, PIDSMaker 코드와 출력 예산을 사용하지만 전처리와 Word2Vec task fingerprint가 같지 않았다.

- Velox의 build graph, transformation, node embedding, edge embedding task hash는 각각 `920a9d9587a9b4ef00987cb0764965fb2f4453f0bb1983d28224141476e73cbd`, `644c07bb88db3f36aa48f205374ec8f4b020be6dbbfd4b1994c940015e3d4286`, `a8c6b5b8e11563b82caf6682eba3c08b119ab57a15843f89978f676bbc7b8377`, `88253d6354abdf33e3fdcaf7ec0a2c7be0b3e7f874e2cc6a3d0ad5359872bb37`이다.
- TGN 경로는 각각 `d50fabc62606116eba14c7c6804209a1c29e99f777c25e889c652d0da3e07823`, `16eb81e473a1d9b9709850731a43c1462fff39b31a5aedf1d2adcae912a1a913`, `ac325f95bb92da6a45f4ec0a68551104b0fb09d70af8314873a0adcce34e30db`, `be01c4c3d7146d66c756c5f3cc8a5a8c31a5c2d2994c9d3690995d2b7e70dc38`을 생성했다.
- 두 node-embedding 산출물의 Word2Vec SHA-256은 Velox `8a6a3ac9dd29de9c8fb43aab0de014031453abd689cb54340916483876fe057c`, TGN `8f01bcad5760866760f0105515e1d1f5264a8536b629b3367146cae5810fbe54`로 서로 다르다.
- 공개 H201 tuned Velox는 1분 graph window, embedding seed 0, node output 256을 사용하지만 등록된 TGN config는 15분 window, seed 16, node output 128을 사용한다. H501에서는 이 기본값들이 H501 tuned Velox와 일치했지만 H201에서는 일치하지 않는다.

따라서 H201 TGN 결과는 input-matched encoder ablation이 아니다. 동일 raw host와 split 위에서 encoder와 feature-pipeline lineage가 함께 달라지는 보조 architecture-sensitivity replication으로만 보고한다. Primary Velox 성공 조건을 대체하거나 두 결과 중 좋은 쪽을 선택하거나 합산하지 않는다.

### 동결 방법 대조군의 H201 사전 등록

2026-07-31 09:08 KST에 H201 corrected event label과 segment CSV가 여전히 워크스테이션에 존재하지 않는 상태에서, 이미 label-free bundle에 동결되는 FlowSub full 선택과 RAVEL v5 선택도 H201에서 평가하기로 등록했다. 이는 v6를 교체하거나 성공 조건을 바꾸는 절차가 아니라 다음 질문을 분리하기 위한 보조 비교다.

- `FlowSub full`은 E3에서 가장 강했던 복합 개발 대조군으로 anomaly, exact deletion responsibility와 submodular budget exchange를 결합한다.
- `RAVEL v5`는 v6와 proof utility가 같고 greedy allocation만 사용하므로 exact matching의 외부 metric 영향을 진단한다.
- Velox, FlowSub, v5, v6는 모두 같은 score universe와 512개 예산을 사용하며 score→route→v5/v6 해시 연결이 일치해야 evaluator가 실행된다.
- H201에서는 라벨 공개 전에 네 선택을 모두 동결하고 결과와 관계없이 전부 보고한다. V6 대 Velox의 기존 aggregate·segment 성공 조건은 바꾸지 않는다.
- H501에 이 비교를 추가하기로 한 결정은 H501 v6·ablation 라벨 결과를 이미 본 뒤이므로 명시적으로 post-hoc이다. 다만 비교 대상 FlowSub와 v5 선택 자체는 H501 label 공개 전에 `frozen-501.json`에 해시돼 있었으며 다시 계산하거나 고르지 않는다.
- V5가 v6보다 좋거나 FlowSub가 둘보다 좋아도 primary 방법을 사후 교체하지 않는다.

동결 방법 evaluator와 테스트 SHA-256은 각각 `experiments/optc_method_eval.py` `89029142fb2b71bda081804e66d00b095ec2b561ea39383ba6b50ae6d2a5d27c`, `tests/test_optc_method_eval.py` `164081f054ae80178c6f6a245cd5c776d4170069be8116c7fde469d9fffad226`이다. 출력에는 H501을 `post_hoc_after_host_labels`, H201을 `preregistered_before_host_labels`로 구분해 비교 결정 시점을 기계 판독 가능하게 남긴다. 기존 corrected evaluator와 함께 실행한 7개 회귀 테스트가 통과했다. 공격 adapter의 수식이나 계수, route, proof utility, matching과 frozen output은 이 평가 확장으로 바뀌지 않는다.

같은 label-absent 시점에 proof clause 곱이 모든 endpoint Cartesian-product realization의 합과 정확히 같고, 계산은 realization 수의 곱이 아니라 clause 크기의 합에 선형이라는 factorization 명제를 본문에 명시했다. 반복 UUID가 있는 합성 chain에서 factorized route와 모든 realization을 직접 열거한 값의 일치를 검사했고 RAVEL·transport 22개 테스트가 통과했다. 수정된 테스트 SHA-256은 `tests/test_ravel.py` `94c60b310fb645f8ff65c3725d4e8802a23db7851239121826fe2e41bdb6425b`이다. 이는 구현 수식과 동결 선택을 바꾸지 않는 명세·검증 강화다.

### 외부 데이터 경로 보고 경계

2026-07-31 09:18 KST에 H201 corrected label이 여전히 없는 상태에서 논문과 실행 기록을 대조했다. 최초 등록한 PIDSMaker H501·H201 PostgreSQL dump 경로는 Google Drive hosted artifact quota로 payload를 확보하지 못했고 score나 selection 결과가 존재하지 않는다. 이후 별도로 사전 등록한 corrected OpTC raw 경로만 H501을 완료했고 H201을 실행 중이다.

- 최종 논문은 corrected OpTC H501을 primary host, H201을 mandatory host replication으로 보고한다.
- Corrected 결과를 존재하지 않는 dump 결과에 대한 robustness delta, PIDSMaker dump 재현 또는 원본·수정 쌍 비교라고 부르지 않는다.
- 원래 dump 계획과 획득 실패는 삭제하지 않고 protocol과 limitation에 남긴다.
- Corrected raw의 PIDSMaker type/relation projection, public Velox config 사용과 detector identity를 구분해 보고한다.
- 이 보고 경계 정정은 외부 선택, 수식, 예산, label evaluator와 성공 조건을 바꾸지 않는다.

### Exact transport 독립 구현 감사

2026-07-31 09:39 KST에 H501 라벨은 이미 공개됐지만 H201 corrected label은 여전히 없는 상태에서, 동결된 SSAP 배정 구현을 SciPy `linear_sum_assignment`와 독립 교차 검사했다. 이 검사는 proof utility, 후보, 예산, tie 입력이나 외부 manifest를 바꾸지 않는다.

- Seed `20260731`로 2,000개 희소 이분 그래프를 생성했다.
- 각 그래프는 root 2–15개, 공유 node 1–20개, edge 확률 0.35, 동률을 포함한 8개 비음수 utility 값과 root별 private hold를 갖는다.
- 2,000개 모두에서 자체 SSAP와 SciPy 배정의 총 목적값이 절대 오차 `1e-12` 안에서 일치했다.
- 감사 스크립트와 결과 SHA-256은 각각 `b9f5a755389311e42d700b942c51439d763b50a6fbff8ebaac767aa8d8290885`, `bd353b303d60613dd7634036acaec83b029536a25fa22618983bdacebfc72a66`이다.

### FlowSub predicate lookup 실행 동치 최적화

2026-07-31 10:40 KST에 H501 라벨은 공개됐지만 H201 corrected label은 여전히 없고, H201 primary Velox route는 기존 코드 hash `92b94bd631ec7eca9f6d0cb78fa11dcc905fdea186b443b12aa768e3c23b3cc2`로 실행 중인 상태에서 FlowSub의 병목을 감사했다. 기존 `_predicate_reliability`는 한 predicate 삭제 신뢰도를 계산할 때 `endpoint_scores` tuple을 endpoint마다 반복해서 dict로 변환했다. 변경 구현은 predicate마다 dict를 한 번 만들고 기존 endpoint 순서, clamp, `math.prod`, continuity와 반환식을 그대로 사용한다.

- 기존에 동결된 H501 Velox와 TGN route의 네 모드를 같은 Python 3.10, `PYTHONHASHSEED=0`에서 다시 계산했다.
- 두 경로 모두 512-node 순서, gain, objective, node value와 chain value가 부동소수 bit까지 같아 최대 절대 차이가 0이었다.
- 이미 추출된 H501 chain에서 선택 재계산은 Velox `14.49`초, TGN `7.90`초였다. 기존 route 전체 시간 `3743.83`초와 `525.58`초에는 DB profile·chain 재생성이 함께 포함되므로 이를 순수 selector 가속비로 나누지 않는다.
- H201 primary Velox 구 프로세스는 route 출력 없이 `01:52:00` 동안 중복 변환을 수행해 PID와 경과시간, 구·신 코드 hash, 기존 score hash, label 부재를 `results/h201-flow-aborted.json`에 먼저 기록한 뒤 종료했다. 이미 고정된 `score-201.json.gz` SHA-256 `18f7c13940d3be2d078be19f99907e1584f1466c4aee8e8ce99f92a5e5f255a9`는 다시 만들지 않고 검사 후 route 단계부터 재개했다.
- H201 primary와 TGN route 모두 새 실행 경로를 사용한다. 중단된 프로세스는 route 파일을 만들지 않았으며, proof chain, FlowSub 수식·선택, RAVEL utility, 후보, 예산, matching과 label evaluator는 바뀌지 않는다. 중단 기록과 재개 스크립트 SHA-256은 `9bfa8d8be12b9f5f7d2dcf638906acfedcadcb86aec33e1d3ff7bd8567049d83`, `9e6acc6a0291633be5fb1cc9ee95a109e869d034b8945d19c10a9b98f560c89f`이다.
- 코드, 회귀 테스트와 checker SHA-256은 각각 `65eb2a675a214693704f64a69c2aa7f24cb9ef4291183e000e8082d1f18af804`, `239e8741374cedc64c35b47f73a009c0cef3c8f2978ce07d182969e32985b494`, `2302057e0afd0d622bd85840e85a6a3f6bfdbec4a222d2c8de047a8bd46cf6be`이다. H501 Velox와 TGN equivalence 결과 SHA-256은 `a9594ca32a8be487c0254357c617fa0ae5eead5d4c66ae404894d866de43872c`, `a6748deb82a7a0a96f42090199e908e10a76f6eba58786f2a2d2215d26952eb2`다.

### RAVEL route-membership 실행 동치 최적화

2026-07-31 10:51 KST에 H201 corrected label이 여전히 없는 상태에서 RAVEL transport의 삭제 평가를 감사했다. 기존 구현은 후보 node가 들어 있지 않은 account route에서도 같은 base route를 다시 계산한 뒤 정확히 0인 차이를 더했다. 변경 구현은 root-route별 UUID membership을 한 번 만들고 후보가 실제로 들어 있는 route에서만 기존 `_route_value` 삭제 계산을 호출한다. Utility 식, 합산 순서와 해당 route의 IEEE-754 연산은 바꾸지 않는다.

- 합성 회귀 테스트는 호출된 모든 route가 삭제 후보를 실제로 포함하고 최종 transport edge가 변경 전과 정확히 같음을 검사한다.
- 수정 H501 Velox v5를 같은 Python 3.10과 `PYTHONHASHSEED=0`에서 재실행한 결과 `runtime_seconds`를 제외한 모든 JSON field가 기존 동결본과 정확히 같았다. 기존 runtime은 `177.413786`초, 변경 runtime은 `104.850183`초였다.
- 실행 동치 checker 결과 SHA-256은 `49d0305361eb14211c8e2736efa05e0c374aca0cd3c60c9281b24ca92e35666e`다. 채택한 `src/wisa_agent/tc/ravel.py` SHA-256은 `4f8a6da8ea5c978ca42f74673d01d72b94de2d7c5371a48fbeafb295e0ad0751`, checker는 `071f4ac7d705011147c4e5e33c4769c456245a61c25a91508aea118e3a199c71`다.
- H201 v5는 프로세스 시작 때 이전 `6513c6a2e96b82dfd14ababf51a850fa2428f0d361dea45c6f7f84a4ea8e4ea9` 코드를 이미 메모리에 올려 기존 수치 경로로 끝났고, 이후 v6부터 채택 코드를 사용한다. 두 경로는 H501에서 runtime 외 완전 동치가 확인됐다.

같은 label-free H201 route에서 최대 5,097개 endpoint를 가진 clause가 확인돼 clause 합을 한 번 계산하고 삭제 항을 빼는 더 빠른 대안도 시험했다. 이 식은 실수 대수에서는 같고 H501의 512-node 집합도 같았지만, 작은 삭제 질량의 부동소수 상쇄 때문에 root assignment 순서가 달라지고 objective가 `1.0531801208912839e-07` 변했다. Runtime은 `177.413786`초에서 `11.326528`초로 줄었지만 동결 수치 재현성을 깨므로 채택하지 않았다. 거절 기록은 `results/ravel-fast-rejected.json`에 보존한다.

같은 시점에 다중 UUID 삭제 fracture가 양의 proof realization을 원소로 하는 weighted-coverage 함수임을 도출했다. 따라서 정규화, 단조성과 submodularity가 성립하고 현재 utility는 그 singleton 값이다. 이는 benchmark 계수나 selector를 바꾸지 않는 명세 강화이며, 반복 UUID가 있는 합성 realization 전수 검사에서 diminishing returns를 확인했다.

### H201 label-free 동결

2026-07-31에 H201 primary와 TGN bundle을 label 없이 완료했다. Primary score universe는 1,437,512개, root budget은 512, admitted chain은 139개다. V5 objective는 `21.6167684091`, v6 objective는 `21.6285293192`이며 v6는 107개 proof node를 운반했다. Exact selection은 v5와 10개 slot이 다르고 runtime은 `1004.523`초다.

TGN bundle은 85개 rooted chain, 27개 proof transport, objective `7.5032686442`를 만들었다. H501에서 separately frozen output과 runtime 외 모든 field가 같은 shared-edge bundle만 사용했으며 방법, utility와 selection을 바꾸지 않았다. Bundle SHA-256은 `24fe9e706c536ef102c539ef493774f6d31e383edaee7b7dd81373a060b154e6`이다.

동결 전 ordered hash는 다음과 같다.

- primary score `18f7c13940d3be2d078be19f99907e1584f1466c4aee8e8ce99f92a5e5f255a9`
- primary route `4c997ca1b3151e07a57fde58197fb8c811853b32fed8c99b8969af19e79b00f`
- v5 `d415f313f917f7af959c31ea98401fa62b5d4c9922742c19c3606940d808c395`
- v6 `835a2bf5df51ad3a283ce2c926f910147c22c14580ada53a97f265186976a16c`
- ablation `454b8d69ac24ccaf9f01ef9889a9a2506aff7538c7e8210c85fdca3b92b254b7`
- TGN score `c465cb388196c84fdd78081bbb1ba657c4325d335dd3b75b70df53bbe18ba359`
- TGN route `2c5629699933327a73dbcc2da9d19ef7c8836b4ed08faaf1d0296057079eb82`

`frozen-201.json` SHA-256은 `b87874150b7a9a9929354911da9254e804379cd63b30f5930499da6a46f883bc`이고 12개 파일과 두 bundle의 연결을 검사한 `audit-201.json` SHA-256은 `b91eb26f5bf1f15bd13b004e61ebb8849a0cb4c9978279f212f922a7a35cbd5c`다. 감사가 통과할 때까지 H201 corrected event와 segment 파일은 존재하지 않았다.

### H201 라벨 공개와 최종 판정

감사 통과 뒤 공개 commit의 두 H201 blob만 복구했다. Working file의 Git blob OID는 공개 tree와 일치했고 SHA-256은 event `a984e0c93ff4c5895cb9f3deacdc6ec7669e1becaabe1fa797d5227a4e722c93`, segment `87e53d592c661080c355b4bd3c3e9ad603b863ab7c1db242177e2afc401bec93`이다.

- 36,045 labeled event에서 score universe에 포함된 malicious actorID는 352개다.
- Velox는 2개, v6는 1개를 회수한다. 107개 변경 slot에서 baseline-only 악성 1개를 잃고 candidate-only 악성을 추가하지 못했다.
- Precision은 `0.00390625→0.001953125`, covered recall은 `0.00568182→0.00284091`, MCC는 `0.00441712→0.00206086`이다.
- Topology, rank, v5, v6는 모두 1개다. Exact matching은 v5보다 objective를 높이고 10개 slot을 바꾸지만 true positive는 바꾸지 않는다.
- Label 공개 전 등록한 FlowSub는 4개를 회수하고 216개 interval 중 감소가 없다.
- TGN은 `2→1`이고 하나의 interval이 감소한다. H201 TGN은 input-matched ablation이 아니라 confounded pipeline-sensitivity 결과다.

H501은 `7→10`이지만 65개 interval 중 3개가 감소하고, H201은 `2→1`이며 216개 중 1개가 감소한다. 두 host 모두 aggregate 개선과 interval no-decline을 요구한 외부 우월성 가설은 기각한다. 같은 campaign의 기술적 합계 `9→11`은 이 판정을 바꾸지 않는다. Label을 본 뒤 hold, proof utility, adapter, budget, comparator 또는 host를 교체하지 않는다.

### 인증형 transport 개발과 H051 사전 등록

2026-07-31 12:55 KST에 H501·H201의 실패 분석을 방법 개발 자료로 전환하고, 아직 내용을 열지 않은 PIDSMaker ORTHRUS H051 node label을 최종 held-out 평가로 등록했다. H501과 H201은 인증 규칙의 소급 성질을 확인하는 개발 결과일 뿐 새 방법의 외부 검정으로 다시 사용하지 않는다. 기존 H051 strict-threshold 실행에서 threshold `18.0919647`이 test maximum `13.8157101`보다 높아 root가 0개였던 결과도 삭제하거나 새 fixed-capacity 결과로 대체하지 않는다. 이번 연구는 같은 동결 Velox score universe에 별도의 512-slot 조사 용량을 적용하는 새 평가다.

첫 인증형 transport v1은 v6 exact assignment를 먼저 그대로 계산했다. Root \(r\)의 모든 허용 route \(q\)에 대해 비root proof clause 중 하나가 정확히 singleton \(\{v\}\)이면 UUID \(v\) 삭제가 각 route의 곱을 0으로 만들므로 상대 fracture는 정확히 1이다. 이 조건을 만족하는 선택만 비root transport로 유지하고, 나머지는 해당 root의 private hold로 되돌렸다. 조정 가능한 threshold나 label 입력은 없으며, 각 유지 선택은 route ID와 singleton clause index를 기계 판독 가능한 witness로 출력한다.

H501에서는 v1이 v6의 59개 transport 중 7개를 인증해 Velox 악성 UUID 회수가 `7→8`이고 65개 interval 감소가 0개였다. H201에서는 107개 중 11개를 인증해 `2→2`이고 216개 interval 감소가 0개였다. 이 두 결과를 본 뒤 singleton 조건의 계수나 의미를 바꾸지 않았으며, witness 직렬화만 추가한 뒤 같은 선택과 count를 재현했다. 이 관찰은 동기와 개발 진단으로만 보고한다.

2026-07-31 13:14 KST에 H051 label을 열지 않은 상태에서 v1의 계산적 불완전성을 확인했다. V6는 전체 fractional fracture 합을 최대화하므로, 한 root의 완전-fracture 간선이 다른 root의 큰 partial 간선과 충돌할 때 완전 간선을 선택하지 않을 수 있다. 선택된 v6 간선만 거르는 v1은 후보 그래프에 남은 유효한 인증 간선을 복구하지 못한다. V2는 모든 v6 proof 후보에서 singleton witness를 검사하고, 인증 간선의 utility를 1, private hold를 0으로 둔 exact matching을 다시 풀어 인증 transport 수를 최대화한다. 이 변경은 H501·H201을 개발 자료로 사용하는 label-aware 방법 개발이지만 H051 label에는 접근하지 않았고, H051 판정식·예산·비교군은 바꾸지 않았다. V1 산출물과 평가는 `cert1-*`, `eval-cert1-*`로 보존한다.

V2의 H501 개발 평가는 aggregate 회수가 `7→7`이었지만 segment no-decline을 통과하지 못했다. 인증 개수만 같은 matching 사이에서 UUID 사전순이 선택을 결정해 더 큰 detector evidence를 버릴 수 있다는 목적함수의 공백으로 판정했다. 2026-07-31 13:34 KST에 H051 label을 열지 않은 상태에서 V3를 등록했다. V3는 인증 transport 수를 1차로 최대화하고, 그 최대 개수 해들 중 선택 node의 validation conformal e-value 합을 2차로 최대화한다. 정규화 e-value가 간선당 \([0,1]\)이므로 1차 항에 \(B+1\)을 부여하면 한 개의 인증 차이가 최대 \(B\)인 전체 2차 차이보다 항상 크다. 따라서 계수 탐색 없이 사전식 목적과 정확히 동치다. V2 H501 산출물은 `cert2-501`, `eval-cert2-501`로 보존한다.

V3도 H501에서 `7→7`과 segment decline을 그대로 보였다. Evidence만으로 동률 인증 해를 고르면 인증기가 원래 v6 assignment를 불필요하게 교환할 수 있다는 두 번째 정의 공백으로 판정했다. V4는 인증기를 v6 해의 certified feasible projection으로 정의하고 ① 인증 수 최대화, ② v6 assignment 일치 수 최대화, ③ conformal e-value 합 최대화의 사전식 목적을 사용한다. 정규화 evidence의 전체 차이는 최대 \(B\), agreement와 evidence를 합친 전체 차이는 최대 \((B+1)^2-1\)이므로 간선 순위 \((B+1)^2 I_{\mathrm{cert}}+(B+1)I_{\mathrm{source}}+\bar e_v\)가 세 목적과 정확히 동치다. V3 H501 산출물은 `cert3-501`, `eval-cert3-501`로 보존하며, V4를 H201 개발 확인 뒤 H051에 적용하는 최종 규칙으로 동결한다.

V4 H501은 92,670개 proof 후보 중 34개가 구조 인증됐고 충돌 제약 아래 최대 7개를 배정했다. V6 선택에도 인증 간선이 7개 있었으므로 projection 일관성에 따라 V1과 같은 node set을 재현했고, Velox 회수 `7→8`, 65개 segment decline 0개였다. V2와 V3의 `7→7`, decline 1개 산출물도 삭제하지 않는다.

V4 H201은 298,021개 proof 후보 중 19개가 구조 인증됐고 최대 11개를 배정했다. V6 선택의 인증 간선 수도 11개여서 다시 V1과 같은 node set을 재현했다. Velox 회수는 `2→2`, 216개 segment decline은 0개다. H501·H201은 모두 V4 방법 개발 데이터이며 두 결과를 외부 검정으로 다시 승격하지 않는다. 이후 H051 label 장벽 전에는 방법, 목적 순서, 예산, 비교군과 endpoint를 변경하지 않는다.

H051 사전 등록은 `results/cert-plan.json`에 기계 판독 가능하게 보존한다.

- 데이터는 PIDSMaker commit `54f687c54aa03e5519cf44953d5ee44f5f6a4a28`, `optc_051.dump` SHA-256 `8b3dc188bc932153e3feca8b2c6254ce692e5478bc5e64d1b8d0f0c6b421f21b`, SQLite projection SHA-256 `aa762123532f5bf29c24cbb390d55344a9bbc276cb030542abeee2a09f4f59ec`를 사용한다.
- 기존 label-free H051 manifest SHA-256은 `6f23c493d7e188f1e7ba62bc2efc9d4a2782747484ed8c5d49b51da80c39caea`이고 official score composite는 `12e4a7f7a68e0ef7a32192f17ab4bc507fdc3b7d478f469f7506df7ab867468c`다.
- Root는 official edge-loss node maximum을 `score 내림차순, UUID 오름차순`으로 정렬한 top 512로 고정한다.
- 비교군은 같은 score universe와 512 예산의 Velox roots, FlowSub full, v6 exact selection이다.
- 1차 안전성 조건은 인증 transport가 하나 이상 실제로 작동하고 H051 단일 공격의 악성 UUID 회수가 Velox보다 감소하지 않는 것이다.
- 2차 효능 조건은 Velox보다 엄격히 많이 회수하는 것이다. FlowSub 이상이면 competitive noninferiority, Velox·FlowSub·v6 모두보다 엄격히 많으면 strict all-comparator success로 별도 판정한다.
- H051은 공개 설정상 label 파일과 공격 시간창이 각각 하나이므로 관측되지 않은 하위 interval을 만들지 않는다. Aggregate 단일 공격만 판정한다.
- Score, route, v6, certified-v4 output, 계획 파일을 ordered manifest로 동결하고 코드 hash, 입력 연결, exact budget, FlowSub·v6·certified 선택, exact source·certified matching certificate, 사전식 목적과 모든 후보 cut witness의 재계산을 독립 감사한 뒤에만 label CSV를 읽는다.
- Label을 읽은 뒤에는 인증 규칙, root policy, 예산, comparator, evaluator와 판정 조건을 바꾸지 않고 네 조건을 모두 보고한다. 실패한 조건은 H051에 맞춰 수정하지 않고 기각한다.

최종 V4 label-free H051 실행은 1,470,624개 score node, 140개 chain 중 112개 seeded chain, 113,495개 proof transport 후보를 만들었다. V6는 59개를 운반했고, universal-cut 검사는 4개 후보를 인증해 exact projection도 4개를 배정했다. Source 인증 수도 4개여서 projection 일관성이 다시 성립했다. Score, route, v6, V4와 계획 파일의 ordered freeze SHA-256은 `af72b40f0552ad0b368161ffd1b10c379d7c2cee838debfa919dbf72f9d829b1`이다. 이 문단까지 H051 label CSV의 내용이나 hash를 읽지 않았다.

독립 감사 SHA-256 `474b793467a7adabf2d486ddb880e79799975331c80bd904440193838595b942`가 source exact matching, V4 사전식 matching, code·input lineage와 5개 route witness를 모두 재현한 뒤 2026-07-31 14:11 KST에 처음 label evaluator를 실행했다. H051 회수는 Velox `4`, FlowSub `8`, v6 `2`, V4 `3`이다. V4는 활성화됐지만 primary safety, secondary efficacy, competitive noninferiority, strict all-comparator 조건이 모두 거짓이다. Velox와 다른 4개 slot에서 악성 root 1개를 잃고 악성 target은 추가하지 못했다. Label과 평가 SHA-256은 `ff8af2562c6746b48f81445fa36a5860ebd9a4402fa6b83cd47ddda35bfdeb3b`, `cee25b17dc9310feaf81d7a35da7732e96e189aa1175284b508570742de98ca8`이다. 이 결과 뒤 H051 방법·예산·비교군·endpoint는 수정하지 않는다.
