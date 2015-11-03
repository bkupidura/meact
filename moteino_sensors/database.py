import sqlite3

from moteino_sensors import utils


BOARDS_TABLE_SQL = """
DROP TABLE IF EXISTS board_desc;
CREATE TABLE board_desc (
  board_id TEXT PRIMARY KEY,
  board_desc TEXT
);
"""


METRICS_TABLE_SQL = """
DROP TABLE IF EXISTS metrics;
CREATE TABLE metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  board_id TEXT, sensor_type TEXT,
  last_update TIMESTAMP DEFAULT (STRFTIME('%s', 'now')),
  data TEXT DEFAULT NULL
);

DROP INDEX IF EXISTS idx_board_id;
CREATE INDEX idx_board_id ON metrics (board_id, sensor_type, last_update, data);
"""


LAST_METRICS_TABLE_SQL = """
DROP TABLE IF EXISTS last_metrics;
CREATE TABLE last_metrics (
  board_id TEXT,
  sensor_type TEXT,
  last_update TIMESTAMP,
  data TEXT
);
DROP TRIGGER IF EXISTS insert_metric;
CREATE TRIGGER insert_metric
  INSERT ON metrics WHEN NOT EXISTS (
    SELECT 1 FROM last_metrics WHERE board_id=new.board_id and sensor_type=new.sensor_type
  )
BEGIN
  INSERT into last_metrics VALUES (new.board_id, new.sensor_type, new.last_update, new.data);
END;

DROP TRIGGER IF EXISTS update_metric;
CREATE TRIGGER update_metric
  INSERT ON metrics WHEN EXISTS (
    SELECT 1 FROM last_metrics WHERE board_id=new.board_id and sensor_type=new.sensor_type
  )
BEGIN
  UPDATE last_metrics SET data=new.data, last_update=new.last_update WHERE board_id==new.board_id and sensor_type==new.sensor_type;
END;
"""


def connect(db_file):
  return sqlite3.connect(db_file)


def create_db(db, boards_map):
  sync_boards(db, boards_map)

  db.executescript(METRICS_TABLE_SQL)
  db.executescript(LAST_METRICS_TABLE_SQL)


def sync_boards(db, boards_map):
  """Wipes out `boards` table and repopulates it"""
  db.executescript(BOARDS_TABLE_SQL)

  db.executemany(
    "INSERT INTO board_desc(board_id, board_desc) VALUES(?, ?)",
    boards_map.iteritems()
  )
  db.commit()
