
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

-- Report-It
CREATE TABLE IF NOT EXISTS assets (id INTEGER PRIMARY KEY AUTOINCREMENT, asset_code TEXT UNIQUE, name TEXT, type TEXT, location TEXT);
CREATE TABLE IF NOT EXISTS tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_id INTEGER, reporter_email TEXT, category TEXT, desc TEXT,
  status TEXT CHECK(status IN ('접수','조치중','완료')) DEFAULT '접수',
  photo_url TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, closed_at TEXT
);
CREATE TABLE IF NOT EXISTS ticket_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER, action TEXT, actor TEXT, memo TEXT, at TEXT DEFAULT CURRENT_TIMESTAMP);
