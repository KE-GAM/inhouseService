# NoonPick : 정오의 선택 — 점심 추천 서비스 Blueprint
_버전: 2.0 · 생성일: 2025-09-22 11:46:46 · 업데이트: 2025-09-29_

---

## 1) 서비스 개요
**NoonPick**은 회사 오피스 반경(100/200/300/500m) 내에서 점심 식당을 추천하는 사내용 웹 서비스입니다.  
- **위치**: 사용자의 실시간 위치를 받지 않고, **오피스 고정 위치(Seoul/Daejeon)** 중 선택
- **데이터 소스**: **Google Places API**(장소 검색/카테고리/좌표/거리/별점/`place_id`), **OpenWeather API**(선택적 날씨 가중)
- **UI 핵심**: 필터(오피스/반경/카테고리, 날씨 on/off) → **추천해줘!** → 지도 + 카드(썸네일/제목/설명/상세보기)  
- **상세정보**: **Google Maps `place_id` 딥링크**를 사용하여 정확한 가게 정보 제공. **Google API 별점 정보**를 활용한 품질 필터링(3점 미만 제외)

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
   - 썸네일/제목/간략 설명 + 거리/대분류 배지/주소/별점
   - **가게 상세보기(Google Maps)** 버튼(새 탭, `place_id` 기반 링크)
   - 하단: **선택**(방문 기록 저장) / **다시 돌리기**(같은 조건, 제외집합 추가)
5. 사용자가 마음에 들지 않으면 **다시 돌리기**로 반복

---

## 3) 요구 사항 요약
- **오피스 고정 위치**: 사용자 위치 수집 없음
  - Seoul: _서울특별시 강남구 테헤란로 521, 파르나스 타워 16층_
  - Daejeon: _대전광역시 유성구 문지로 272-16 502호_
  - 최초 1회 **Google Geocoding API**로 lat/lng 확보 → DB `offices`에 캐싱
- **Google Places API**만 사용. 상세는 `place_id` 기반 Google Maps 딥링크로 해결
- **실시간 검색**: 매번 Google Places API 호출로 최신 정보 보장
- **품질 필터링**: Google API 별점 3점 미만 자동 제외
- **추천 로직**: **대분류 매핑 + 거리 감쇠 + 별점 가중치** 사용
- **재뽑기**: 같은 필터, 제외집합(excluded_ids) 적용
- **방문 기록**: 선택 시 누적 → 재방문 페널티 등 향후 확장 근거

---

## 4) 시스템 구조
### 4.1 아키텍처(논리)
- **Frontend**: Flask 템플릿 + Google Maps JS API
- **Backend**: Flask + SQLite(개발)/PostgreSQL(운영 선택), Requests + concurrent.futures(병렬 처리)
- **External**: Google Places API, Google Maps API, OpenWeather API

### 4.2 데이터 흐름
1. 사용자가 필터 선택 → 백엔드 `/api/lunch/reco` 호출
2. **실시간 Google Places API** 검색 (카테고리 + 키워드)
3. **별점 필터링** (3점 미만 제외) → **점수 계산** → 상위 N 가중 랜덤 → 1곳 + 대안 2곳 JSON 응답
4. **병렬 이미지 처리** (Google Places Photos + 카테고리 기반 이미지)
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

-- places: Google Places 캐시(실시간 검색 결과)
CREATE TABLE IF NOT EXISTS places (
  id INTEGER PRIMARY KEY,
  provider TEXT,            -- 'google'
  provider_key TEXT,        -- place_id
  name TEXT,
  lat REAL, lng REAL,
  raw_category TEXT,        -- Google types[0]
  big_categories TEXT,      -- JSON 배열 ["KOREAN","SOUP"]
  phone TEXT,
  address TEXT,
  road_address TEXT,
  distance_m INTEGER,
  google_place_url TEXT,    -- place_id 기반 Google Maps 링크
  rating REAL,              -- Google API 별점
  place_id TEXT,            -- Google place_id
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

-- 이미지 캐시(Google Places Photos + 카테고리 기반)
CREATE TABLE IF NOT EXISTS image_cache (
  place_id TEXT PRIMARY KEY,
  photo_url TEXT,
  cached_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 5.1 대분류 매핑(Google Places types → 우리 분류)
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
    "id": "google_ChIJ...",
    "name": "불타는 김치찌개",
    "distance_m": 320,
    "big_categories": ["KOREAN","SOUP"],
    "google_place_url": "https://www.google.com/maps/place/?q=place_id:ChIJ...",
    "address": "서울 강남구 ...",
    "rating": 4.2,
    "photo_url": "https://maps.googleapis.com/maps/api/place/photo?...",
    "og": { "title": "불타는 김치찌개", "description": "서울 강남구 ... - restaurant", "image": "http://..." }
  },
  "alternatives": [{ "...": "..." }, { "...": "..." }],
  "excluded_suggestion": ["google_ChIJ...", "google_ChIJ...", "google_ChIJ..."]
}
```

### 6.2 방문 기록
`POST /api/lunch/visit`  
```json
{ "place_id": 123, "user_id": 1 }
```

### 6.3 인제스트(관리/배치) - 제거됨
~~`POST /internal/lunch/ingest`~~  
**실시간 검색으로 변경**: 더 이상 배치 인제스트가 필요하지 않음. 매 요청마다 Google Places API를 직접 호출하여 최신 정보를 보장합니다.

---

## 7) 추천 로직(가중치 + 별점 필터링 + 가중 랜덤)
```python
def distance_score(d_m: int, r_m: int) -> float:
    if d_m >= r_m: return 0.4
    lo, hi = 0.4, 1.0
    return lo + (hi - lo) * (1.0 - d_m / max(1, r_m))

def category_match(place_cats, selected):
    if not selected: return 0.5  # 미선택이면 중립
    return 1.0 if set(place_cats) & set(selected) else 0.0

def rating_score(rating: float) -> float:
    if rating == 0: return 0.5  # 별점 없으면 중립
    return min(1.0, rating / 5.0)  # 5점 만점 기준 정규화

def score(place, ctx):
    cat = category_match(place.big_categories, ctx.categories)
    dist = distance_score(place.distance_m, ctx.radius)
    rating = rating_score(place.rating)
    return 0.4 * cat + 0.3 * dist + 0.3 * rating

# 별점 3점 미만 필터링 → 상위 N(예: 10) → softmax(τ≈0.08)로 확률 샘플링 → 1곳 + 대안 2곳
```

---

## 8) Google Places 실시간 검색 개요
- **카테고리 검색**: `type=restaurant`로 음식점 전체 검색
- **키워드 검색**: 선택된 카테고리별 키워드로 추가 검색 (최대 3개)
- 응답의 `name/types/vicinity/geometry/rating/place_id` 수집
- `place_id`를 `provider_key`로 사용 → 중복 제거
- `types[0]` → **대분류 매핑** 후 `big_categories` 저장(JSON 배열)
- **별점 필터링**: 3점 미만 자동 제외

---

## 9) 이미지 처리(최적화)
- **Google Places Photos**: 상위 10개 장소에 대해 실제 가게 사진 조회
- **카테고리 기반 이미지**: 나머지 장소는 Unsplash 고품질 이미지 사용
- **병렬 처리**: `ThreadPoolExecutor`로 최대 3개 스레드 동시 처리
- **캐싱**: 이미지 URL을 `image_cache` 테이블에 저장하여 재사용

---

## 10) 프론트 설계(요약)
- **필터 바**
  - Office(Seoul/Daejeon), 반경(100/200/300/500), 카테고리(다중), 날씨 토글(후속)
- **결과 뷰**
  - **Google Maps**(JS API): primary 마커(빨간색) + 대안 2개 마커(파란색)
  - **카드**: 썸네일/제목/설명 + 주소/거리/배지/별점 + **가게 상세보기(Google Maps)**
  - 버튼: **선택**(visit) / **다시 돌리기**(exclude 적용)

---

## 11) 환경 변수(.env)
- `DATABASE=inhouse.sqlite3`
- `GOOGLE_PLACES_API_KEY=...` (서버에서만 사용, 프록시 호출)
- `OPENWEATHER_API_KEY=...` (날씨 가중치가 필요해질 때)
- `JSON_AS_ASCII=false`, `TEMPLATES_AUTO_RELOAD=true` 등

---

## 12) 배포/운영 포인트
- **실시간 검색**: 매 요청마다 Google Places API 호출로 최신 정보 보장
- Google API 쿼터 고려 → 사내용 서비스로 무료 한도 내 충분히 운용 가능
- 이미지 캐시는 만료 정책(예: 7일)로 재갱신
- 키 보호: 모든 외부 API는 **서버에서 호출**
- **성능 최적화**: 병렬 처리로 응답 시간 단축 (2-3초)

---

## 13) 향후 로드맵
- 개인/전체 **피드백(별점/태그)** 수집 → `LocalQuality` 가중 추가
- **재방문 페널티**(최근 7일 중복 방문 감소) 반영

---

## 14) 완료 정의(DoD, MVP)
- [x] 오피스 드롭다운(Seoul 기본), 반경/카테고리/날씨 토글 필터 노출
- [x] **실시간 Google Places API** 검색 구현
- [x] `/api/lunch/reco` 구현(대분류+거리+별점 점수 → 가중 랜덤)
- [x] **Google Maps** + 카드(썸네일/제목/설명/별점 + 상세보기 버튼)
- [x] 방문 기록 `/api/lunch/visit` 저장
- [x] "다시 돌리기"로 같은 조건 재추천(제외집합 반영)
- [x] **별점 필터링** (3점 미만 제외)
- [x] **병렬 이미지 처리** (Google Places Photos + 카테고리 기반)
