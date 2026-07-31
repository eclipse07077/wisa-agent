# 실험 결과

이 문서는 CAGE 방어 실험과 DARPA TC의 CADETS·THEIA·TRACE·ClearScope 공격 체인 실험을 함께 기록한다.

## CAGE Challenge 4

모든 조건은 공식 `FiniteStateRedAgent`, 500 step, 같은 20개 seed를 사용했다. reward는 0에 가까울수록 좋다.

| 에이전트 | reward 평균 | 표준편차 | privileged host | impacted host |
|---|---:|---:|---:|---:|
| Sleep | -6836.45 | 1494.42 | 54.50 | 19.20 |
| Reactive | -6286.10 | 1161.42 | 51.65 | 18.30 |
| LayerChain | -2878.60 | 610.11 | 34.75 | 7.85 |
| 보고서 기반 전체 | -3583.00 | 1069.70 | 36.60 | 10.00 |
| 체인 제거 | -3660.45 | 992.31 | 36.45 | 10.10 |
| 허니팟 제거 | -3943.65 | 754.24 | 38.65 | 10.85 |
| 강한 대응 guard 제거 | -3583.00 | 1069.70 | 36.60 | 10.00 |

보고서 기반 전체 방법은 LayerChain보다 reward가 704.4 낮았다. paired bootstrap 95% 구간은 `[-1290.86, -130.89]`이며, impacted host도 2.15개 많았다. 이 결과는 방어 성능 우위를 지지하지 않는다.

전체 방법과 체인 제거의 reward 차이는 `+77.45`, 95% 구간은 `[-90.61, 244.45]`다. 허니팟 제거 대비 차이는 `+360.65`, 구간은 `[-67.65, 759.20]`다. 두 구성요소 모두 방향은 양수지만 개발 seed에서 불확실하다. guard 제거는 모든 지표가 완전히 같아 현재 환경에서 작동하지 않았다.

온라인 적대 호스트 전이로 허니팟 대상을 고른 v7은 reward `-3855.60`으로 v6보다 272.6 낮았다. paired 95% 구간은 `[-607.86, 61.65]`이고 Impact도 평균 0.55 증가해 기본 방법에서 제외했다.

정상-이탈 위험식을 이진 process·connection flag에 적용한 v8은 reward `-3750.65`로 v6보다 167.65 낮았다. paired 95% 구간은 `[-367.80, 27.90]`이고 Impact 개선도 없어 연결을 롤백했다. 공통 코어의 정상-이탈 식은 유지하되 CAGE의 두 flag는 사전 정의 경보로 처리한다.

### 미사용 seed 검증

동결된 v6을 seed 4400–4419에서 다시 실행했다. LayerChain의 reward는 `-3698.75 ± 934.93`, 보고서 기반 전체 방법은 `-3799.50 ± 1272.83`이었다. paired reward 차이는 `-100.75`, 95% 구간은 `[-672.50, 500.27]`, win rate는 `0.45`였다.

보고서 기반 방법은 privileged host가 평균 1.90개, impacted host가 0.55개, 성공한 Impact가 0.50회 많았다. 각 95% 구간은 모두 0을 포함한다. 개발 seed에서 관측한 유의한 열세는 재현되지 않았지만, reward나 공격 억제에서 우위를 보였다는 증거도 없다.

### 최종 100-episode 평가

동결된 v6과 LayerChain을 사전 기록한 seed 5400–5499에서 한 번 실행했다.

| 에이전트 | reward 평균 | 표준편차 | privileged host | impacted host | 성공 Impact |
|---|---:|---:|---:|---:|---:|
| LayerChain | -3027.08 | 926.60 | 34.69 | 8.72 | 8.76 |
| 보고서 기반 v6 | -3591.80 | 1049.53 | 36.84 | 9.71 | 9.79 |

보고서 기반 v6 minus LayerChain paired reward는 `-564.72`, 95% 구간은 `[-812.21, -319.86]`, paired effect size는 `-0.446`, win rate는 `0.37`이었다. privileged host는 `+2.15 [1.03, 3.26]`, impacted host는 `+0.99 [0.26, 1.69]`, 성공 Impact는 `+1.03 [0.28, 1.75]`였다.

v6은 Analyse 10,448회와 DeployDecoy 5,554회를 실행한 반면 LayerChain은 각각 19,686회와 7,093회를 실행했다. 반대로 v6은 Remove를 4,975회 실행했지만 LayerChain은 5회뿐이었다. 이 행동 분포는 보고서 위험 구간이 CAGE에서 조기 Remove를 과도하게 선택하고 관측·기만 기회를 줄이는 실패 가설과 일치하지만, 별도의 인과 ablation은 하지 않았다. 이 최종 seed를 본 뒤 새 버전을 만들거나 같은 seed에서 재선택하지 않는다.

### 사전등록 후속 개발

기존 개발·검증·최종 시드를 봉인하고 새 개발 seed 6400–6419에서 행동 오케스트레이션만 두 번 평가했다. 위험도, 체인, predicate, criticality, 허니팟, Red 정책과 episode 길이는 고정했다.

| 버전 | reward 평균 | 표준편차 | privileged host | impacted host | 성공 Impact |
|---|---:|---:|---:|---:|---:|
| LayerChain | -3217.10 | 1048.50 | 35.50 | 8.10 | 8.10 |
| 보고서 기반 v6 | -3638.20 | 944.75 | 37.35 | 11.10 | 11.10 |
| fresh-analysis v9 | -6376.85 | 1242.34 | 53.65 | 18.45 | 18.45 |
| event-aware v10 | -3674.55 | 1184.77 | 37.05 | 9.45 | 9.45 |

v9은 강한 대응 전에 다음 step의 분석 근거 지속을 요구했다. 공식 CAGE 소스 감사에서 process·connection 비트가 지속 감염 상태가 아니라 매 step 회전되는 최근 이벤트 버퍼임을 확인했다. v9은 v6 대비 reward가 `-2738.65 [-3254.83, -2251.11]` 낮고 모든 공격 영향 지표가 악화돼 표현 불일치로 기각했다.

사전등록상 허용된 마지막 수정 v10은 독립 계층 두 개를 강한 대응의 조건으로 사용하고, 18-step 재발 감시와 중복 대응 억제를 적용했다. v10 minus v6는 reward `-36.35 [-367.55, 260.65]`, privileged host `-0.30 [-2.80, 2.25]`, impacted host와 성공 Impact `-1.65 [-3.25, -0.05]`였다. 영향 억제는 좋아졌지만 reward 점추정 개선이라는 선택 조건을 충족하지 못했다. LayerChain 대비 reward도 `-457.45 [-909.91, -35.22]`로 유의하게 낮았다.

v10은 선택하지 않았다. 예약한 검증 seed 7400–7419와 최종 seed 8400–8499는 열지 않았고 추가 방어 정책 수정도 하지 않는다.

### 범위 제약 오케스트레이션 v12

v11은 시간 belief와 정적 행동 효용을 새 개발 seed 9400–9419에서 평가했지만 LayerChain보다 reward가 공식 Red에서 `-751.90`, 체인형 Red에서 `-971.05` 낮아 기각했다. 원인은 부분 Remove의 조치 범위가 교차 계층 증거 범위를 덮지 못한 것이었다.

v12는 점수 조정 대신 세 구조를 결합했다. 강한 조치의 범위가 증거 범위를 포함하도록 하고, process와 connection이 함께 확인되면 부분 Remove보다 Restore를 사용하며, 효과 확인 중 같은 대상의 강한 조치를 억제한다. 위협이 없을 때에는 구역별 기만 coverage를 한 번에 하나씩 확장한다. 개발 12400–12419와 검증 13400–13419에서 두 Red 정책 모두 reward 평균과 공격 영향 지표가 악화되지 않아 코드를 변경하지 않고 최종 seed 14400–14499를 열었다.

| Red 정책 | 에이전트 | reward 평균 | 표준편차 | privileged host | impacted host | 성공 Impact |
|---|---|---:|---:|---:|---:|---:|
| 공식 | LayerChain | -3110.39 | 815.63 | 35.12 | 8.30 | 8.31 |
| 공식 | v12 | -2641.74 | 746.69 | 32.28 | 7.41 | 7.46 |
| 체인형 | LayerChain | -3703.61 | 983.85 | 35.50 | 6.58 | 6.64 |
| 체인형 | v12 | -3108.22 | 814.13 | 33.35 | 5.53 | 5.56 |

공식 Red에서 v12 minus LayerChain reward는 `+468.65 [276.24, 656.89]`, effect size `0.483`, win rate `0.67`이었다. privileged host, impacted host, 성공 Impact는 각각 `-2.84 [-4.13, -1.61]`, `-0.89 [-1.55, -0.26]`, `-0.85 [-1.51, -0.21]`였다.

체인형 Red에서 reward는 `+595.39 [410.39, 784.28]`, effect size `0.624`, win rate `0.72`였다. 세 공격 영향 차이는 `-2.15 [-3.24, -1.04]`, `-1.05 [-1.66, -0.45]`, `-1.08 [-1.70, -0.47]`였다. 두 조건의 네 지표 모두 95% 구간 전체가 개선 방향이므로 사전 기준에 따라 v12를 최종 방어 방법으로 선택한다. 이 최종 결과를 본 뒤 정책이나 상수를 변경하지 않는다.

## DARPA TC CADETS E3

정상 학습은 3, 4, 5, 7, 8, 9, 10일, validation threshold는 2일, 개발 평가는 6, 11, 12, 13일을 사용했다. 정답 라벨은 metric 계산에서만 읽었다.

| 버전 | predicate 구성 | AUROC | AP | 체인 노드 precision | 체인 노드 recall |
|---|---|---:|---:|---:|---:|
| event v1 | 이상 이벤트 직접 변환 | 0.78705 | 0.12600 | 0 | 0 |
| semantic v2 | 이상 이벤트 세션 집계 | 0.78697 | 0.02651 | 0 | 0 |
| trace v3 | 이상 seed 주변 전이 복원, raw 결합 | 0.82644 | 0.02248 | 0.03208 | 0.25000 |
| grounded trace v4 | predicate confidence로 노드 기여 제한 | 0.79144 | 0.12600 | 0.03208 | 0.25000 |

grounded trace는 530개 조사 노드에서 악성 노드 17개를 찾았다. 같은 수의 anomaly-only 상위 노드는 10개를 찾아 precision `0.01887`, recall `0.14706`이었다. 체인 attribution은 더 좋았지만 node-ranking AP는 `0.126001`에서 `0.125996`으로 사실상 변하지 않았다.

공격이 없는 11일에도 108개 체인 노드를 출력했다. 따라서 이 결과는 고정-budget 조사 우선순위의 개선이지, 낮은 오탐률의 공격 경보 성능을 의미하지 않는다.

### CADETS 경보 압축 후속 실험

외부 performer에 다시 접근하기 전에 넓은 세션 footprint를 줄이는 세 변형을 순차 사전등록했다. 각 버전은 CADETS에서 한 번만 실행하고, 같은 보고 예산의 anomaly-only보다 악성 node를 더 많이 찾지 못하면 THEIA에서 실행하지 않았다.

| 방법 | AP | 보고 node | 악성 node | matched anomaly 악성 node | 판정 |
|---|---:|---:|---:|---:|---|
| grounded trace v4 | 0.125996 | 530 | 17 | 10 | 기준 방법 |
| connector v5 | 0.104029 | 1,870 | 11 | 12 | 기각 |
| cut set v6 | 0.104029 | 1,708 | 10 | 12 | 기각 |
| minimal core v7 | 0.129095 | 183 | 5 | 10 | 기각 |

v5와 v6은 보고량과 악성 회수를 모두 악화시켰다. v7은 보고량을 v4의 34.5%까지 줄이고 AP를 높였지만 같은 183개 예산의 anomaly-only보다 악성 node를 다섯 개 적게 찾았다. 따라서 최소 인과 핵심은 경보 압축에는 유효하지만 체인 기반 공격 node 발견 성능을 높이지 못했다. 세 결과와 첫 v5 실행의 metric 환경 실패 로그를 모두 보존했고, 통과 조건을 충족한 변형이 없어 THEIA 재평가와 추가 공격 방법 수정은 하지 않았다.

## DARPA TC THEIA E3 외부 검증

CADETS에서 동결한 grounded trace v4를 코드와 파라미터 변경 없이 적용했다. 공식 JSON 4개에서 원본 113,293,343개 레코드, 추적 이벤트 39,922,077개, 고유 노드 1,487,424개를 인덱싱했다. 공개 분할의 2일에는 추적 이벤트가 없어 실질 정상 학습 데이터는 3·4·5일이며, threshold `0.1670956`은 9일에서만 계산했다.

| 방법 | AUROC | AP | 조사 노드 precision | 조사 노드 recall |
|---|---:|---:|---:|---:|
| anomaly-only | 0.83723 | 0.028519 | 0.00657 | 0.06780 |
| grounded trace v4 | 0.84664 | 0.028947 | 0.01396 | 0.14407 |

동결 방법은 1,218개 체인 조사 노드에서 악성 노드 17개를 찾았고, 같은 수의 anomaly-only 상위 노드는 8개를 찾았다. AUROC는 `+0.00941`, AP는 `+0.000428` 상승했다. 그러나 top-100, top-500, top-1000의 precision·recall은 변하지 않았으므로 상위 고정 예산 ranking 개선으로 해석할 수 없다.

공격별로 day 10은 체인 835개에서 악성 12개 대 anomaly-only 9개, day 12는 201개에서 5개 대 4개였다. 공격이 없는 day 13에도 체인 노드 196개를 출력했다. 외부 데이터에서도 attribution 방향은 재현됐지만 공격-instance 경보 calibration은 실패했다. 실행 시간은 323.83초, peak RAM은 809.34 MiB였다.

fine-label 공격 사례가 두 개뿐이므로 공격 사례 단위 신뢰구간이나 통계적 우월성은 주장하지 않는다.

상위 48개 체인은 모두 `trust_break → lifecycle → mission_effect` 구조였지만, 이 중 세 개는 고빈도 세션 집계로 각각 416, 441, 485개 endpoint를 포함했다. attribution 향상의 일부가 넓은 세션 footprint에서 생길 수 있으므로 간결한 공격 경로 복원 성과로 해석하지 않는다.

## DARPA TC ClearScope E5 외부 평가

CADETS에서 동결하고 THEIA에서 수정하지 않은 grounded trace v4를 CDM20 ClearScope E5에 적용했다. PIDSMaker 공개 dump를 서버에 복원하지 않고 읽기 전용 SQLite로 변환했다. 정상 학습은 8·9일, validation은 11일, 평가는 14·15·17일이며 fine UUID 라벨은 세 평가일 출력이 모두 끝난 뒤 읽었다.

- 원본 인덱스: 노드 501,006개, event 198,794,211개, 누락 endpoint 0개
- 선택 분할: train 61,248,915개, validation 512,119개, test 48,553,585개 event
- validation anomaly threshold: `0.1518871`
- 평가 노드: 150,964개, covered positive 51개, label coverage 1.0
- 실행 시간: 887.69초, peak RAM 227.09MiB

| 방법 | AUROC | AP | 조사 노드 | 악성 노드 | precision | recall |
|---|---:|---:|---:|---:|---:|---:|
| anomaly-only | 0.52672 | 0.023037 | 522 | 11 | 0.02107 | 0.21569 |
| grounded trace v4 | 0.54243 | 0.023052 | 522 | 4 | 0.00766 | 0.07843 |

AUROC는 `+0.01572`, AP는 `+0.000014` 올랐지만 top-100·500·1000 precision과 recall은 완전히 같았다. 핵심 matched-budget attribution은 11개에서 4개로 악화됐다. day 15는 chain 280개에서 악성 3개 대 anomaly-only 6개, day 17은 237개에서 1개 대 5개였다. 공격 없는 day 14에도 5개 chain node를 출력했다.

유효 체인은 97개, predicate는 6,144개였다. 상위 48개 중 44개가 `EVENT_CONNECT → EVENT_OPEN → EVENT_SENDMSG`였고 가장 넓은 체인은 endpoint 56개를 포함했다. 체인 형성 자체는 CDM20에서도 작동했지만 악성 attribution을 개선하지 못했다.

이 결과는 frozen parser와 오케스트레이터의 실행 가능성만 확인한다. 공개 dump에 원본 `predicateObjectPath`가 없어 path는 모두 `unknown`이며, 이를 E5 앱 이름이나 node path로 사후 복원하지 않았다. H25를 기각하고 E5/CDM20 attribution 일반화와 낮은 오탐 경보 주장을 하지 않는다.

### E5 원인 분리: CADETS no-path 진단

E5 결과를 다시 사용하지 않고, 사전에 정한 대로 CADETS의 train·validation·development event에서 path만 제거해 grounded trace v4를 한 번 재실행했다.

| CADETS 개발 | 원본 path | path 제거 |
|---|---:|---:|
| validation threshold | 0.179505 | 0.135382 |
| path profile state | 8,274 | 9 |
| grounded trace AUROC | 0.791443 | 0.733838 |
| grounded trace AP | 0.125996 | 0.085902 |
| 체인 조사 노드 | 530 | 1,220 |
| 체인 악성 노드 | 17 | 3 |
| matched anomaly 악성 노드 | 10 | 12 |
| 체인 attribution recall | 0.25000 | 0.04412 |

체인 수는 192개, predicate 수는 8,192개로 같았지만 path가 사라지자 조사 footprint가 넓어지고 attribution 우위가 역전됐다. H30을 지지하며 event path를 주요 표현 한계로 판정한다. 다만 서로 다른 performer와 CDM 버전이 함께 바뀐 E5의 유일한 실패 원인을 이 CADETS 반사실 실험만으로 확정할 수는 없다. H29 backbone 수정은 실행 조건이 충족되지 않아 수행하지 않았고 E5도 재평가하지 않았다.

### Validation-only 체인 경보 진단

기존 외부 출력을 본 뒤 등록한 탐색 실험이다. 각 performer의 validation 체인 점수 0.995 `higher` quantile 이상만 경보로 남겼다. method나 test 결과로 quantile을 다시 선택하지 않았다.

| 데이터 | validation threshold | 전체 경보 노드 | 악성 경보 노드 | matched anomaly 악성 노드 | 공격 없는 날 경보 |
|---|---:|---:|---:|---:|---:|
| CADETS E3 | 0.716994 | 102 | 5 | 9 | day 11: 27 |
| THEIA E3 | 0.742980 | 27 | 5 | 8 | day 13: 8 |

CADETS는 unfiltered chain node 530개에서 102개로 줄었지만 악성 회수도 17개에서 5개로 감소했다. THEIA는 1,218개에서 27개로 줄었으나 day 10 공격을 완전히 놓쳤고 aggregate recall은 `0.04237`로 matched anomaly-only의 `0.06780`보다 낮았다. 단일 validation quantile은 조사량을 줄이지만 낮은 오탐 경보와 공격 recall을 함께 만족하지 못했다. H24를 기각하며 performer별 재조정은 하지 않는다.

## 공식 Velox seed 결합

PIDSMaker `velox` commit `54f687c`의 tuned 설정과 공개 pretrained weights를 변경 없이 재현했다. detector의 `nodes`와 `pred_scores`만 label-free manifest 생성 프로세스에 전달했고, `y_truth`와 attack metadata는 별도 평가 전까지 사용하지 않았다. 임계값은 validation edge loss의 정확한 최댓값에 대한 엄격한 `>`인 `9.57309627532959`다.

공식 Velox는 CADETS E3에서 ADP 1.0으로 세 공격을 모두 탐지했고, 281,585개 후보 중 1,103개를 보고해 악성 노드 23개를 회수했다. 동결된 trace head의 192개 체인 중 공식 seed와 겹친 5개만 허용하자 28개 endpoint가 선택됐고, 기존 seed와 중복을 제거한 신규 조사 노드는 19개였다.

| CADETS E3 | 조사 노드 | 악성 노드 | precision | recall | MCC |
|---|---:|---:|---:|---:|---:|
| 공식 Velox threshold | 1,103 | 23 | 0.02085 | 0.33824 | 0.08318 |
| 동일 1,122-node Velox top-k | 1,122 | 23 | 0.02050 | 0.33824 | 0.08246 |
| Velox seed + 동결 체인 | 1,122 | 30 | 0.02674 | 0.44118 | 0.10786 |

같은 예산의 cutoff에는 세 노드가 동점이었고 모두 정상이어서 tie-break와 무관하게 Velox TP는 23개다. 공격 파일별 회수는 matched Velox의 `2, 17, 5`에서 `3, 22, 8`로 모두 증가했다. 세 파일이 일부 UUID를 공유해 aggregate 증가는 9가 아니라 7이다. 공식 detector ranking 자체는 AUROC `0.77170`, AP `0.30938`이며 이 실험은 ranking을 변경하지 않았으므로 AP 개선으로 주장하지 않는다.

ClearScope E3의 공식 confusion matrix는 TP 1, FP 13,813으로 총 13,814개 경보였고 AP `0.000735`, AUROC `0.39735`, MCC `-0.00580`이었다. 로그에 소수 셋째 자리까지만 남은 threshold를 재구성한 adapter는 13,816개 seed를 만들었지만 28개 동결 체인과의 교집합은 0개였다. 두 경보 차이가 있으므로 이를 정확한 matched-budget 결과로 사용하지 않는다. 공식 저장소가 이 performer의 null netflow와 중복 event를 경고하므로 이 실패를 detector 일반 결론으로 확대하지 않는다.

CADETS의 세 공격 사례에서 matched-budget 차이는 모두 양수지만, 단측 sign test는 `p=0.125`다. 따라서 이 결과만으로 통계적 우월성을 주장하지 않았다.

같은 코드를 바꾸지 않고 공식 THEIA E3 pretrained 모델에 적용했다. train은 2–8일, validation은 9일, test는 10·12·13일이고 정확한 validation 최대 loss `7.088447093963623`에 엄격한 `>`를 사용했다. 공식 Velox ranking은 AUROC `0.77375`, AP `0.10601`이었다.

| THEIA E3 | 조사 노드 | 악성 노드 | precision | recall | MCC |
|---|---:|---:|---:|---:|---:|
| 공식 Velox threshold | 503 | 16 | 0.03181 | 0.13559 | 0.06536 |
| 동일 1,155-node Velox top-k | 1,155 | 16 | 0.01385 | 0.13559 | 0.04285 |
| Velox seed + 동결 체인 | 1,155 | 27 | 0.02338 | 0.22881 | 0.07268 |

동점 처리는 라벨을 보지 않고 UUID 내림차순으로 고정했다. cutoff에서 191개가 동점이고 그중 악성은 1개였으므로 가능한 어떤 tie-break에서도 matched Velox TP는 16–17개다. 동결 체인의 27개는 최선의 tie-break보다도 10개 많다.

144개 동결 체인 중 seed와 겹친 것은 6개였다. 두 공격 파일에서 회수 수가 각각 `12→15`, `4→12`로 모두 증가해 aggregate TP가 11개 늘었다. CADETS와 THEIA의 다섯 공격 파일 차이는 `+1, +5, +3, +3, +8`이며, 파일을 독립 단위로 볼 때 정확 단측 sign test는 `p=0.03125`다. 표본이 작고 파일 간 의존 가능성이 있어 이를 넓은 통계적 보장으로 확대하지 않는다.

두 performer를 설명 목적으로 합치면 동일한 총 2,277개 보고 예산에서 matched Velox는 186개 악성 노드 중 39개, 동결 체인 결합은 57개를 회수했다. precision은 `0.01713→0.02503`, recall은 `0.20968→0.30645`, MCC는 `0.05934→0.08703`이다. 이 결론은 detector ranking이나 자동 침투 성공률이 아니라 node attribution 성능에 한정한다.

## FlowSub 고정 예산 선택

기존 결합은 체인 endpoint를 seed에 추가하므로 CADETS 19개, THEIA 652개만큼 조사량이 늘었다. FlowSub는 공식 seed 수를 고정 예산으로 두고, anomaly percentile·node 삭제 책임도·보존 causal flow로 구성한 부분모듈 목적함수를 greedy로 최적화한다. 전체 수식과 증명은 `docs/flow.md`에 기록했다.

CADETS label을 열기 전에 네 ablation과 tie-break를 고정했고 label-free manifest SHA-256 `d24e97dd40b08f1f87055262368e7a80fc64eb125defa3857f3b0c3fa9aa57e4`를 먼저 생성했다. THEIA에는 수식과 파라미터를 바꾸지 않았으며 manifest SHA-256은 `e15062739c3fc46836b9f19433bed055a4d350c4b5562521332f26842bb3ece0`다.

| 데이터·예산 | 공식 seed TP | anomaly TP | flow TP | responsibility TP | full TP |
|---|---:|---:|---:|---:|---:|
| CADETS, 1,103 | 23 | 23 | 23 | 29 | 29 |
| THEIA, 503 | 16 | 16 | 17 | 25 | 25 |

| 데이터 | 비교 | precision | recall | MCC |
|---|---|---:|---:|---:|
| CADETS | 공식 seed | 0.02085 | 0.33824 | 0.08318 |
| CADETS | FlowSub | 0.02629 | 0.42647 | 0.10514 |
| THEIA | 공식 seed | 0.03181 | 0.13559 | 0.06536 |
| THEIA | FlowSub | 0.04970 | 0.21186 | 0.10231 |

CADETS 공격 파일별 회수는 `2→3`, `17→22`, `5→7`, THEIA는 `12→15`, `4→10`으로 다섯 파일 모두 증가했다. 두 node universe를 설명 목적으로 합치면 같은 총 1,606개 보고에서 악성 node는 39/186에서 54/186으로 증가했다. 파일 독립성을 가정한 단측 sign test는 `p=0.03125`지만 표본이 작고 label 파일 간 의존 가능성이 있다.

Full과 responsibility-only는 두 데이터에서 정확히 같은 결과였다. Flow-only는 CADETS에서 anomaly-only와 같고 THEIA에서 한 node만 더 회수했다. 따라서 성능 기여는 exact counterfactual responsibility와 submodular budget exchange에 귀속한다. Conserved flow는 효율성·비음수성·비례 배분의 유일성은 만족하지만 측정된 성능 기여는 없거나 약한 음성 ablation이다. 결과를 본 뒤 flow를 제거하거나 가중치를 재조정하지 않았다.

THEIA는 이전 방법 개발에서 label을 이미 관측했으므로 이 결과는 수정 없는 회고적 performer 전이 검사다. FlowSub가 detector AP를 개선하거나 자동 공격을 실행하거나 CDM20/E5에 일반화한다고 주장하지 않는다.

## 단일-ledger novelty 실험

FlowSub의 별도 responsibility·flow·coverage 결합을 제거하기 위해 BEAR와 RAVEL을 순서대로 개발했다. 모든 selector manifest는 metric 프로세스보다 먼저 생성하고 해시를 고정했다.

| 방법 | CADETS TP / 예산 | THEIA TP / 예산 | 판정 |
|---|---:|---:|---|
| 공식/local | 23 / 1,103 | 16 / 503 | 기준 |
| FlowSub | 29 / 1,103 | 25 / 503 | 성능 기준 |
| BEAR v1 | 26 / 1,103 | 16 / 503 | 상호작용 전이 실패 |
| BEAR v2 | 22 / 1,103 | 미실행 | 길이 보정 실패 |
| RAVEL v1 full | 23 / 1,103 | 미실행 | root evidence 이중 사용 |
| RAVEL v2 | 28 / 1,103 | 17 / 503 | CADETS 강함, THEIA 불안정 |
| RAVEL v3 | 23 / 1,103 | 미실행 | 보존 제약이 교체 차단 |

RAVEL v2의 CADETS precision, recall, MCC는 `0.02539`, `0.41176`, `0.10148`이고 세 공격 파일이 `2,17,5→3,21,7`로 모두 개선됐다. FlowSub보다 TP 하나 낮지만 detector와 causal score의 가중합이나 부분모듈 coverage 없이 하나의 조건부 proof ledger만 사용한다.

THEIA의 precision, recall, MCC는 `0.03380`, `0.14407`, `0.06946`으로 aggregate는 한 node 늘었다. 그러나 공격별 회수가 `12,4→5,12`라서 한 공격의 큰 손실을 다른 공격의 이득이 가렸다. 따라서 RAVEL이 performer 간 전이되거나 FlowSub와 같은 성능을 낸다는 주장은 기각한다.

RAVEL v3는

\[
\mathcal L(\mathbf1)=1
\]

과 root별 최소 \(1/B\) 개입 손실을 합성 검사와 실제 manifest에서 만족했다. 하지만 CADETS TP가 23으로 돌아가 수학적 보존 성질과 attribution 성능이 같은 것이 아님을 보여준다.

이 실험의 긍정적 결과는 새로운 단일-ledger 정의와 CADETS 개발 가능성이다. 부정적 결과는 THEIA 강건성, 외부 검증, 기존 최고 개발 점수 대체가 아직 없다는 점이다. 전체 수식과 novelty 경계는 `docs/ravel.md`에 기록했다.

### Proof-mass transport 구조 검사

RAVEL v4는 root마다 하나의 조사 질량을 공급하고 node capacity를 하나로 제한하는 greedy maximum-weight matching으로 등록했다. 합성 검사에서는 질량 보존, 정확한 예산, 중복 방지, 단조변환 불변성과 \(1/2\) 근사 경계가 성립했다. 그러나 label-free CADETS와 THEIA manifest에서 비root transport가 모두 0개여서 metric evaluator를 실행하지 않고 구조적으로 기각했다.

V4의 원인은 조건화한 root의 detector score를 singleton utility로 다시 사용한 scale 불일치였다. 이를 제거한 conditional transport v5를 별도 등록했다. V5는 root 자기 간선을 0 utility fallback으로 두고 비root 간선을 account route capital의 상대 intervention loss로 정의한다. Label-free 구조 검사에서 CADETS는 1,103개 중 9개, THEIA는 503개 중 13개 슬롯을 proof node로 운반했고, 두 데이터 모두 root/node degree와 총 질량 1을 보존했다.

V5의 CADETS·THEIA 악성 node metric은 계산하지 않았다. 이 결과는 방법이 비자명하게 작동한다는 구조 검사일 뿐 성능 증거가 아니며, H501·H201의 동결 top-512 외부 평가만 최종 판정에 사용한다.

### Exact transport 구조 검사

RAVEL v6는 v5 utility와 후보를 바꾸지 않고 greedy matching만 exact minimum-cost flow로 교체했다. 합성 3-root 그래프의 729개 weight 조합에서 전수조사 optimum과 모두 일치했다.

별도 구현 감사에서는 seed `20260731`의 무작위 희소 이분 그래프 2,000개를 생성해 SciPy `linear_sum_assignment`와 비교했고 목적값이 모두 절대 오차 `1e-12` 안에서 일치했다. 이는 배정 구현 검증이며 악성 node 회수 성능 증거로 사용하지 않는다.

| 데이터 | v5 objective | v6 objective | proof transport | v6 runtime |
|---|---:|---:|---:|---:|
| CADETS E3 | 3.176187 | 3.178597 | 9 | 6.10초 |
| THEIA E3 | 4.130598 | 4.130598 | 13 | 12.18초 |

CADETS는 충돌한 슬롯 하나를 재배정해 objective가 `0.002410` 증가했다. THEIA는 동일 objective의 다른 결정론적 최적해를 반환했다. 두 결과 모두 root degree 1, node degree 최대 1, 정확한 예산과 질량 1을 만족했다. Ordered manifest SHA-256은 CADETS `48470cf2087ebddfe912a20f8d78a869f6a23f5f79a1d0d185858070149b8e55`, THEIA `190d48b221c4892b96eda8627648812d0758da8b32222fe53d28d4f44b041e30`이다. Label evaluator는 실행하지 않았다.

### OpTC H051 미관측 외부 검사

RAVEL v2와 type-aware relation adapter를 label 접근 전에 동결했다. 공식 tuned Velox는 1,920개 validation loss 파일과 4,852개 test loss 파일을 생성했고 1,470,624개 test node를 score했다. 공식 `max_val_loss` threshold는 `18.091964721679688`이었지만 test 최대 node score는 `13.815710067749023`이었다.

따라서 공식 strict-threshold seed 예산은 0이었다. 라벨 비공개 reconstruction은 연속 chain 140개를 만들었지만 seed-anchored chain은 없었다. Ordered manifest SHA-256은 `6f23c493d7e188f1e7ba62bc2efc9d4a2782747484ed8c5d49b51da80c39caea`다.

사전등록한 stop rule에 따라 threshold나 top-k를 대체하지 않았고 RAVEL selector와 label-only evaluator도 실행하지 않았다. 이 결과는 RAVEL의 외부 성능 실패가 아니라 공식 detector가 비교 예산을 만들지 못한 `inconclusive_zero_official_budget` 경계다.

#### H051 fixed-capacity RAVEL-C 검사

위 zero-budget 연구와 별도로 top-512 조사 용량을 새로 등록했다. Label 접근 전 score, FlowSub route, v6, certified output과 계획을 freeze `af72b40f0552ad0b368161ffd1b10c379d7c2cee838debfa919dbf72f9d829b1`로 묶고 독립 감사 `474b793467a7adabf2d486ddb880e79799975331c80bd904440193838595b942`를 통과했다. 113,495개 proof transport 후보 중 4개가 모든 route를 완전히 끊었고 네 개 모두 배정됐다.

| 방법 | 예산 | 악성 UUID | precision | covered recall | MCC |
|---|---:|---:|---:|---:|---:|
| Velox top-512 | 512 | 4 | 0.00781 | 0.03509 | 0.01640 |
| FlowSub | 512 | 8 | 0.01563 | 0.07018 | 0.03296 |
| RAVEL v6 | 512 | 2 | 0.00391 | 0.01754 | 0.00812 |
| RAVEL-C V4 | 512 | 3 | 0.00586 | 0.02632 | 0.01226 |

RAVEL-C는 v6보다 1개를 복구했지만 Velox보다 1개 적다. 네 인증 이동 중 하나가 악성 root를 unlabeled target으로 바꿨고 candidate-only 악성 UUID는 0개였다. 따라서 primary safety를 포함한 네 등록 조건을 모두 기각한다. 구조적 full fracture는 actorID 안전성을 의미하지 않는다.

### 수정 OpTC H501 개발 전 평가 기록

Majorczyk et al.의 수정 OpTC raw와 공식 corrected actorID label을 사용했다. Label 접근 전에 Velox와 input-matched TGN의 score·route·v5·v6·topology/rank 대조군 11개 파일을 동결했고, frozen manifest `4b7f3134ebe845b81ea5f150c2f37e80346228168a9767657148bcb04faa3179`에 대해 byte·hash·lineage·budget·capacity·mass·optimality 감사가 통과했다.

| 백본 | top-512 TP | topology TP | rank TP | RAVEL v6 TP | v6 proof transport |
|---|---:|---:|---:|---:|---:|
| Velox | 7 | 3 | 7 | 10 | 59 |
| TGN | 2 | 1 | 4 | 4 | 57 |

Velox 경로에서 precision은 `0.01367→0.01953`, covered recall은 `0.08140→0.11628`, MCC는 `0.03322→0.04752`로 증가했다. 바뀐 59개 slot 중 baseline-only 악성 actorID는 4개, v6-only는 7개로 순증가 3개다. 조건부 exact 기술 통계는 단측 `p=0.26425`이므로 일반화 검정으로 해석하지 않는다. Topology-only는 3개, rank-only는 baseline과 같은 7개, exact node intervention은 10개를 회수해 H501 Velox 결과의 추가 이득은 topology나 validation rank만으로 설명되지 않는다.

TGN 경로에서도 precision `0.00391→0.00781`, covered recall `0.02326→0.04651`, MCC `0.00939→0.01893`으로 증가했다. 그러나 rank-only와 v6가 모두 4개라 이 백본에서는 exact deletion의 추가 aggregate 이득이 관측되지 않았다.

Aggregate는 두 백본에서 모두 개선됐지만 Velox는 3개, TGN은 1개 process-interval segment에서 baseline보다 적게 회수했다. 따라서 사전 등록한 `segment_no_decline`과 `host_success`는 모두 거짓이다. 방법·평가기준을 수정하지 않으며 H201 mandatory replication을 동일 설정으로 실행한다.

## MAGIC 전처리 그래프 강건성 검사

MAGIC 공개 anomaly score와 ThreaTrace coarse label을 사용해 동결된 정적 그래프 어댑터를 THEIA와 TRACE에 적용했다. 이 검사는 ORTHRUS fine-label 평가와 다른 실험이며 수치를 직접 합치지 않는다.

| 데이터 | anomaly AUROC | anomaly AP | 유효 체인 | 체인 결합 후 변화 |
|---|---:|---:|---:|---:|
| THEIA E3 | 0.99873 | 0.97685 | 0 | 없음 |
| TRACE E3 | 0.99982 | 0.99840 | 0 | 없음 |

강한 anomaly 점수는 MAGIC의 공개 결과이며 우리 방법의 성과가 아니다. 두 데이터 모두 보고서 조건을 만족한 체인이 없어 ranking을 악화시키지도 개선하지도 않았다. 이 음성 결과는 정적 전처리 그래프가 시간·세션 기반 체이닝에 충분하지 않다는 CADETS 관찰을 재현한다.

## 구현 계약 재검증

논문 작성 후 방법 상수를 `src/wisa_agent/method/config.py`로 중앙화했다. 수치나 연산 순서는 변경하지 않았으며 `paper/check.py`가 원고 수식, 구현 상수, 원시 결과를 함께 검사한다. 워크스테이션에서 seed 5400을 500 step 재실행한 결과 LayerChain과 report v6의 reward, 행동, 공격 telemetry가 저장된 최종 run과 정확히 일치했다. 최종 평가 뒤 추가된 값이 0인 v9·v10 진단 필드 두 개는 행동 비교에서 제외했다.

## RAVEL 수정 OpTC 개발 기록

H501과 H201 모두 score, route, v5, v6와 두 ablation을 먼저 동결·감사한 뒤 수정 actorID label을 열었다. Budget은 host별 512다.

| Host | positive | Velox | FlowSub | topology | rank | v5 | v6 | v6 감소 interval |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| H501 | 86 | 7 | 11 | 3 | 7 | 10 | 10 | 3/65 |
| H201 | 352 | 2 | 4 | 1 | 1 | 1 | 1 | 1/216 |
| 기술적 합계 | 438 | 9 | 15 | 4 | 8 | 11 | 11 | 4/281 |

H501은 59개 slot을 바꾸며 악성 UUID를 7개에서 10개로 늘렸다. Precision `0.01367→0.01953`, covered recall `0.08140→0.11628`, MCC `0.03322→0.04752`다. 그러나 세 attack interval에서 Velox보다 감소했다.

Mandatory H201은 107개 slot을 바꾸며 악성 UUID가 2개에서 1개로 줄었다. Precision `0.00391→0.00195`, covered recall `0.00568→0.00284`, MCC `0.00442→0.00206`이다. Exact v6는 greedy v5보다 proof objective를 높이고 10개 slot을 바꾸지만 true positive를 바꾸지 않는다.

FlowSub는 H501 11개, H201 4개로 RAVEL보다 강하다. H501 FlowSub 비교 결정은 label 공개 뒤였고 H201 비교는 label 공개 전에 등록됐다. 보조 TGN은 H501 `2→4`, H201 `2→1`이며 H201 feature pipeline이 Velox와 달라 통제된 encoder ablation으로 해석하지 않는다.

H501과 H201은 같은 campaign의 서로 다른 host이므로 `9→11` 합계는 기술적으로만 보고한다. 두 host aggregate 개선과 모든 interval no-decline을 요구한 사전 가설은 기각한다.

## 판정

- 방어 에이전트: v12는 두 Red 정책의 최종 100-episode 평가에서 LayerChain보다 reward가 유의하게 높고 모든 공격 영향 지표가 유의하게 낮았다.
- 공격 에이전트 개발 근거: 공식 Velox seed와 동결 체인 탐색의 결합은 CADETS와 THEIA에서 같은 예산의 Velox top-k보다 악성 노드를 각각 7개와 11개 더 회수했다. 이미 본 E3 데이터이므로 최종 외부 성능 근거로 사용하지 않는다.
- 수학적 선택: FlowSub는 공식 seed와 같은 예산에서 CADETS 악성 node를 23개에서 29개, THEIA를 16개에서 25개로 늘렸다. Ablation상 성능 원인은 exact counterfactual responsibility와 submodular budget exchange이며 conserved flow의 추가 기여는 지지되지 않는다.
- 단일-ledger novelty: RAVEL은 계층 proof, chaining, root orchestration과 exact global node intervention을 하나의 조건부 ledger로 정의하고, 다중 삭제를 submodular weighted coverage로 일반화한다.
- 공격 에이전트 개발 기록: fractional RAVEL은 수정 OpTC H501 `7→10`, H201 `2→1`이고 hostwise·interval 성공 조건을 기각했다. 두 label은 이후 인증형 projection 개발에 쓰였으므로 외부 검증으로 재사용하지 않는다.
- 공격 에이전트 홀드아웃: 별도 등록한 H051 top-512에서 Velox 4, FlowSub 8, fractional RAVEL 2, RAVEL-C 3이다. 네 성공 조건이 모두 실패했으며 SOTA나 actor-recall safety를 주장하지 않는다. 기존 strict-threshold zero-budget 연구는 별개의 불확정 결과로 보존한다.
- 공격 에이전트 E5 검증: CDM20에서 체인은 형성됐지만 matched-budget 악성 노드 회수가 11개에서 4개로 악화돼 일반화에 실패했다.
- E5 원인 분리: CADETS no-path 진단에서 attribution 우위가 역전돼 event path 손실이 주요 표현 한계라는 근거를 얻었지만 E5의 단일 원인으로 확정하지 않는다.
- 체인 경보 calibration: 두 performer에서 경보량은 줄였지만 공격 회수가 anomaly-only보다 낮고 공격 없는 날 경보가 남아 실패했다.
- 정적 그래프 어댑터: THEIA와 TRACE에서 체인을 만들지 못해 기여가 없다.
- 방법론: 계층·체인 표현과 반사실 책임도의 부분모듈 예산 교환은 공격 조사 우선순위를 개선하고, 증거 범위를 행동 범위에 연결한 오케스트레이션은 평가한 CAGE 조건에서 방어를 개선했다. TC 경보 calibration은 추가 연구가 필요하다.
- 연구 주장: CAGE 방어 우월성은 두 Red 정책과 내부 LayerChain 비교에 한정한다. 공격 측의 주 기여는 formal budgeted-attribution objective와 leakage-resistant mixed-result evaluation이다. E5/CDM20 일반성, OpTC hostwise 우월성, detector ranking·자동 침투 성공률·낮은 오탐 경보는 주장하지 않는다.

모든 실패 버전과 원시 결과는 `results`에 보존했다. 고정 파라미터와 변경 이유는 `docs/protocol.md`에 기록했다.
