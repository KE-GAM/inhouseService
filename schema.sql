
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

-- Booker
CREATE TABLE IF NOT EXISTS desks (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, floor TEXT);
CREATE TABLE IF NOT EXISTS rooms (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, capacity INTEGER, floor TEXT);
CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id INTEGER NOT NULL,
  resource_type TEXT CHECK(resource_type IN ('desk','room')) NOT NULL,
  resource_id INTEGER NOT NULL,
  date TEXT NOT NULL, slot TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(resource_type, resource_id, date, slot)
);

-- Calendar
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
