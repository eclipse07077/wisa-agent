# wisa-agent

CAGE Challenge 4와 DARPA Transparent Computing에서 계층 탐색, 공격 체인 추적, 분산 방어 오케스트레이션을 평가하기 위한 연구 코드다.

## 현재 범위

- CAGE 관측 벡터의 동적 계층 복원
- 시간·인과 기반 공격 체인 점수화
- 8비트 메시지를 사용하는 다중 Blue 에이전트
- 체인 완결을 우선하는 Red FSM 변형
- 기본 Red와 체인형 Red에 대한 비교 실험

## 구조

```text
src/wisa_agent/cage/
  core.py
  blue.py
  red.py
  telemetry.py
  wrapper.py
  teams.py
experiments/
  run.py
  batch.py
  summary.py
results/
tests/
```

## CAGE 비교 실험

```bash
PYTHONPATH=/path/to/cage-challenge-4:src \
python experiments/run.py \
  --episodes 3 \
  --steps 500 \
  --output artifacts/pilot.json
```

예비 결과는 `docs/pilot.md`, 30개 시드 결과는 `docs/result.md`에 기록했다.

30개 시드 병렬 비교와 요약 파일 생성은 다음과 같이 실행한다.

```bash
PYTHONPATH=/path/to/cage-challenge-4:src \
python experiments/batch.py \
  --episodes 30 \
  --steps 500 \
  --jobs 3 \
  --output artifacts/cage-30x500.json

python experiments/summary.py \
  artifacts/cage-30x500.json \
  --json-output results/summary.json \
  --csv-output results/summary.csv
```
