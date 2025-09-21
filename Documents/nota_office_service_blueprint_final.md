# 📌 Nota 오피스 공간 관리 서비스 Blueprint (개발 가이드 문서) — Final

## 0. 문서 목적
Cursor가 이 문서만으로 **프런트(React/TS), 백엔드(Flask), DB 스키마**를 구현할 수 있도록
사양·API·UX 상태·운영 룰을 구체화했습니다. *이름(개인정보) 노출은 하지 않습니다.*

---

## 1. 서비스 개요
- **목적**: Nota 오피스 내 다양한 공간(회의실, 포커스룸, 라운지 등)을 효율적으로 관리
- **핵심 기능**
  1) 회의실 예약  
  2) 포커스룸 현황판 + 즉시 점유(찜)  
  3) React 기반 **SVG 인터랙티브 맵** 시각화

---

## 2. 공간 구분
- **회의실**: 예약 필요 (정식 예약제)
- **포커스룸**: 현황판 + 찜 (실시간 점유 관리)

---

## 3. 사용자 흐름 (User Flow)

### 3.1 회의실
1) 현황판/SVG에서 회의실 선택  
   - **총 10개**: Disagree&Commit, Ownership, Customer-Centric, Trust, Leadership Principle, 회의실1~5  
2) 선택 시 **ReservationPopover** 표시 → 시작/종료 시간(30분 단위 슬롯) 선택 → 예약 생성  
3) 예약 시간에 맞춰 입실/퇴실  
4) **상태 표시 규칙**
   - 현재 시간 포함 예약이 있으면: **사용중**  
   - 현재 시간 미포함, *30분 이내 시작* 예약 존재: **예약됨**  
   - 그 외: **사용 가능**

### 3.2 포커스룸
1) 현황판/SVG에서 빈자리 확인  
2) **“찜(사용 시작)”** 클릭 → 즉시 **사용 중**으로 변경  
3) 기본 타이머 **2시간** 부여  
   - **만료 10분 전** 연장 여부 Alert.  
   - **30분 단위** 연장 가능
4) 퇴실 시 **체크아웃** → 빈자리 전환  
5) 자동 해제
   - 타이머 만료 시 자동 **사용 종료**

> 이름은 표시하지 않으며, 맵/현황판에는 **상태 + 종료/시작 시각**만 노출합니다.

---

## 4. 프론트엔드 (React + TypeScript)

### 4.1 기술 스택
- React (TS), Vite
- TailwindCSS
- 상태관리: React Query (서버 상태 동기화)
- SVG: 오피스 평면도를 SVG로, 공간별 `<path>`/`<rect>`에 **roomId** 데이터 속성 매핑

### 4.2 컴포넌트
- `<NotaOfficeSituation />`
  - 전체 공간 리스트 & SVG 맵 동기화, 상태 텍스트: **사용 가능 / 예약됨 / 사용중**
  - 라벨 포맷 예:  
    - 사용중: `사용중 · ~ 15:30`  
    - 예약됨: `예약됨 · 16:00 시작`  
    - 사용 가능: `사용 가능`
- `<ReservationPopover />` (회의실)
  - 날짜+시간 슬롯(30분 단위), 중복 방지 검증, 생성/취소
- `<FocusRoomPopover />` (포커스룸)
  - 찜(시작), 연장(+30m), 체크아웃
- `<SvgOfficeMap />`
  - `roomsStatus`를 받아 색상 채우기/라벨 텍스트 렌더
  - 방 id ↔ SVG 요소 id를 **config 맵**으로 연결

### 4.3 상태 색상(권장)
- AVAILABLE = green-500
- RESERVED = amber-500
- OCCUPIED = rose-500

---

## 5. 백엔드 (Flask)

### 5.1 DB 스키마 (PostgreSQL 예시)

```sql
CREATE TABLE rooms (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('MEETING','FOCUS','LOUNGE')),
  capacity INT
);

CREATE TABLE reservations (
  id SERIAL PRIMARY KEY,
  room_id INT NOT NULL REFERENCES rooms(id),
  start_time TIMESTAMPTZ NOT NULL,
  end_time   TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE'
);
/* 겹침 탐지를 위한 인덱스 */
CREATE INDEX idx_resv_room_time ON reservations(room_id, start_time, end_time);

CREATE TABLE occupancies (
  id SERIAL PRIMARY KEY,
  room_id INT NOT NULL REFERENCES rooms(id),
  start_time TIMESTAMPTZ NOT NULL,
  end_time   TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX idx_occ_active ON occupancies(room_id, status);
```

> 개인정보 표시는 하지 않으므로 사용자 FK는 제외. 향후 필요 시 `user_id` 컬럼 추가 가능.

### 5.2 REST API

#### 회의실
- `POST /rooms/{id}/reservations`
  - body: `{ "start": "...", "end": "..." }`
  - 409: 시간 겹침
- `GET /rooms/{id}/reservations?from=...&to=...`

#### 포커스룸
- `POST /focus/{id}/claim` → 즉시 점유 시작(타이머 2h)
- `POST /focus/{id}/extend` → 30m 연장
- `POST /focus/{id}/release` → 사용 종료

#### 현황 조회
- `GET /rooms/status`
  - 응답 예:
```json
[
  {
    "roomId": 1,
    "name": "Ownership",
    "type": "MEETING",
    "status": "OCCUPIED",
    "current": { "until": "2025-09-21T15:30:00+09:00" },
    "next": { "start": "2025-09-21T16:00:00+09:00" }
  },
  {
    "roomId": 7,
    "name": "회의실2",
    "type": "FOCUS",
    "status": "AVAILABLE"
  }
]
```

### 5.3 상태 판정 로직 (요약)
- MEETING
  - `exists reservation where start <= now < end` → **OCCUPIED**
  - else `exists reservation where 0 <= start-now <= 30m` → **RESERVED**
  - else **AVAILABLE**
- FOCUS
  - `exists active occupancy` → **OCCUPIED**
  - else **AVAILABLE**

### 5.4 동시성·무결성
- 예약 생성은 트랜잭션으로 **시간 겹침 재검증**
- 포커스룸 `claim`은 `room_id` 당 **active unique** 보장 (앱 레벨 락 or unique partial index)

---

## 6. 현황판 + 찜 구현 원칙
- **찜=사용 시작** (즉시 점유)
- 기본 **2시간** 타이머, **만료 10분 전 알림**, **+30분 연장**
- **무활동 5분** 또는 타이머 만료 시 자동 종료(옵션)
- 동시 클릭 선착순 처리, 실패 시 “이미 사용중” 메시지

---

## 7. 관리자 대시보드
- 통계: 일별 예약/찜 횟수, 평균 점유시간, 피크타임
- 운영 룰 변경: 기본 타이머/연장 단위, 예약 슬롯 단위, 예약 가능 시간대
- 수동 해제(운영자): 이례 상황 처리

---

## 8. SVG 인터랙티브 맵 연결 규칙
- `rooms` 시드 데이터(10개 회의실 + N개 포커스룸)와 SVG 요소 `id`를 매핑한 **config JSON** 관리
```json
{
  "1": { "svgId": "room-ownership", "label": [320, 140] },
  "2": { "svgId": "room-dnc", "label": [520, 140] }
}
```
- 프런트는 `/rooms/status` 결과를 `roomId→status`로 변환해 SVG 채우기/라벨 텍스트 갱신

---

## 9. 시간·타임존·i18n
- 서버·DB: **UTC 저장**, 응답은 ISO8601(+09:00)로 변환
- 프런트: 클라이언트 타임존 렌더
- i18n 키(예): `status.available`, `status.reserved`, `status.occupied`

---

## 10. 에러/엣지 케이스
- 예약 겹침: 409 CONFLICT
- 잘못된 시간(종료≤시작): 400
- 포커스룸 `claim` 시 이미 사용중: 409
- 네트워크 오류 시 optimistic UI 롤백

---

## 11. 시드 데이터 (회의실 10개)
```sql
INSERT INTO rooms (name, type, capacity) VALUES
('Disagree&Commit','MEETING',10),
('Ownership','MEETING',10),
('Customer-Centric','MEETING',10),
('Trust','MEETING',10),
('Leadership Principle','MEETING',10),
('회의실1','MEETING',8),
('회의실2','MEETING',8),
('회의실3','MEETING',8),
('회의실4','MEETING',8),
('회의실5','MEETING',8);
```

---

## 12. 보안·프라이버시
- 현황판에는 **사용자 이름 비노출**
- 내부망/SSO 뒤 배치
- 감사 로그(관리자 수동 해제 등)만 서버 보관

---

## 13. 테스트 체크리스트
- 예약 겹침/경계(정각, 30분 슬롯) 케이스
- 포커스룸 동시 claim
- 타이머 만료/연장/자동 종료
- 상태 전이: AVAILABLE↔RESERVED↔OCCUPIED
- SVG 렌더 일관성(색상/라벨)

---

## 14. 개발 단계 로드맵
**MVP**: 예약/찜/현황 조회 + SVG 맵 채색/라벨  
**2차**: 알림(만료 10분 전), 연장 API, 관리자 패널(기본 타이머 변경)  
**3차**: 센서 연동(회의실 자동), 혼잡도, 통계 시각화