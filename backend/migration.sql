-- backend/migration.sql
-- Create basic tables if not exist
CREATE TABLE IF NOT EXISTS readings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rtype TEXT,
  value REAL,
  lat REAL,
  lng REAL,
  vehicle_id TEXT DEFAULT 'robot-1',
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_readings_type ON readings(rtype);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  substance TEXT,
  concentration REAL,
  lat REAL,
  lng REAL,
  vehicle_id TEXT DEFAULT 'robot-1',
  status TEXT DEFAULT 'new',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  approved_at DATETIME,
  resolved_at DATETIME,
  approved_by TEXT,
  resolved_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(created_at);
