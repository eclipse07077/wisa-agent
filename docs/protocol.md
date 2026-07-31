# 실험이랑 재현 기록

최종 논문에 필요한 split·seed·label barrier·결과 파일만 정리한 문서. 개발 중 매 실행마다 쌓였던 긴 일지는 뺐음. 정확한 파일 hash는 `paper/artifacts.json`이랑 `paper/attack.json`에 기계 판독 가능한 형태로 남아 있음.

## 1. 공통 규칙

- 공통 코어에 데이터셋 이름·정답 UUID·공격 시각·고정 hostname·CAGE action index 안 넣음
- Test label로 threshold·epoch·seed·가중치·탐색 깊이 안 고름
- 개발·검증·최종 split 분리
- Final 결과 보고 같은 split에서 방법 다시 고르지 않음
- 실패 버전이랑 불리한 결과도 삭제 안 함
- TC label은 출력 고정 뒤 metric 계산에서만 읽음
- CAGE는 같은 seed끼리 paired 비교
- CAGE 신뢰구간은 run-level 차이를 10,000번 bootstrap
- TC node는 서로 독립 표본이 아니라서 node 수로 유의성 검정 안 함

## 2. 고정 방법

| 구분 | 최종 버전 |
|---|---|
| 공통 체인 | evidence–predicate–chain |
| 방어 | `report_v12` |
| TC 통합 원고 공격 조사 | `grounded_trace_v4` |
| 공격 전용 조사 | `ravel_cert_v4` |

공통 chain 상수.

| 항목 | 값 |
|---|---:|
| 시간 근접성 | 0.30 |
| Shared context | 0.30 |
| 단계 진행 | 0.25 |
| Mission effect | 0.15 |
| Edge threshold | 0.58 |
| 시간 창 | 18초 |
| 최대 길이 | 5 |

Grounded trace anomaly 상수.

| 항목 | 값 |
|---|---:|
| Structure | 0.50 |
| Trace | 0.30 |
| Path | 0.20 |
| Validation threshold | 0.995 quantile |

방어 risk 상수.

| 항목 | 값 |
|---|---:|
| Confidence | 0.35 |
| Severity | 0.25 |
| Chain correlation | 0.25 |
| Asset criticality | 0.15 |

RAVEL-C는 학습 threshold 없음. Detector budget `B`를 그대로 쓰고 complete-fracture certificate랑 exact matching만 적용.

## 3. CAGE Challenge 4

### 환경

- 공식 저장소 commit: `8c3c50ca54b176c2de199847944e8dcc035497e3`
- Episode 길이: 500 step
- 공식 공격: `FiniteStateRedAgent`
- 추가 공격: `ChainAwareRedAgent`
- 비교군: 내부 `LayerChain`
- 최종 방법: `report_v12`

LayerChain은 공개 대회 상위 제출물 재현이 아님. 같은 저장소 안에서 만든 계층형 내부 baseline.

### Split

| 단계 | Seed | 용도 |
|---|---|---|
| 초기 개발 | 3400~3419 | v6이랑 초기 ablation |
| 초기 검증 | 4400~4419 | 동결 v6 재검사 |
| 초기 최종 | 5400~5499 | v6 최종 실패 확인 |
| 후속 개발 | 6400~6419 | v9·v10 행동 구조 확인 |
| 미개봉 검증 | 7400~7419 | v9·v10 미선택으로 안 열었음 |
| 미개봉 최종 | 8400~8499 | v9·v10 미선택으로 안 열었음 |
| v11 개발 | 9400~9419 | Temporal belief·static utility 실패 확인 |
| v12 개발 | 12400~12419 | Scope constraint 개발 |
| v12 검증 | 13400~13419 | 코드 고정 전 검증 |
| v12 최종 | 14400~14499 | Red별 100 paired episode |

v12는 개발이랑 검증에서 두 Red 정책 모두 reward랑 공격 영향 지표가 악화되지 않는 걸 확인한 뒤 final을 열었음. Final 결과 뒤 상수나 정책 안 바꿈.

### 최종 지표

Primary는 누적 Blue reward. Secondary는 unique privileged host랑 impacted host랑 successful Impact.

| Red | 비교 | Reward 차이 | 95% 구간 |
|---|---|---:|---:|
| 공식 | v12 - LayerChain | +468.65 | [276.24, 656.89] |
| Chain-aware | v12 - LayerChain | +595.39 | [410.39, 784.28] |

원본이랑 요약.

- `results/cage-v12-final-100x500.json`
- `results/cage-v12-final-default-stats.json`
- `results/cage-v12-final-chain-stats.json`
- `results/defense.json`

### 실패 기록

| 버전 | 결과 | 판정 |
|---|---|---|
| v6 | LayerChain보다 -564.72 | 초기 보고서 정책 실패 |
| v9 | -2738.65 악화 | 선택 안 함 |
| v10 | LayerChain보다 -457.45 | 선택 안 함 |
| v11 | 두 Red에서 각각 -751.90·-971.05 | 선택 안 함 |
| v12 | 두 Red 모두 개선 | 최종 선택 |

v6~v11은 risk 계산보다 action scope가 문제였음. 부분 `Remove`가 process랑 connection evidence 범위를 못 덮었고 같은 강한 행동도 반복됐음. v12는 가중치 재튜닝 없이 구조를 바꿨음.

## 4. DARPA TC Grounded trace

### 데이터 split

| 데이터 | Normal train | Validation | Test·개발 |
|---|---|---|---|
| CADETS E3 | 3·4·5·7·8·9·10일 | 2일 | 6·11·12·13일 개발 |
| THEIA E3 | 2·3·4·5일 | 9일 | 10·12·13일 외부 적용 |
| ClearScope E5 | 8·9일 | 11일 | 14·15·17일 외부 적용 |

Grounded trace v4는 CADETS에서 고정. THEIA랑 ClearScope에는 relation-stage mapping이랑 18초 window랑 threshold 규칙을 안 바꾸고 적용.

Fine ground truth는 ORTHRUS/PIDSMaker UUID 사용. MAGIC/ThreaTrace coarse neighborhood label은 이 결과랑 합치지 않음.

| 데이터 | 전체 node | Covered positive | Label coverage |
|---|---:|---:|---:|
| CADETS E3 | 297,085 | 68 | 94.44% |
| THEIA E3 | 701,622 | 118 | 100% |
| ClearScope E5 | 150,964 | 51 | 100% |

평가는 두 종류.

- Ranking: AUROC랑 AP
- Attribution: 같은 조사 node budget에서 악성 node 몇 개 찾았는지

공격 없는 날 reported node도 따로 셌음.

결과 파일.

- `results/tc-cadets-raw-trace-grounded-dev.json`
- `results/tc-theia-raw.json`
- `results/tc-clearscope-e5.json`
- `results/tc-cadets-no-path.json`
- `results/attack.json`

ClearScope E5 결과 뒤 E5를 다시 튜닝하지 않았음. Path 손실 가설은 CADETS 전체 split에서 path만 제거하는 진단으로 확인. 이 진단은 path 중요성만 지지하고 E5 실패 원인 전체를 증명하진 않음.

## 5. RAVEL-C

### 개발이랑 holdout

| 데이터 | 역할 | Label 사용 시점 |
|---|---|---|
| H501 | 개발 | 최종 RAVEL-C 설계 전에 확인했음 |
| H201 | 개발 | 최종 RAVEL-C 설계 전에 확인했음 |
| H051 | Holdout | 방법·예산·비교군·성공 조건 동결 뒤 처음 확인 |

H501이랑 H201은 결과가 괜찮아도 외부 검증이라고 안 부름. 두 label이 certified projection 만드는 과정에 영향을 줬음.

H051 고정 내용.

- PIDSMaker commit: `54f687c54aa03e5519cf44953d5ee44f5f6a4a28`
- Budget: 512
- 비교군: Velox·FlowSub·fractional RAVEL v6
- 최종 방법: `ravel_cert_v4`
- 성공 조건: primary safety·secondary efficacy·FlowSub noninferiority·모든 비교군 strict superiority

### Label barrier

H051 label 보기 전에 아래 파일을 먼저 만듦.

1. `score-051.json.gz` 워크스테이션 대용량 score
2. `results/route-051.json.gz`
3. `results/v6-051.json.gz`
4. `results/cert-051.json.gz`
5. `results/cert-plan.json`
6. `results/frozen-051.json`

Ordered freeze SHA-256은 `af72b40f0552ad0b368161ffd1b10c379d7c2cee838debfa919dbf72f9d829b1`.

`score-051.json.gz`는 33MB가 넘는 중간 score라 GitHub에는 안 넣었음. Byte 수랑 SHA-256이 `results/frozen-051.json`이랑 `results/ravel.json`에 남아 있어서 최종 선택이 어떤 score에서 나온 건지는 확인 가능.

독립 감사 `results/audit-051.json`이 source matching이랑 certified matching이랑 code lineage랑 route witness를 다시 계산. 감사 SHA-256은 `474b793467a7adabf2d486ddb880e79799975331c80bd904440193838595b942`.

감사 통과 뒤 처음 label을 열고 `results/eval-cert-051.json` 생성. 평가 SHA-256은 `cee25b17dc9310feaf81d7a35da7732e96e189aa1175284b508570742de98ca8`.

### H051 결과

| 방법 | 악성 UUID 회수 |
|---|---:|
| Velox | 4 |
| FlowSub | 8 |
| Fractional v6 | 2 |
| RAVEL-C | 3 |

등록한 성공 조건 네 개 전부 실패. 결과 뒤 방법이나 endpoint 안 바꿈.

최종 요약은 `results/ravel.json`. 주장 경계는 `paper/claims.md`.

## 6. 참고 코드 commit

| 대상 | Commit |
|---|---|
| CAGE Challenge 4 | `8c3c50ca54b176c2de199847944e8dcc035497e3` |
| Cybermonic | `2afd652d80ce9d4051a07c23c2538f3dec6bb6c6` |
| MAGIC | `aa0b647eea74b6faa0e52eb444370c4411a32cbe` |
| ORTHRUS | `e7f25dfee1ddd182a955b88f8a90a8cbd4a8e543` |
| PIDSMaker Velox | `54f687c54aa03e5519cf44953d5ee44f5f6a4a28` |
| 수정 OpTC code | `644f41fb0a955e471f34bed016fb2bfd9c74dc04` |

논문이랑 공개 코드에서 실제로 참고한 부분은 `docs/research.md`에 있음.

## 7. 결과 파일 기준

최종 숫자 확인은 이 네 파일부터.

| 파일 | 내용 |
|---|---|
| `results/results.json` | 공·방 통합 결과 |
| `results/defense.json` | 방어 최종 결과 |
| `results/attack.json` | Grounded trace 결과 |
| `results/ravel.json` | RAVEL-C 결과 |

세부 raw 파일은 위 섹션 표에 적은 파일 사용. 논문 수치 checker는 JSON에 기록된 hash랑 표 수치를 같이 확인.

## 8. 재현 명령

노트북에서 먼저 실행.

```powershell
$env:PYTHONPATH = "$PWD;$PWD\src"
python paper/check.py
python paper/attack-check.py
$skip = @('test_core.py','test_red.py','test_report.py','test_telemetry.py')
$tests = Get-ChildItem tests -Filter test_*.py | Where-Object { $_.Name -notin $skip }
pytest -q $tests.FullName
```

CAGE가 설치된 워크스테이션에선 전체 테스트.

```powershell
$env:PYTHONPATH = "$PWD;$PWD\src"
pytest -q
```

RAVEL-C 핵심만 확인할 때.

```powershell
pytest -q tests/test_cert.py tests/test_cert_check.py tests/test_orthrus_eval.py
```

실험을 다시 돌릴 때는 기존 final seed에서 방법을 다시 선택하면 안 됨. 새 방법은 새 dev·validation·final block을 먼저 정하고 진행.

## 9. Artifact registry

- 공·방 통합 artifact: `paper/artifacts.json`
- RAVEL-C artifact: `paper/attack.json`
- 통합 checker: `paper/check.py`
- RAVEL-C checker: `paper/attack-check.py`

Markdown 문서는 사람이 보는 요약. 최종 hash랑 commit이 필요하면 JSON registry를 기준으로 확인.
