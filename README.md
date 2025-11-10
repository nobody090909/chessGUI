# Chess Proto

## 디렉터리 개요
```
chess-proto/
├─ README.md
├─ LICENSE
├─ requirements.txt                # 런타임 의존성 선언(버전 고정은 별도 코드 저장소에서 관리)
├─ .gitignore
├─ .env.example
├─ configs/
│  ├─ config.example.json          # AI_URL, API_KEY 등 예시
│  └─ config.json                  # 실제 설정(개인 토큰/엔드포인트) — 커밋 제외 권장
├─ assets/
│  ├─ svg/
│  │  └─ merida/                   # wP.svg … bK.svg (원본; 라이선스 확인 필수)
│  ├─ png/
│  │  └─ 72/                       # 변환된 PNG 세트(보드 칸 크기 72px 기준)
│  └─ themes/
│     ├─ classic.json
│     └─ dark.json
├─ docs/
├─ pgn/.gitkeep
├─ logs/.gitkeep
└─ .github/workflows/ci.yml        # 문서·스펙 정합성 체크(가벼운 CI)
```

## 설정
`configs/config.json`(또는 `.env`)에 **AI 서버 URL/토큰**을 넣어 GUI가 원격 AI를 호출하도록 합니다.
- `AI_URL`: 예) `https://ai.example.com`
- `API_KEY`: Bearer 토큰(없으면 빈 문자열 허용)
- `THINK_MS`: AI 탐색 시간 제한(ms)
- `TIMEOUT`: HTTP 요청 타임아웃(초)

> 코드 저장소에서 이 파일을 읽어 `RemoteAIClient` 초기화에 사용합니다.

## 에셋 파이프라인
- 원본 SVG 12개(`wP, wN, …, bK`)를 `assets/svg/merida/`에 배치
- 빌드 단계에서 **보드 칸 크기(SQ_SIZE)**에 맞춰 PNG로 변환 → `assets/png/<SQ_SIZE>/`
- GUI는 `SQ_SIZE`와 동일 해상도의 PNG를 로드하여 렌더링

## 빠른 체크리스트
- [ ] `configs/config.json`에 AI_URL/API_KEY 채우기
- [ ] `assets/svg/merida/`에 SVG 12개 배치
- [ ] PNG 변환 파이프라인 실행 (별도 코드 저장소의 스크립트 사용)
- [ ] GUI 코드에서 `SQ_SIZE`와 PNG 경로 일치 여부 확인
