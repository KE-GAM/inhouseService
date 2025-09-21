# Report-It 서비스 Blueprint (v1.1)

> **목적**: 사내 **시설/IT 이슈**만을 신속히 접수·배정·조치·공개 조회하는 경량 운영 시스템. QR→신고→슬랙 알림→운영대시보드 등록까지 **Google Forms + Apps Script + Flask API** 조합으로 MVP를 완성하고, 점진적으로 자체 폼/스토리지/권한을 고도화한다.

---

## 1. 스코프 / 비스코프
- **스코프**: 사내 시설/장비/공용 IT(프린터, 프로젝터, 공유 AP, 회의실 설비 등) 고장·파손·성능저하·기타 신고.
- **비스코프**: HR/보안/제안/구매요청 등은 제외. 별도 시스템 대상.

---

## 2. 주요 페르소나 & 권한
- **임직원(Reporter)**: QR 촬영→신고, 전체 이슈 현황판 열람, 내가 신고한 건은 목록에 표시(✔️ 내 신고 뱃지).
- **시설 관리자(Facility Manager)**: 이슈 목록/검색·상세·상태변경(접수→조치 중→완료/불가), 조치 메모(코멘트), 병합.
- **Admin(개발자, 시스템 관리자)**: 서비스 유지보수 및 기능 개발 담당. 실제 운영에는 관여하지 않음. 하지만 서비스에 대한 모든 권한을 가지고 있음.

> **열람 정책**
> - 전사 임직원 누구나 전체 이슈 현황판 열람 가능.
> - Reporter는 자신의 접수 건에 "✔️내 신고" 표시를 통해 식별 가능.
> - 시설 관리자는 상태 변경과 코멘트 작성 권한을 가짐.

---

## 3. 상태 모델 & 색상
- `OPEN(접수)` = 흰색
- `IN_PROGRESS(조치 중)` = 노란색
- `DONE(조치 완료)` = 초록색
- `CANNOT_FIX(조치 불가)` = 빨간색

상태 전이: `OPEN → IN_PROGRESS → DONE|CANNOT_FIX` (필요 시 `REOPEN` 도입)

---

## 4. 엔드투엔드 플로우 (권장 v2)
1) **QR 스캔 → 장소 페이지** (예: `/place/{location_id}`)
   - 현재 진행 중 이슈 목록(제목+상태) / "새 이슈 신고" 버튼
2) **신고 버튼 → Google Form(미리채움)**
   - `location_id` 프리필
   - 필드: 장소 ID, 이슈 발생 시설/장(=assetName), 이슈 종류, 이슈 내용, (선택) 사진 업로드
3) **폼 제출 → Google Sheet** (응답 연결)
4) **Apps Script onFormSubmit**
   - **Slack 채널**에 Block Kit 알림
   - **Report-It 백엔드** `POST /api/issues`로 등록(중복시 병합 처리)
5) **Report-It 대시보드**
   - 목록(장소/접수일/이슈/종류/현재상태)
   - 아코디언 상세(설명, 첨부, 시설 관리자 코멘트, 상태 이력)
   - 시설 관리자만 쓰기/수정/삭제/코멘트 입력/코멘트 수정/코멘트 삭제

---

## 5. Google Form/Sheet 설계
### 5.1 폼 필드(단일 폼, 장소별 프리필)
- **장소 ID**(단답, 필수) — QR로 프리필 (예: `MEET-3A`)
- **이슈 발생 시설/장**(단답, 필수) — 예: 프로젝터, 프린터A
- **이슈 종류**(객관식, 필수) — 고장/파손/성능저하/기타
- **이슈 내용**(장문, 필수)
- **사진 업로드**(파일, 선택)

> **미리채움 링크**: 폼 편집 → "미리채움 링크 받기" → `entry.12345=MEET-3A` 식 파라미터를 QR별로 바꿔 부여

- 구글 폼 양식 및 미리채움 링크 생성 완료.

### 5.2 시트 컬럼(예시)
- (자동) **타임스탬프**
- 이메일 주소(자동 수집)
- 이슈 발생 장소(=장소 ID)
- 이슈 발생 시설/장(=assetName)
- 이슈 종류
- 이슈 내용
- 사진 업로드(있으면 다중 URL 또는 줄바꿈 텍스트)

- 구글 스프레드시트에 컬럼 입력 완료.

---

## 6. Apps Script (onFormSubmit) 개요
- **역할**: 폼 응답을 받아 **Slack 알림** + **Report-It API 등록** 수행
- **프로젝트 속성**(Script Properties):
  - `SLACK_WEBHOOK_URL`
  - `REPORTIT_API_URL` (예: `https://your-domain/api/issues`)
  - `REPORTIT_API_TOKEN` (백엔드와 공유하는 Bearer)
- **트리거**: From spreadsheet → On form submit → `onFormSubmit`

### 6.1 파싱 규칙
- 기본: `e.namedValues['질문 제목']` 사용(순서 영향 없음)
- 타임스탬프: `namedValues['타임스탬프']` → 실패 시 `e.values[0]` or `new Date()`
- 첨부: 셀 텍스트에서 URL 정규식으로 추출 (줄바꿈/쉼표 분리 대응)

### 6.2 Slack 알림(예시 Block)
- Header: "새 이슈 접수"
- Fields: 장소, 시설/장비, 종류, 접수시각, 신고자
- Section: 상세내용(최대 600자)
- (선택) 첨부 URL 목록

> **Slack 준비**: 워크스페이스 채널에 *Incoming Webhook* 설치 → Webhook URL을 Script Properties에 저장

- App script와 Slack 연결 완료.

---

## 7. 백엔드(API) 사양 (Flask, SQLite)
### 7.1 엔드포인트 요약
- **POST** `/api/issues` — 폼 응답 등록(또는 중복 병합)
- **GET** `/api/issues` — 전사 공개 목록/검색(상태/장소/기간 필터)
- **GET** `/api/issues/{id}` — 상세(첨부/시설 관리자 코멘트/이력 포함)
- **PATCH** `/api/issues/{id}/status` — 상태 변경(시설 관리자)
- **POST** `/api/issues/{id}/comments` — 시설 관리자 코멘트 추가
- **POST** `/api/issues/{id}/merge` — 중복 병합(시설 관리자)
- **GET** `/api/places/{location_id}/active` — 장소별 진행 중 이슈 요약

### 7.2 `POST /api/issues` (Apps Script 연동)
**Headers**: `Authorization: Bearer <REPORTIT_API_TOKEN>`

**Request (JSON)**
```json
{
  "location_id": "MEET-3A",
  "title": "프로젝터",             
  "type": "고장",                 
  "description": "전원 버튼 반응 없음",
  "attachments": ["https://drive.google.com/..."],
  "reporter_email": "user@company.com",
  "reported_at": "2025-09-22T12:34:56.000Z",
  "source": "google_form"
}
```

**Server Behavior**
- 필수값 확인(`location_id`, `title`, `type`)
- **경량 중복 방지**: 동일 장소 + 동일 제목 + 상태(OPEN/IN_PROGRESS) + 최근 24h 존재 시 → 신규 생성 대신 **병합**
  - 기존 건에 시설 관리자 코멘트 `[Auto-merge] 추가 접수: ...` 기록
  - 첨부 URL 추가
- 신규 생성 시 `status=OPEN` + 상태 이력 1건 기록

**Response**
- 신규: `201 { "id": 123 }`
- 병합: `200 { "merged_into": 123 }`

### 7.3 스키마 (SQLite 예시)
```sql
CREATE TABLE IF NOT EXISTS issues (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  location_id TEXT NOT NULL,
  title TEXT NOT NULL,
  type TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL,      -- 'OPEN'|'IN_PROGRESS'|'DONE'|'CANNOT_FIX'
  reported_at TEXT NOT NULL,
  reporter_email TEXT,
  source TEXT
);

CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  issue_id INTEGER NOT NULL,
  url TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(issue_id) REFERENCES issues(id)
);

CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  issue_id INTEGER NOT NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  author TEXT,               -- 시설 관리자 이름
  source TEXT,
  FOREIGN KEY(issue_id) REFERENCES issues(id)
);

CREATE TABLE IF NOT EXISTS status_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  issue_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  changed_at TEXT NOT NULL,
  actor TEXT,                -- 시설 관리자 이름
  FOREIGN KEY(issue_id) REFERENCES issues(id)
);
```

---

## 8. 운영 대시보드(UI/UX)
### 8.1 이슈 목록(기본표)
- 컬럼: **이슈 발생 장소 / 이슈 접수 일자 / 이슈 이름(=title) / 이슈 종류 / 현재 상태**
- 행 클릭 → **아코디언 상세**: 상세내용, 첨부, 시설 관리자 코멘트, 상태 이력
- 필터: 장소/상태/기간/종류, 검색: 키워드(title/description)

### 8.2 장소 페이지
- 장소는 총 5곳(Ownership, Trust, Focus-A, Lounge, Snack Bar)
- 진행 중 이슈 존재 여부 / 간략 요약 표시
- "+ 새 이슈 신고" 버튼 → Google Form(프리필)
- 각 장소별 google Form(프리필) 주소
Ownership: https://docs.google.com/forms/d/e/1FAIpQLScMwCRHstG7GBKmC7hSgbXWNe_xtPX4Jmuni_sHzTyUMFJRqw/viewform?usp=pp_url&entry.1116565432=Ownership
Trust: https://docs.google.com/forms/d/e/1FAIpQLScMwCRHstG7GBKmC7hSgbXWNe_xtPX4Jmuni_sHzTyUMFJRqw/viewform?usp=pp_url&entry.1116565432=Trust
Focus-A: https://docs.google.com/forms/d/e/1FAIpQLScMwCRHstG7GBKmC7hSgbXWNe_xtPX4Jmuni_sHzTyUMFJRqw/viewform?usp=pp_url&entry.1116565432=Focus-A
Lounge: https://docs.google.com/forms/d/e/1FAIpQLScMwCRHstG7GBKmC7hSgbXWNe_xtPX4Jmuni_sHzTyUMFJRqw/viewform?usp=pp_url&entry.1116565432=Lounge
SnackBar: https://docs.google.com/forms/d/e/1FAIpQLScMwCRHstG7GBKmC7hSgbXWNe_xtPX4Jmuni_sHzTyUMFJRqw/viewform?usp=pp_url&entry.1116565432=Lounge

### 8.3 상태 변경/코멘트(시설 관리자 전용)
- 버튼: "조치 중", "완료", "불가"
- 변경 시 메모 팝업 → `status_history` 자동 기록
- **시설 관리자 코멘트 영역**: 조치 상황/예정 사항/불가 사유를 일방향 안내용으로 작성

---

## 9. 중복 신고 방지 전략
1) **장소 페이지에서 진행 중 이슈 노출**(최소 정보) → 새 신고 전에 확인
2) **서버 병합 기능**: 유사/동일 건을 시설 관리자가 병합

---

## 10. 보안/권한/감사
- Apps Script→API: Bearer 토큰 검증(`REPORTIT_API_TOKEN`)
- 운영 UI: 로그인(사내 SSO 권장), 역할 기반 접근(Reporter/시설 관리자/Admin)
- **감사 로그**: 상태 변경/병합/삭제에 대해 `status_history` + 별도 `audit_log`(선택)

---

## 11. 배포/환경
- **프론트/운영 대시보드**: 기존 in-house Flask 템플릿 체계에 탑재
- **DB**: SQLite3
- **시크릿**: 환경변수/프로퍼티로 분리 (Webhook/Token/DB Path)

---

## 12. 테스트 시나리오(체크리스트)
- QR→폼 프리필 동작
- 폼 제출 시 시트 기록/스크립트 트리거 작동
- Slack 채널 Block 알림 수신
- API 등록(201/200 병합) 응답
- 목록/상세/상태 변경/코멘트/병합 동작
- Reporter: 내 신고는 ✔️ 뱃지 표시로 확인
- 시설 관리자/Admin: 코멘트 작성 및 상태 변경 가능

---

### 부록 A. Slack Block Kit 예시 페이로드(요약)
```json
{
  "blocks": [
    { "type": "header", "text": { "type": "plain_text", "text": "새 이슈 접수" }},
    { "type": "section", "fields": [
      { "type": "mrkdwn", "text": "*장소*\nMEET-3A" },
      { "type": "mrkdwn", "text": "*시설/장비*\n프로젝터" },
      { "type": "mrkdwn", "text": "*종류*\n고장" },
      { "type": "mrkdwn", "text": "*접수시각*\n2025-09-22T12:34:56Z" },
      { "type": "mrkdwn", "text": "*신고자*\nuser@company.com" }
    ]},
    { "type": "section", "text": { "type": "mrkdwn", "text": "*상세내용*\n전원 버튼 반응 없음" }}
  ]
}
```