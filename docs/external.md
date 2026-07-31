# 외부 평가 기록

이 문서는 fractional RAVEL v6 단계에서 수행한 H501·H201 평가의 동결 기록이다. 이후 두 host의 label이 인증형 projection 개발에 사용됐으므로 최종 논문에서는 둘을 개발 데이터로만 분류한다. 최종 외부 판정은 별도 label barrier를 통과한 H051 fixed-capacity 평가이며 Velox 4, FlowSub 8, v6 2, RAVEL-C 3으로 네 성공 조건이 모두 실패했다.

## 평가 경로

이 단계의 외부 평가는 Majorczyk 등이 공개한 수정 OpTC DOI `10.57745/UXCWOC`와 라벨·정정 코드 commit `644f41fb0a955e471f34bed016fb2bfd9c74dc04`를 사용했다. H501은 당시 primary, H201은 결과와 무관하게 실행하는 mandatory replication으로 등록했다.

원래 등록한 PIDSMaker H501·H201 PostgreSQL dump는 hosted distribution에서 확보하지 못했다. 따라서 수정 raw 결과를 원본 dump와의 paired robustness 비교나 공식 dump score 재현으로 부르지 않는다. 아래 Velox는 공개 구현, host 설정과 가중치를 수정 JSON의 process·file·netflow projection에 적용한 결과다.

## 라벨 장벽

두 host 모두 19–21일 train, 22일 validation, 23–25일 test, budget 512, RAVEL v6 수식과 exact transport를 사용한다. 공격 라벨은 다음 파일이 모두 생성되고 ordered hash 감사가 통과한 뒤에만 복구했다.

- detector score
- label-free route
- greedy v5
- exact v6
- topology-only와 rank-only ablation

H501 freeze SHA-256은 `4b7f3134ebe845b81ea5f150c2f37e80346228168a9767657148bcb04faa3179`, audit SHA-256은 `36af313d3bba121e1258f28465ce3c378afcb9e4d6aaae1c68835debdb824566`이다.

H201 freeze SHA-256은 `b87874150b7a9a9929354911da9254e804379cd63b30f5930499da6a46f883bc`, audit SHA-256은 `b91eb26f5bf1f15bd13b004e61ebb8849a0cb4c9978279f212f922a7a35cbd5c`이다.

H201 라벨 파일은 공개 commit의 exact blob과 일치한다. Event SHA-256은 `a984e0c93ff4c5895cb9f3deacdc6ec7669e1becaabe1fa797d5227a4e722c93`, segment SHA-256은 `87e53d592c661080c355b4bd3c3e9ad603b863ab7c1db242177e2afc401bec93`이다.

## 결과

Positive는 수정 host event에서 `actorID`로 나타나는 process UUID다. File과 netflow는 조사에 유용할 수 있어도 이 ground truth에서는 unlabeled로 계산한다.

| Host | covered positive | Velox | FlowSub | topology | rank | v5 | v6 | v6 감소 interval |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| H501 | 86 | 7 | 11 | 3 | 7 | 10 | 10 | 3/65 |
| H201 | 352 | 2 | 4 | 1 | 1 | 1 | 1 | 1/216 |
| 기술적 합계 | 438 | 9 | 15 | 4 | 8 | 11 | 11 | 4/281 |

H501에서 v6는 59개 slot을 바꾸며 baseline-only 악성 4개와 candidate-only 악성 7개를 만든다. Precision은 `0.0136719→0.0195313`, covered recall은 `0.0813953→0.1162791`, MCC는 `0.0332248→0.0475244`다. 같은 대칭차에 조건화한 단측 기술 확률은 `0.2642477`이다.

H201에서는 107개 slot을 바꾸며 baseline-only 악성 1개를 잃고 candidate-only 악성을 추가하지 못한다. Precision은 `0.0039063→0.0019531`, covered recall은 `0.0056818→0.0028409`, MCC는 `0.0044171→0.0020609`다. 단측 기술 확률은 `1.0`이다.

H501과 H201은 한 campaign 안의 서로 다른 host·scenario이므로 합계 9→11을 독립 replication이나 일반화 검정으로 사용하지 않는다. H501의 FlowSub 비교 결정은 host label 공개 뒤였지만 선택 자체는 공개 전에 동결됐다. H201 FlowSub 비교 결정은 label 공개 전 등록됐다.

## 보조 TGN

TGN top-512와 RAVEL은 H501에서 `2→4`, H201에서 `2→1`이다. H201 tuned Velox는 1분 graph window, Word2Vec seed 0, 256차원 출력을 쓰지만 TGN은 15분, seed 16, 128차원을 사용한다. 따라서 H201 TGN은 input-matched encoder ablation이 아니라 feature pipeline과 architecture가 함께 변하는 민감도 진단이다.

## 판정

사전 조건은 두 host 모두에서 aggregate recovery가 증가하고 어떤 nonempty attack interval도 감소하지 않는 것이었다. H501은 aggregate가 증가하지만 세 interval이 감소했고, H201은 aggregate와 한 interval이 감소했다. 외부 성능 우월성 가설은 기각한다.

H501의 대표 성공은 utility 1인 악성 actor가 모든 양의 proof realization을 끊은 사례다. H201의 대표 실패는 utility `0.0548`인 unlabeled actor가 악성 detector root를 대체한 사례다. Zero-valued hold에서는 어떤 양의 fracture도 root 유지보다 선호되므로 proof utility와 actorID recovery가 항상 정렬되지 않는다. 이 분석은 label 공개 후 설명이며 방법 수정에 사용하지 않는다.
