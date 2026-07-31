# 논문 작업

- `paper.md`: 형식 중립 한국어 본문 초안
- `paper-en.md`: 익명 영문 학술 원고
- `main.tex`: 익명 Springer LNCS 원고
- `llncs.cls`, `splncs04.bst`: Springer 공식 proceedings 템플릿
- `references.bib`: 공식 논문·코드 참고문헌
- `artifacts.json`: 벤치마크 commit과 핵심 결과 파일 SHA-256
- `claims.md`: 허용·기각·금지 주장과 원시 근거
- `check.py`: 본문 수치·방법론 상수·원시 결과·파일 해시의 일치 검사
- `venue.md`: WISA 2026 형식과 현재 접수 상태 점검

```bash
python paper/check.py
```

```powershell
powershell -ExecutionPolicy Bypass -File paper/build.ps1
```

현재 PDF는 익명 심사용 저자·소속 placeholder를 사용하며 참고문헌을 포함해 12쪽이다. 최종 PDF는 `output/pdf/paper.pdf`에 둔다.
