
# Flask Scaffold (4 Services)

## 환경 설정

### 1. API 키 설정
```bash
# env.example 파일을 .env로 복사
cp env.example .env

# .env 파일을 편집하여 실제 API 키 입력
# - KAKAO_REST_API_KEY: 카카오 REST API 키
# - KAKAO_JAVASCRIPT_KEY: 카카오 JavaScript 키  
# - GOOGLE_PLACES_API_KEY: Google Places API 키
# - OPENWEATHER_API_KEY: OpenWeather API 키 (선택사항)
```

### 2. 설치 및 실행
```bash
python3 -m venv .venv && source .venv/scripts/activate
pip install -r requirements.txt
python app.py  # first run will 404 until DB exists
# init DB
flask --app app init-db
# seed (optional)
python seed.py
# run
python app.py
```

## 보안 주의사항
- **절대 API 키를 코드에 하드코딩하지 마세요**
- `.env` 파일은 `.gitignore`에 포함되어 있어 Git에 커밋되지 않습니다
- `env.example` 파일을 참고하여 필요한 환경변수를 설정하세요
Open http://localhost:8000/
- Hub → 공지/예약/캘린더/리포트현황
- 공지: 데모용 `/notice/new` 폼으로 수동 등록 가능
- 예약: 간단한 폼으로 테스트 (자원 ID는 1부터)
- 캘린더: My/Company 탭에서 간단 등록
- 리포트: `/report/inbound`에 JSON POST 시 유입
- 관리자용 모니터링 대시보드
