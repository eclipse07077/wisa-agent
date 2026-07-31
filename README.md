# wisa-agent

이 저장소에는 provenance 기반 공격 조사 방법 RAVEL-C와 CAGE Challenge 4 방어 에이전트 실험이 함께 있다.

RAVEL-C는 detector root마다 조건부 proof account를 만들고, UUID-continuous typed chain을 factorized proof로 표현한다. UUID 하나가 모든 route를 완전히 끊는지 singleton-hyperclause witness로 인증한 뒤, exact matching으로 다음 세 목적을 순서대로 최적화한다.

1. 인증 transport 수 최대화
2. Fractional proposal과의 Hamming 왜곡 최소화
3. Conformal evidence 최대화

최종 방법은 `ravel_cert_v4`다. H501과 H201은 개발 데이터이며 RAVEL-C recovery는 각각 Velox `7→8`, `2→2`였다. 사전등록한 H051 홀드아웃에서는 exact budget 512에서 Velox 4, FlowSub 8, fractional proposal 2, RAVEL-C 3이었다. 네 성공 조건이 모두 실패했으므로 SOTA나 actor-recall safety를 주장하지 않는다. 논문의 기여는 인증 가능한 fixed-budget formulation, exact lexicographic projection, fixed-budget safety의 불가능성 정리와 label-barrier 반증이다.

최종 논문은 `output/pdf/attack.pdf`, 작은 결과 요약은 `results/ravel.json`, 주장 감사표는 `paper/claims.md`에 있다.

## 구성

- `src/wisa_agent/tc`: proof account, transport, certificate
- `experiments`: label-free 선택, 동결, 독립 감사, label-only 평가
- `config`: 데이터셋과 실험 설정
- `results`: 고정 manifest, 감사 영수증, 결과 요약
- `docs`: 방법, 프로토콜, 문헌과 전체 실험 기록
- `paper`: 원고, 참고문헌, 자동 검증기

## 설치

```bash
python -m pip install -e ".[test,tc]"
```

PIDSMaker와 CAGE는 공식 저장소를 별도로 받아 해당 실행의 `PYTHONPATH`에 추가한다.

## 핵심 검증

```bash
python -m pytest -q tests/test_cert.py tests/test_cert_check.py tests/test_orthrus_eval.py
python paper/attack-check.py
```

첫 명령은 complete-fracture equivalence, full certified graph, 세 단계 objective와 독립 audit를 검사한다. 두 번째 명령은 H051 label barrier, hash, 결과, 논문 수치와 PDF 페이지를 함께 검사한다.

## H051 재현 순서

Label-free selection과 독립 감사는 다음 순서다.

```bash
python experiments/cert.py \
  --source results/v6-051.json.gz \
  --routes results/route-051.json.gz \
  --plan results/cert-plan.json \
  --output results/cert-051.json.gz

python experiments/cert_check.py \
  --frozen results/frozen-051.json \
  --directory results \
  --output results/audit-051.json
```

`results/frozen-051.json`이 기록한 33 MB score manifest는 용량 때문에 워크스테이션에만 보존하며 hash는 `551fc12945a6b71d4549c5763e1c3fd8f502b94fcd0eb01fed2e11f025341b0c`다. 감사 통과 뒤 별도 label-only evaluator로 생성한 결과가 `results/eval-cert-051.json`이다. 정확한 접근 시점과 네 endpoint 판정은 `results/label-051.json`에 있다.
