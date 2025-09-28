
-- Core employees
CREATE TABLE IF NOT EXISTS employees (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT, email TEXT UNIQUE, team TEXT
);

-- Notice
CREATE TABLE IF NOT EXISTS announcements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slack_ts TEXT UNIQUE, channel TEXT, author TEXT,
  text TEXT, html TEXT, created_at TEXT, edited_at TEXT,
  deleted INTEGER DEFAULT 0
);

-- Nota Office Service: Desk & Room Booker
-- Legacy tables for compatibility
CREATE TABLE IF NOT EXISTS desks (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, floor TEXT);
CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id INTEGER NOT NULL,
  resource_type TEXT CHECK(resource_type IN ('desk','room')) NOT NULL,
  resource_id INTEGER NOT NULL,
  date TEXT NOT NULL, slot TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(resource_type, resource_id, date, slot)
);

-- New Nota Office Service Tables
CREATE TABLE IF NOT EXISTS rooms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('MEETING','FOCUS','LOUNGE')),
  capacity INTEGER,
  floor TEXT,
  svg_id TEXT,  -- for SVG mapping
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reservations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER NOT NULL REFERENCES rooms(id),
  start_time TEXT NOT NULL,  -- ISO 8601 format
  end_time TEXT NOT NULL,    -- ISO 8601 format
  status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','CANCELLED')),
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS occupancies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER NOT NULL REFERENCES rooms(id),
  start_time TEXT NOT NULL,  -- ISO 8601 format
  end_time TEXT,             -- NULL means still active
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','completed','expired')),
  timer_duration INTEGER DEFAULT 7200,  -- seconds (default 2 hours)
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_reservations_room_time ON reservations(room_id, start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_occupancies_active ON occupancies(room_id, status) WHERE status = 'active';

-- Calendar Hub: Extended schema for complete calendar functionality
-- HRIS employees table (synced from HRIS data)
CREATE TABLE IF NOT EXISTS hris_employees (
  employee_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  gender TEXT,
  dob TEXT,
  org_code TEXT NOT NULL,
  org_name TEXT NOT NULL,
  title TEXT,
  hire_date TEXT,
  email TEXT,
  location TEXT,
  is_active BOOLEAN DEFAULT 1,
  synced_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Calendar events (My + Official)
CREATE TABLE IF NOT EXISTS calendar_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  description TEXT,
  start_at TEXT NOT NULL,  -- ISO8601 format
  end_at TEXT NOT NULL,    -- ISO8601 format
  all_day BOOLEAN DEFAULT 0,
  location TEXT,
  event_type TEXT CHECK(event_type IN ('MY','OFFICIAL')) NOT NULL,
  owner_email TEXT NOT NULL,
  status TEXT CHECK(status IN ('SCHEDULED','CANCELLED')) DEFAULT 'SCHEDULED',
  source_type TEXT,  -- for future external integration
  source_id TEXT,    -- for future external integration
  source_version INTEGER DEFAULT 1,
  created_by TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Vacation events (from HRIS)
CREATE TABLE IF NOT EXISTS vacation_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id TEXT NOT NULL,
  name TEXT NOT NULL,
  org_code TEXT NOT NULL,
  org_name TEXT NOT NULL,
  type TEXT CHECK(type IN ('PTO','HALF','SICK')) NOT NULL,
  start_at TEXT NOT NULL,  -- ISO8601 format
  end_at TEXT NOT NULL,    -- ISO8601 format
  all_day BOOLEAN DEFAULT 1,
  status TEXT CHECK(status IN ('ACTIVE','CANCELLED')) DEFAULT 'ACTIVE',
  hris_updated_at TEXT,
  synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (employee_id) REFERENCES hris_employees(employee_id)
);

-- Event subscriptions (Vacation/Official -> My)
CREATE TABLE IF NOT EXISTS event_subscriptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  subscriber_email TEXT NOT NULL,
  source_table TEXT CHECK(source_table IN ('vacation_events','calendar_events')) NOT NULL,
  source_event_id INTEGER NOT NULL,
  my_event_id INTEGER NOT NULL,
  user_memo TEXT,  -- private memo for subscriber
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (my_event_id) REFERENCES calendar_events(id),
  UNIQUE(subscriber_email, source_table, source_event_id)
);

-- User settings
CREATE TABLE IF NOT EXISTS user_settings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_email TEXT NOT NULL,
  setting_key TEXT NOT NULL,
  setting_value TEXT,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_email, setting_key)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_calendar_events_owner_time ON calendar_events(owner_email, start_at, end_at);
CREATE INDEX IF NOT EXISTS idx_vacation_events_org_time ON vacation_events(org_code, start_at, end_at);
CREATE INDEX IF NOT EXISTS idx_vacation_events_status ON vacation_events(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_subscriber ON event_subscriptions(subscriber_email);
CREATE INDEX IF NOT EXISTS idx_hris_employees_org ON hris_employees(org_code);

-- Legacy events table (keeping for backward compatibility)
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT CHECK(kind IN ('my','vac','company')) NOT NULL,
  owner_email TEXT, title TEXT NOT NULL,
  start TEXT NOT NULL, end TEXT NOT NULL,
  location TEXT, body TEXT, link TEXT,
  created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Report-It: 시설/IT 이슈 신고 및 관리 시스템
CREATE TABLE IF NOT EXISTS issues (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  location_id TEXT NOT NULL,      -- 장소 ID (예: 'MEET-3A', 'Ownership', 'Trust')
  title TEXT NOT NULL,            -- 이슈 발생 시설/장 (예: '프로젝터', '프린터A')
  type TEXT NOT NULL,             -- 이슈 종류 ('고장', '파손', '성능저하', '기타')
  description TEXT,               -- 이슈 내용
  status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','IN_PROGRESS','DONE','CANNOT_FIX')),
  reporter_email TEXT,            -- 신고자 이메일
  reported_at TEXT NOT NULL,      -- 신고 시각 (ISO8601)
  source TEXT DEFAULT 'manual',   -- 신고 경로 ('google_form', 'manual')
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  issue_id INTEGER NOT NULL,
  url TEXT NOT NULL,              -- 첨부 파일 URL (Google Drive 등)
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(issue_id) REFERENCES issues(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  issue_id INTEGER NOT NULL,
  body TEXT NOT NULL,             -- 코멘트 내용
  author TEXT,                    -- 작성자 (시설 관리자명)
  source TEXT DEFAULT 'manual',   -- 작성 경로 ('manual', 'auto_merge')
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(issue_id) REFERENCES issues(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS status_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  issue_id INTEGER NOT NULL,
  status TEXT NOT NULL,           -- 변경된 상태
  actor TEXT,                     -- 변경한 사람 (시설 관리자명)
  memo TEXT,                      -- 변경 메모
  changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(issue_id) REFERENCES issues(id) ON DELETE CASCADE
);

-- Report-It 인덱스
CREATE INDEX IF NOT EXISTS idx_issues_location_status ON issues(location_id, status);
CREATE INDEX IF NOT EXISTS idx_issues_reporter ON issues(reporter_email);
CREATE INDEX IF NOT EXISTS idx_issues_status_date ON issues(status, reported_at);
CREATE INDEX IF NOT EXISTS idx_attachments_issue ON attachments(issue_id);
CREATE INDEX IF NOT EXISTS idx_comments_issue ON comments(issue_id);
CREATE INDEX IF NOT EXISTS idx_status_history_issue ON status_history(issue_id);

-- Legacy Report-It tables (keeping for backward compatibility)
CREATE TABLE IF NOT EXISTS assets (id INTEGER PRIMARY KEY AUTOINCREMENT, asset_code TEXT UNIQUE, name TEXT, type TEXT, location TEXT);
CREATE TABLE IF NOT EXISTS tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_id INTEGER, reporter_email TEXT, category TEXT, desc TEXT,
  status TEXT CHECK(status IN ('접수','조치중','완료')) DEFAULT '접수',
  photo_url TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, closed_at TEXT
);
CREATE TABLE IF NOT EXISTS ticket_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER, action TEXT, actor TEXT, memo TEXT, at TEXT DEFAULT CURRENT_TIMESTAMP);

-- NoonPick: 점심 추천 서비스
-- 오피스 고정 위치 (지오코딩 1회 후 저장)
CREATE TABLE IF NOT EXISTS offices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE,      -- 'seoul' | 'daejeon'
  name TEXT,
  address TEXT,
  lat REAL,
  lng REAL,
  is_default INTEGER DEFAULT 0
);

-- 카카오 Local 캐시 (반경 검색 결과)
CREATE TABLE IF NOT EXISTS places (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
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
  photo_url TEXT,           -- 음식점 사진 URL
  last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, provider_key)
);

-- 방문 기록 (선택 버튼 누를 때)
CREATE TABLE IF NOT EXISTS visits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  place_id INTEGER,
  visited_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(place_id) REFERENCES places(id)
);

-- OG 메타 캐시 (썸네일/제목/설명)
CREATE TABLE IF NOT EXISTS og_cache (
  url TEXT PRIMARY KEY,
  title TEXT,
  description TEXT,
  image TEXT,
  cached_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- NoonPick 인덱스
CREATE INDEX IF NOT EXISTS idx_places_provider_key ON places(provider, provider_key);
CREATE INDEX IF NOT EXISTS idx_places_location ON places(lat, lng);
CREATE INDEX IF NOT EXISTS idx_visits_user_place ON visits(user_id, place_id);
CREATE INDEX IF NOT EXISTS idx_visits_date ON visits(visited_at);
CREATE INDEX IF NOT EXISTS idx_og_cache_url ON og_cache(url);

-- Admin Monitoring Dashboard
-- 모든 서비스의 이벤트를 집계하는 통합 테이블
CREATE TABLE IF NOT EXISTS monitoring_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts DATETIME NOT NULL,                    -- 이벤트 시각 (KST)
  user_id TEXT NOT NULL,                   -- 이메일/사번/해시 (개인정보 최소 수집)
  service TEXT NOT NULL CHECK(service IN ('booker','calendar','reportit','faq','noonpick')),
  action TEXT NOT NULL,                    -- 서비스별 이벤트명 (스네이크 케이스)
  target_id TEXT,                          -- 예약/문서/이슈/메뉴 등 식별자
  meta TEXT,                               -- 추가 속성 (JSON 문자열)
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 모니터링 이벤트 인덱스
CREATE INDEX IF NOT EXISTS idx_events_ts ON monitoring_events(ts);
CREATE INDEX IF NOT EXISTS idx_events_svc_act_ts ON monitoring_events(service, action, ts);
CREATE INDEX IF NOT EXISTS idx_events_user_ts ON monitoring_events(user_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_service ON monitoring_events(service);
