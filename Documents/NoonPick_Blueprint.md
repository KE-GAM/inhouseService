# NoonPick : 정오의 선택 — 점심 추천 서비스 Blueprint
_버전: 1.0 · 생성일: 2025-09-22 11:46:46_

---

## 1) 서비스 개요
**NoonPick**은 회사 오피스 반경(100/200/300/500m) 내에서 점심 식당을 추천하는 사내용 웹 서비스입니다.  
- **위치**: 사용자의 실시간 위치를 받지 않고, **오피스 고정 위치(Seoul/Daejeon)** 중 선택
- **데이터 소스**: **카카오 Local API**(장소 검색/카테고리/좌표/거리/`place_url`), **OpenWeather API**(선택적 날씨 가중)
- **UI 핵심**: 필터(오피스/반경/카테고리, 날씨 on/off) → **추천해줘!** → 지도 + 카드(썸네일/제목/설명/상세보기)  
- **상세정보**: 법·정책 준수를 위해 **카카오 `place_url` 딥링크**를 사용. 추가로 서버는 허용 범위 내에서 **Open Graph 메타(og:title/og:description/og:image)**만 파싱하여 카드에 미리보기 표시

---

## 2) 사용자 시나리오(Workflow)
1. 포털 사이드바에서 **NoonPick** 클릭
2. 점심 추천 페이지에서 필터 설정
   - 오피스: **Seoul**(기본) / Daejeon (드롭다운)
   - 반경: **100 / 200 / 300 / 500m** (라디오)
   - 카테고리: 한식/중식/일식/양식/고기/국·탕·찌개/면/밥/카페 등 **다중 선택 가능(미선택 허용)**
   - 날씨 영향: **On/Off** 토글
3. **추천해줘!** 클릭 → 로딩 후 지도 + 카드 표시
4. 카드 구성
   - 썸네일/제목/간략 설명(OG 메타) + 거리/대분류 배지/주소
   - **가게 상세보기(카카오)** 버튼(새 탭, `place_url`)
   - 하단: **선택**(방문 기록 저장) / **다시 돌리기**(같은 조건, 제외집합 추가)
5. 사용자가 마음에 들지 않으면 **다시 돌리기**로 반복

---

## 3) 요구 사항 요약
- **오피스 고정 위치**: 사용자 위치 수집 없음
  - Seoul: _서울특별시 강남구 테헤란로 521, 파르나스 타워 16층_
  - Daejeon: _대전광역시 유성구 문지로 272-16 502호_
  - 최초 1회 **카카오 지오코딩**으로 lat/lng 확보 → DB `offices`에 캐싱
- **카카오 Local API**만 사용(네이버 제외). 상세는 `place_url` 딥링크로 해결
- **OG 메타 파싱**(허용 범위): 카드 미리보기에만 사용(원문 HTML/이미지의 저장·재배포 금지)
- **추천 로직**: MVP에서는 **대분류 매핑 + 거리 감쇠**만 사용(가격/세부 취향 가중치 제외)
- **재뽑기**: 같은 필터, 제외집합(excluded_ids) 적용
- **방문 기록**: 선택 시 누적 → 재방문 페널티 등 향후 확장 근거

---

## 4) 시스템 구조
### 4.1 아키텍처(논리)
- **Frontend**: React(또는 기존 템플릿) + Kakao Map JS SDK
- **Backend**: Flask + SQLite(개발)/PostgreSQL(운영 선택), Requests + BeautifulSoup(OG 메타)
- **External**: Kakao Local API, OpenWeather API

### 4.2 데이터 흐름
1. 관리/배치: 오피스 좌표 + 반경 + 키워드로 카카오 Local 검색 → `places` **upsert 캐시**
2. 사용자가 필터 선택 → 백엔드 `/api/lunch/reco` 호출
3. DB에서 후보 조회 → **점수 계산** → 상위 N 가중 랜덤 → 1곳 + 대안 2곳 JSON 응답
4. 서버는 `place_url`의 **OG 메타**를 읽어 카드에 첨부(캐시)
5. 사용자가 **선택** → `/api/lunch/visit` 로깅

---

## 5) 데이터 모델
```sql
-- offices: 오피스 좌표 고정(지오코딩 1회 후 저장)
CREATE TABLE IF NOT EXISTS offices (
  id INTEGER PRIMARY KEY,
  code TEXT UNIQUE,      -- 'seoul' | 'daejeon'
  name TEXT,
  address TEXT,
  lat REAL,
  lng REAL,
  is_default INTEGER DEFAULT 0
);

-- places: 카카오 Local 캐시(반경 검색 결과)
CREATE TABLE IF NOT EXISTS places (
  id INTEGER PRIMARY KEY,
  provider TEXT,            -- 'kakao'
  provider_key TEXT,        -- place_url 해시 등 유니크 키
  name TEXT,
  lat REAL, lng REAL,
  raw_category TEXT,        -- kakao category_name
  big_categories TEXT,      -- JSON 배열 ["KOREAN","SOUP"]
  phone TEXT,
  address TEXT,
  road_address TEXT,
  distance_m INTEGER,
  kakao_place_url TEXT,
  last_seen_at DATETIME,
  UNIQUE(provider, provider_key)
);

-- 방문 기록(선택 버튼 누를 때)
CREATE TABLE IF NOT EXISTS visits (
  id INTEGER PRIMARY KEY,
  user_id INTEGER,
  place_id INTEGER,
  visited_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- OG 메타 캐시(썸네일/제목/설명)
CREATE TABLE IF NOT EXISTS og_cache (
  url TEXT PRIMARY KEY,
  title TEXT,
  description TEXT,
  image TEXT,
  cached_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 5.1 대분류 매핑(카카오 category_name → 우리 분류)
```python
CATEGORY_MAP = [
  ("KOREAN",   ["한식","국밥","찌개","백반","분식","비빔밥","국수","냉면"]),
  ("JAPANESE", ["일식","스시","초밥","라멘","우동","돈카츠","소바","덮밥"]),
  ("CHINESE",  ["중식","짜장","짬뽕","탕수육","마라"]),
  ("WESTERN",  ["양식","파스타","피자","버거","스테이크","브런치"]),
  ("MEAT",     ["고기","구이","삼겹","갈비","정육","솥뚜껑"]),
  ("NOODLE",   ["국수","라면","라멘","우동","소바","짜장","짬뽕"]),
  ("RICE",     ["덮밥","비빔밥","백반","카레","김밥","국밥"]),
  ("SOUP",     ["국","탕","찌개","전골"]),
  ("CAFE",     ["카페","디저트","빵","베이커리"])
]
```

---

## 6) API 설계(핵심)
### 6.1 추천
`GET /api/lunch/reco?office=seoul&radius=300&cats=KOREAN,JAPANESE&exclude=12,45`
- **입력**
  - `office`: `seoul|daejeon` (기본: seoul)
  - `radius`: `100|200|300|500` (기본: 300)
  - `cats`: 대분류 CSV (미전달 시 전체 허용)
  - `exclude`: 직전 추천에서 본 place id들(재뽑기 시)
- **출력**
```json
{
  "primary": {
    "id": 123,
    "name": "불타는 김치찌개",
    "distance_m": 320,
    "big_categories": ["KOREAN","SOUP"],
    "kakao_place_url": "https://place.map.kakao.com/...",
    "address": "서울 강남구 ...",
    "og": { "title": "불타는 김치찌개", "description": "오전 11시~", "image": "http://..." }
  },
  "alternatives": [{ "...": "..." }, { "...": "..." }],
  "excluded_suggestion": [123, 456, 789]
}
```

### 6.2 방문 기록
`POST /api/lunch/visit`  
```json
{ "place_id": 123, "user_id": 1 }
```

### 6.3 인제스트(관리/배치)
`POST /internal/lunch/ingest`  
```json
{ "office_code": "seoul", "radius": 500, "keywords": ["맛집","한식","스시","파스타","국밥","고기","카페"] }
```

---

## 7) 추천 로직(단순 가중치 + 가중 랜덤)
```python
def distance_score(d_m: int, r_m: int) -> float:
    if d_m >= r_m: return 0.4
    lo, hi = 0.4, 1.0
    return lo + (hi - lo) * (1.0 - d_m / max(1, r_m))

def category_match(place_cats, selected):
    if not selected: return 0.5  # 미선택이면 중립
    return 1.0 if set(place_cats) & set(selected) else 0.0

def score(place, ctx):
    cat = category_match(place.big_categories, ctx.categories)
    dist = distance_score(place.distance_m, ctx.radius)
    return 0.6 * cat + 0.4 * dist

# 상위 N(예: 10) → softmax(τ≈0.08)로 확률 샘플링 → 1곳 + 대안 2곳
```

---

## 8) 카카오 Local 인제스터 개요
- 키워드(예: 맛집/한식/중식/일식/양식/국밥/스시/파스타/피자/고기/카페 등)로 다중 검색
- 응답의 `place_name/category_name/address_name/road_address_name/phone/place_url/distance` 수집
- `place_url` 해시를 `provider_key`로 사용 → `places` **upsert**
- `category_name` → **대분류 매핑** 후 `big_categories` 저장(JSON 배열)

---

## 9) OG 메타 파싱(허용 범위)
- 대상: **카카오 place_url** (공개 페이지)
- 내용: `og:title`, `og:description`, `og:image` **만** 추출/캐시
- 보안/정책: 원문 HTML/이미지의 **대량 저장·재배포 금지**. iFrame 임베드 대신 **새 탭 딥링크**

---

## 10) 프론트 설계(요약)
- **필터 바**
  - Office(Seoul/Daejeon), 반경(100/200/300/500), 카테고리(다중), 날씨 토글(후속)
- **결과 뷰**
  - **카카오 지도**(JS SDK): primary 마커 + 대안 2개 옅은 마커
  - **카드**: OG 썸네일/제목/설명 + 주소/거리/배지 + **가게 상세보기(카카오)**
  - 버튼: **선택**(visit) / **다시 돌리기**(exclude 적용)

---

## 11) 환경 변수(.env)
- `DATABASE=inhouse.sqlite3`
- `KAKAO_REST_API_KEY=...` (서버에서만 사용, 프록시 호출)
- `OPENWEATHER_API_KEY=...` (날씨 가중치가 필요해질 때)
- `JSON_AS_ASCII=false`, `TEMPLATES_AUTO_RELOAD=true` 등

---

## 12) 배포/운영 포인트
- 인제스트는 업무 시작 전/점심 전(예: 10:30/11:00) 2회 실행 추천
- 카카오 API 쿼터 고려 → 캐시 먼저 조회, 필요 시만 동기화
- OG 메타는 캐시 만료 정책(예: 7일)로 재갱신
- 키 보호: 모든 외부 API는 **서버에서 호출**

---

## 13) 향후 로드맵
- 개인/전체 **피드백(별점/태그)** 수집 → `LocalQuality` 가중 추가
- **재방문 페널티**(최근 7일 중복 방문 감소) 반영

---

## 14) 완료 정의(DoD, MVP)
- [ ] 오피스 드롭다운(Seoul 기본), 반경/카테고리/날씨 토글 필터 노출
- [ ] `/internal/lunch/ingest`로 places 캐시 구축(Seoul 500m)
- [ ] `/api/lunch/reco` 구현(대분류+거리 점수 → 가중 랜덤)
- [ ] 지도 + 카드(OG 썸네일/제목/설명 + 상세보기 버튼)
- [ ] 방문 기록 `/api/lunch/visit` 저장
- [ ] “다시 돌리기”로 같은 조건 재추천(제외집합 반영)

---

**NoonPick : 정오의 선택** — *반경으로 고르는 사내 점심 추천*  
문의/개발: Inhouse Platform Team · 2025
