# 완료 감사

감사 기준일은 2026년 7월 30일이다. 이 문서는 예선 보고서 기반 공·방 에이전트 설계, CAGE Challenge 4와 DARPA TC E3/E5 평가, 선행 연구·공개 코드 검토, 과적합 방지, 논문 산출물을 요구사항별로 대조한다.

## 요구사항 대조

| 요구사항 | 구현과 증거 | 상태 |
|---|---|---|
| 예선 보고서를 토대로 방어 에이전트 설계 | 보고서 2장과 3.2절의 입력 정규화, 다중 근거 상관분석, 규칙·정상 이탈 위험도, 동적 허니팟, 가역적 대응, 효과 확인, MetaMonitor를 `src/wisa_agent/method/defense.py`와 `src/wisa_agent/cage/report.py`에 반영했다. 세부 대응표는 `docs/method.md`에 기록했다. | 완료 |
| 계층 탐색·predicate·체이닝·오케스트레이션 기반 공격 에이전트 설계 | 정상 provenance 구조·전이·경로 profile, 18초 process trace, 단계별 predicate, best-first chain 탐색, baseline·single·pairwise·combined·negative 실험 계획을 `src/wisa_agent/method`와 `src/wisa_agent/tc/cdm_agent.py`에 구현했다. | 완료 |
| 벤치마크에 종속되지 않는 공통 방법 | 공통 코어는 `Evidence`, `Predicate`, `Chain`, `Finding`만 처리한다. CAGE 관측과 CDM relation 해석은 어댑터에 분리했다. 공통 코어의 데이터셋명, performer명, 정답 UUID, 고정 hostname, 평가 seed 검색 결과는 0건이다. | 완료 |
| CAGE Challenge 4 방어 평가 | 공식 commit, 기본 Red와 체인형 Red, 500 step, paired seed를 사용했다. v12는 독립 개발·검증 20회와 두 Red별 최종 100회를 실행했으며 원시 결과와 bootstrap 통계를 보존했다. | 완료 |
| DARPA TC E3/E5 공격 평가 | CADETS E3 개발, THEIA E3 외부 검증, ClearScope E5 외부 평가를 수행했다. 정상 profile과 validation threshold를 먼저 고정하고 fine label은 출력 뒤 metric 계산에서만 읽었다. | 완료 |
| 나쁜 결과 판별과 방법 수정 | 방어 v7–v11과 공격 v1–v7을 분리해 평가했다. 실패 결과를 삭제하지 않았고, 새 분할에서 범위 제약 v12만 개발·검증 조건을 통과해 최종 평가했다. | 완료 |
| 과적합과 통계 조작 방지 | 개발·검증·최종 분할, paired 비교, bootstrap 95% 구간, 변경 규칙, 외부 평가 순서를 `docs/protocol.md`에 사전 기록했다. v10의 예약 구간은 열지 않았고 v12는 별도 12400·13400·14400 seed 블록을 사용했다. | 완료 |
| 관련 논문과 공개 코드 검토 | CAGE 공식 환경·결과 논문·Cybermonic·H-MARL과 MAGIC·ORTHRUS·PIDSMaker·ThreaTrace·KAIROS의 방법, 평가 누수 위험, 공개 commit을 `docs/research.md`와 `paper/artifacts.json`에 기록했다. | 완료 |
| 논문과 결과 검증 | 익명 LNCS 12쪽 논문, 한·영문 초안, 참고문헌, 주장 감사표를 작성했다. `paper/check.py`가 원시 결과 hash, 표 수치, 구현 상수, 수식, 인용을 함께 검사한다. | 완료 |
| 코드와 보안 규칙 | Python 45개 파일의 tokenizer 기반 검사에서 주석 0개, 저장소의 OpenAI·GitHub·AWS 비밀 패턴 검색에서 0개 파일이 검출됐다. API 호출 없이 실험했으며 키를 저장하지 않았다. | 완료 |

## 최종 결과 판정

| 평가 | 제안 방법 | 비교 방법 | 판정 |
|---|---:|---:|---|
| CAGE 공식 Red 최종 reward, 100 episode | -2641.74 | LayerChain -3110.39 | v12가 +468.65 높고 paired 95% 구간은 [276.24, 656.89]이다. 우월성 지지 |
| CAGE 체인형 Red 최종 reward, 100 episode | -3108.22 | LayerChain -3703.61 | v12가 +595.39 높고 paired 95% 구간은 [410.39, 784.28]이다. 우월성 지지 |
| CADETS E3 고정 조사 예산 | 악성 17/530 | anomaly-only 10/530 | attribution 개선, AP는 0.126001에서 0.125996으로 개선되지 않음 |
| THEIA E3 외부 검증 | 악성 17/1218 | anomaly-only 8/1218 | attribution 방향 재현, 절대 AP 증가는 0.000428이고 공격 없는 날 출력이 남음 |
| ClearScope E5 외부 평가 | 악성 4/522 | anomaly-only 11/522 | attribution 일반화 실패 |

초기 방어 v6와 v7–v11은 좋지 않았지만, 행동 범위를 증거 범위에 맞춘 v12는 독립 개발·검증을 거쳐 두 Red 정책의 최종 평가에서 reward와 세 공격 영향 지표를 모두 개선했다. 최종 결과를 본 뒤 정책이나 상수를 다시 변경하지 않았다.

공격 방법은 CADETS와 THEIA E3에서 동일 조사 예산의 공격 연관 node 회수를 높였지만 node ranking과 저오탐 경보의 전반적 우월성은 입증하지 못했다. ClearScope E5에서는 방향이 뒤집혔다. 따라서 논문 주장은 `path와 시간 세션 정보가 보존된 E3 두 performer에서의 제한적 attribution 개선`으로 한정한다.

## 범위 경계

- 공격 에이전트는 실제 시스템 침투를 실행하는 도구가 아니라 로그에서 교차 계층 공격 가설과 조사 경로를 생성·검증하는 에이전트다.
- LLM은 최종 행동권을 갖지 않으며 이번 정량 실험에는 OpenAI API나 별도의 LLM-only baseline을 사용하지 않았다. 따라서 LLM 대비 우월성을 주장하지 않는다.
- CAGE 방어 우월성은 평가한 두 Red 정책과 내부 LayerChain 비교로 한정한다. E5/CDM20 공격 attribution 일반성과 낮은 오탐 경보 성능은 주장하지 않는다.
- 이번 감사까지의 변경은 로컬과 워크스테이션에만 있으며 GitHub commit, push, pull request는 이 감사 범위에서 수행하지 않는다.

## 최종 검증

- 노트북: `paper/check.py` 통과, 강화 방법·CDM 계약 테스트 21개 통과
- 워크스테이션: 공식 CAGE 경로를 포함한 전체 테스트 47개 통과
- 논문 PDF: 12쪽, US Letter, Type 1 글꼴 18개 모두 내장
- 논문 PDF SHA-256: `66a9a19fd4c0686ff49338868f01a32993daddcc85e744567b52af344a4847e6`
- 감사 문서, 방법 상수, 통합 결과, 원고, PDF의 SHA-256이 노트북과 워크스테이션에서 일치

## 재현 명령

```bash
python paper/check.py
pytest -q
```

워크스테이션의 공식 CAGE 환경을 포함한 전체 테스트와 논문 검증이 모두 통과해야 완료 상태로 본다.
