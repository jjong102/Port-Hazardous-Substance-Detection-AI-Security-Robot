ALTER TABLE events ADD COLUMN perimeter_m REAL DEFAULT 30;
ALTER TABLE events ADD COLUMN report_url TEXT;
ALTER TABLE events ADD COLUMN requires_cosign INTEGER DEFAULT 0;

CREATE TABLE IF NOT EXISTS evidence(
  id INTEGER PRIMARY KEY,
  event_id INTEGER,
  kind TEXT,      -- photo|video|audio|note
  url TEXT,
  sha256 TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sop_logs(
  id INTEGER PRIMARY KEY,
  event_id INTEGER,
  step_id TEXT,
  ok INTEGER,
  note TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cosigns(
  id INTEGER PRIMARY KEY,
  event_id INTEGER,
  device_id TEXT,
  lat REAL, lng REAL,
  ts DATETIME,
  sig TEXT
);
