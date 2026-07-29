# CAGE 예비 실험

## 설정

- CAGE 커밋: `8c3c50ca54b176c2de199847944e8dcc035497e3`
- 에피소드: 조건별 3개
- 길이: 에피소드당 500스텝
- 시드: 3407, 3408, 3409
- 지표: 에피소드 누적 Blue reward
- 방향: 0에 가까울수록 우수

## 결과

| Red | Blue | Reward |
|---|---|---:|
| 기본 FSM | Sleep | −6164.0 ± 677.5 |
| 기본 FSM | Reactive | −6396.0 ± 554.2 |
| 기본 FSM | LayerChain | **−2340.0 ± 402.9** |
| 체인형 FSM | Sleep | −5667.3 ± 208.3 |
| 체인형 FSM | Reactive | −5206.3 ± 630.6 |
| 체인형 FSM | LayerChain | **−3340.3 ± 290.9** |

LayerChain은 기본 FSM에서 Sleep 대비 패널티를 62.0%, Reactive 대비 63.4% 줄였다. 체인형 FSM에서는 각각 41.1%, 35.8% 줄였다.

## 행동 변화

기본 FSM 3에피소드에서 LayerChain은 Restore를 200회 수행했고 Red Impact는 Sleep 1084회에서 678회로 감소했다. 체인형 FSM은 Sleep 조건에서 기본 FSM보다 패널티가 약 8% 작아 더 강한 공격기로 보기는 어렵다. 공격 단계 분포가 다른 일반화 조건으로만 사용한다.

## 검증

- 단위 테스트 4개 통과
- 공식 CAGE 평가 로더 통과
- 공식 평가 2에피소드 smoke reward: −3068.0 ± 693.0
- 코드 내 일반 주석 없음

## 다음 실험

- 조건별 30개 paired seed
- 계층 추적, 체인 링크, 8비트 메시지 각각의 ablation
- CAGE 일반화 변형 5종
- Invalid action과 서비스 가용성 보조 지표
