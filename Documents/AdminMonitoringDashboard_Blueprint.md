http://127.0.0.1:8000/admin/
# 📊 관리자 모니터링 대시보드 BluePrint
**Version:** 1.0 (MVP)  
**Scope:** Desk & Room Booker / Calendar HUB / Report-It / Nota Guidebook / NoonPick  
**Runtime Target:** Flask + SQLite3 (단일 DB)  
**Time Zone:** Asia/Seoul (KST)  

---

# 1) 목표(Why)
인하우스 5개 서비스의 **핵심 지표를 선택적으로 모니터링**하여
- 실제로 매일 쓰이는지(활성),  
- 업무 효율 향상에 기여하는지(전환·해결),  
- 병목 또는 문제 신호가 어디인지(실패·중복·0건 검색),  
를 **한 화면에서 빠르게 파악**한다.

원칙
1) **공통 이벤트 테이블 1장**으로 모든 로그 집계.  
2) **서비스 드롭다운 + 기간(시작·끝) 선택 + 지표 토글** 구조.  
3) 기간에 따라 **버킷 자동 전환**(≤72h: 시간, >72h: 일).  
4) 지표 정의는 본 문서와 **1:1 일치**해야 함.

---

# 2) 화면/UX 구조
## 2.1 상단 바
- **서비스 선택 드롭다운**: `booker / calendar / reportit / faq / noonpick`
- **기간 선택**: `시작일시 ~ 종료일시` (KST, 기본: 최근 7일)
- **버킷 표시**: `hour` 또는 `day` (자동 판정 규칙 표시)
- **지표 토글/체크박스**: 선택한 서비스의 KPI들을 On/Off
- **Last updated**: 데이터 최신화 시각(KST)

## 2.2 본문
- **KPI 카드(3~5개)**: 선택 서비스의 핵심 수치를 큰 숫자로
- **시계열 그래프(라인/막대)**: 토글된 지표만 표시, 버킷 단위에 맞춤
- **보조 표(선택)**: Top 항목(예: FAQ 문서/NoonPick 메뉴) 또는 Zero-result 쿼리

## 2.3 공통 표시 규칙
- 퍼센트 지표: `소수점 1자리`(예: 81.3%)
- 분모=0: `–`로 표시 + 툴팁 `집계 없음`
- KST 고정, X축 라벨은 버킷 단위에 맞춤

---

# 3) 데이터 모델(개념)
단일 테이블 **events**
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | 자동 증가 |
| ts | DATETIME | 이벤트 시각(KST 저장 또는 TZ 변환) |
| user_id | TEXT | 이메일/사번/해시(개인정보 최소 수집 원칙) |
| service | TEXT | `booker|calendar|reportit|faq|noonpick` |
| action | TEXT | 서비스별 이벤트명(스네이크 케이스) |
| target_id | TEXT | 예약/문서/이슈/메뉴 등 식별자 |
| meta | TEXT(JSON) | 추가 속성(JSON 문자열) |

권장 인덱스  
- `CREATE INDEX idx_events_ts ON events(ts);`  
- `CREATE INDEX idx_events_svc_act_ts ON events(service, action, ts);`

자동/배치 이벤트 구분: `meta.source = 'user' | 'system'`

---

# 4) 서비스별 이벤트 사전(요약)
> *상세 이벤트명은 필요 시 확장. 핵심은 **source='user'** 기준으로 활성 지표 산정.*

## 4.1 Desk & Room Booker (`booker`)
- `reservation_attempt` `{roomId,start,end}`  
- `reservation_success` `{roomId,start,end}`  
- `reservation_failed` `{roomId,start,end,reason}` // `overlap|permission|invalid`  
- `claim_focusroom` `{roomId,until}`

## 4.2 Calendar HUB (`calendar`)
- `view_calendar` `{tab:'my|vacation|official', source:'user|system'}`  
- `register_vacation` `{days,from,to, source}`  
- (선택) `event_created` `{origin:'booker|calendar', source}`

## 4.3 Report-It (`reportit`)
- `issue_created` `{severity,category, source}`  
- `issue_resolved` `{issueId,ttr_minutes, source}`  
- `slack_click` `{issueId, source}`

## 4.4 FAQ/Guidebook (`faq`)
- `faq_view` `{docId, source}`  
- `faq_search` `{q,resultsCount, source}`  
- `faq_zero_result` `{q, source}`

## 4.5 NoonPick (`noonpick`)
- `menu_recommended` `{ts_noon,candidates:[...], source}`  
- `menu_clicked` `{menuId, source}`  
- `menu_selected` `{menuId, source}`

---

# 5) KPI 정의(정식)
## 5.1 Booker
- **예약 성공률** = `reservation_success / reservation_attempt`  
- **중복시도율** = `reservation_failed(reason='overlap') / reservation_attempt`  
- **점유율(시간)** = `Σ reserved_minutes / (회의실수 × 운영시간분)`  
  - *reserved_minutes는 success meta에서 (end-start)로 산출*

## 5.2 Calendar (Strict, user 이벤트만)
- **DAU** = `DISTINCT user_id` where `action IN ('view_calendar','register_vacation','edit_event') AND meta.source='user'`  
- **탭 비중** = `view_calendar.meta.tab` 그룹 카운트 분포(‘user’만)

## 5.3 Report-It
- **신규 이슈** = `issue_created` 수  
- **해결율** = `issue_resolved / issue_created` *(동일 집계 기간)*  
- **평균 TTR(분)** = `AVG(issue_resolved.meta.ttr_minutes)` *(중앙값 병행 권고)*

## 5.4 FAQ
- **검색 0건 비율** = `faq_zero_result / faq_search`  
- **Top 문서** = `faq_view` 상위 docId (정렬: 조회수)

## 5.5 NoonPick
- **선택률** = `menu_selected / menu_recommended`  
- **7일 중복률** = `1 - (distinct(menu_selected) / total(menu_selected))` (최근 7일)  
- **Top 메뉴** = `menu_selected` 상위 메뉴ID

---

# 6) 버킷/기간 규칙
- **버킷 자동 전환**: 조회 기간이 `≤ 72h` → `hour`, 그 외 `day`
- **기간 경계**: `[from(포함) ~ to(미포함)]`, KST 기준 정확히 24h/1h 간격
- 기본 프리셋: 최근 7일

---

# 7) API 계약(개념)
단일 엔드포인트 권장: **`GET /admin/api/metrics`**

### 요청 파라미터
- `service` : `booker|calendar|reportit|faq|noonpick`  
- `from` : `YYYY-MM-DD` 또는 `YYYY-MM-DD HH:MM:SS` (KST)  
- `to` : `YYYY-MM-DD` 또는 `YYYY-MM-DD HH:MM:SS` (KST)  
- `bucket` : `hour|day` (미지정 시 자동 판정)  
- `include` : 쉼표분리 지표 키(토글 상태 반영, 예: `success_rate,overlap_rate`)  
- (선택) `limit` : 표 데이터 개수(Top N 등)

### 응답 예시(서비스별)
```json
{
  "service": "booker",
  "range": {"from":"2025-09-16","to":"2025-09-23","bucket":"day"},
  "kpis": {
    "success_rate": {"value": 0.813},
    "overlap_rate": {"value": 0.172},
    "occupancy": {"value": 0.531}
  },
  "series": {
    "success_rate": [["2025-09-17",0.78],["2025-09-18",0.82]],
    "overlap_rate": [["2025-09-17",0.19],["2025-09-18",0.16]],
    "occupancy":    [["2025-09-17",0.47],["2025-09-18",0.55]]
  },
  "tables": {},
  "last_updated_kst": "2025-09-23 10:05:12"
}
```
```json
{
  "service": "faq",
  "range": {"from":"2025-09-16","to":"2025-09-23","bucket":"day"},
  "kpis": { "zero_rate": {"value": 0.152} },
  "series": { "zero_rate": [["2025-09-17",0.11],["2025-09-18",0.18]] },
  "tables": {
    "top_docs": [["HR-101",84],["VPN-Guide",63]],
    "zero_queries": [["연차 이월",7],["출장비 정산",5]]
  },
  "last_updated_kst": "2025-09-23 10:05:12"
}
```

지표 키(예시)
- `booker`: `success_rate,overlap_rate,occupancy`
- `calendar`: `dau,tab_share_my,tab_share_vacation,tab_share_official`
- `reportit`: `created,resolved,resolve_rate,ttr_avg,ttr_p50`
- `faq`: `zero_rate`
- `noonpick`: `select_rate,dup7`

---

# 8) 차트 매핑(권장)
- **Booker**: 성공률/중복시도율(라인), 점유율(영역)  
- **Calendar**: DAU(라인), 탭 비중(스택 막대)  
- **Report-It**: created·resolved(이중축 막대/라인), TTR(라인)  
- **FAQ**: Zero-rate(라인), Top 문서/Zero-queries(표)  
- **NoonPick**: 선택률/7일중복률(라인), Top 메뉴(표)

---

# 9) 품질/성능(초기 최소)
- 조회 범위 가드: 최대 180일
- SQLite `WAL` 모드 권장, 인덱스는 3장 참조
- (선택) 7일/30일 **일 단위 사전 집계** 테이블로 응답 체감 개선

---

# 10) QA 체크리스트
- [ ] 서비스/기간/버킷 조합별 **수치 일관성**(수작업 계산 대비)  
- [ ] **분모=0** 지표 표시(`–`)와 툴팁 동작  
- [ ] Calendar DAU가 **user 이벤트만** 집계되는지 확인(`meta.source='user'`)  
- [ ] 버킷 전환 경계(72h)에서 **축/데이터 포인트** 정상  
- [ ] 표 데이터(Top N)가 요청 `limit`와 일치

---

# 11) 릴리스 플랜(MVP)
1) **MVP**: 드롭다운/기간/버킷/토글 + KPI 카드 + 시계열 그래프 + (필요 시) 표 1개  
2) **V1**: 전/후 비교(Δ, %Δ), 간단 드릴다운(집계 표)  
3) **V2**: 사전 집계 캐시/CSV 내보내기/저장된 뷰

---

# 12) 부록 — 샘플 이벤트(JSON)
```json
{"ts":"2025-09-23T11:58:00","user_id":"u123","service":"booker","action":"reservation_attempt","target_id":"R-A-20250923-1200","meta":{"roomId":"A","start":"2025-09-23T12:00:00","end":"2025-09-23T12:30:00","source":"user"}}
{"ts":"2025-09-23T11:58:02","user_id":"u123","service":"booker","action":"reservation_success","target_id":"R-A-20250923-1200","meta":{"roomId":"A","start":"2025-09-23T12:00:00","end":"2025-09-23T12:30:00","source":"user"}}
{"ts":"2025-09-23T12:00:05","user_id":"u888","service":"faq","action":"faq_zero_result","meta":{"q":"연차 이월","source":"user"}}
{"ts":"2025-09-23T12:00:10","user_id":"u555","service":"noonpick","action":"menu_selected","meta":{"menuId":"naengmyeon","source":"user"}}
{"ts":"2025-09-23T12:10:00","user_id":"u123","service":"calendar","action":"view_calendar","meta":{"tab":"my","source":"user"}}
```
