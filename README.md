
# Flask Scaffold (4 Services)

## Quickstart
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
Open http://localhost:8000/
- Hub → 공지/예약/캘린더/리포트현황
- 공지: 데모용 `/notice/new` 폼으로 수동 등록 가능
- 예약: 간단한 폼으로 테스트 (자원 ID는 1부터)
- 캘린더: My/Company 탭에서 간단 등록
- 리포트: `/report/inbound`에 JSON POST 시 유입
