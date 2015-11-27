import time

from sqlalchemy import Column, Integer, Text, Index, ForeignKey, desc, DDL, event, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


Base = declarative_base()

class Metric(Base):
  __tablename__ = 'metrics'

  id = Column(Integer, primary_key=True)
  board_id = Column(Text, ForeignKey("boards.board_id"), nullable=False)
  sensor_type = Column(Text, nullable=False)
  sensor_data = Column(Text, nullable=False)
  last_update = Column(Integer, nullable=False)

  __table_args__ = (Index('idx_metrics', 'board_id', 'sensor_type', 'sensor_data', 'last_update'), )

  def __repr__(self):
    return "<Metric(board_id='%s', sensor_type='%s', sensor_data='%s', 'last_update'='%s')>" % (
            self.board_id,
            self.sensor_type,
            self.sensor_data,
            self.last_update)


class LastMetric(Base):
  __tablename__ = 'last_metrics'

  board_id = Column(Text, ForeignKey("boards.board_id"), nullable=False, primary_key=True)
  sensor_type = Column(Text, nullable=False, primary_key=True)
  sensor_data = Column(Text, nullable=False)
  last_update = Column(Integer, nullable=False)

  def __repr__(self):
    return "<Metric(board_id='%s', sensor_type='%s', sensor_data='%s', 'last_update'='%s')>" % (
            self.board_id,
            self.sensor_type,
            self.sensor_data,
            self.last_update)


class Board(Base):
  __tablename__ = 'boards'

  board_id = Column(Text, primary_key=True)
  board_desc = Column(Text, nullable=False)

  def __repr__(self):
    return "<Metric(board_id='%s', board_desc='%s')>" % (
            self.board_id,
            self.board_desc)


TRIGGER_SQLITE_INSERT = DDL("""
CREATE TRIGGER insert_metric
  INSERT ON metrics WHEN NOT EXISTS (
    SELECT 1 FROM last_metrics WHERE board_id = new.board_id and sensor_type = new.sensor_type
  )
  BEGIN
    INSERT into last_metrics VALUES (new.board_id, new.sensor_type, new.last_update, new.sensor_data);
  END;
""")

TRIGGER_SQLITE_UPDATE = DDL("""
CREATE TRIGGER update_metric
  INSERT ON metrics WHEN EXISTS (
    SELECT 1 FROM last_metrics WHERE board_id = new.board_id and sensor_type = new.sensor_type
  )
  BEGIN
    UPDATE last_metrics SET sensor_data = new.sensor_data, last_update = new.last_update WHERE board_id = new.board_id and sensor_type = new.sensor_type;
  END;
""")

event.listen(
  Base.metadata,
  'after_create',
  TRIGGER_SQLITE_INSERT.execute_if(dialect='sqlite')
)
event.listen(
  Base.metadata,
  'after_create',
  TRIGGER_SQLITE_UPDATE.execute_if(dialect='sqlite')
)

def connect(db_file):
  return create_engine('sqlite:///{}'.format(db_file))


def create_session(db):
  Session = sessionmaker()
  Session.configure(bind=db)
  return Session()


def create_db(db, boards_map):
  Base.metadata.drop_all(db)
  Base.metadata.create_all(db)

  sync_boards(db, boards_map)


def sync_boards(db, boards_map):
  s = create_session(db)

  s.query(Board).delete()
  for board in boards_map.iteritems():
    b = Board(board_id=board[0], board_desc=board[1])
    s.add(b)
  s.commit()


def insert_metric(db, sensor_data):
  s = create_session(db)

  now = int(time.time())

  s.add(Metric(board_id = sensor_data['board_id'],
          sensor_type = sensor_data['sensor_type'],
          sensor_data = sensor_data['sensor_data'],
          last_update = now))

  s.commit()


def get_boards(db, board_ids=None):
  s = create_session(db)

  if board_ids is not None and not isinstance(board_ids, list):
    board_ids = [board_ids]

  boards = s.query(Board)

  if board_ids:
    boards = boards.filter(Board.board_id.in_(board_ids))

  return boards.all()


def get_last_metrics(db, board_ids=None, sensor_type=None, start=None, end=None):
  s = create_session(db)

  if board_ids is not None and not isinstance(board_ids, list):
    board_ids = [board_ids]

  last_metrics = s.query(LastMetric)

  if board_ids:
    last_metrics = last_metrics.filter(LastMetric.board_id.in_(board_ids))

  if sensor_type:
    last_metrics = last_metrics.filter(LastMetric.sensor_type == sensor_type)

  if start:
    last_metrics = last_metrics.filter(LastMetric.last_update >= start)

  if end:
    last_metrics = last_metrics.filter(LastMetric.last_update <= end)

  return last_metrics.all()


def get_metrics(db, board_ids=None, sensor_type=None, start=None, end=None, last_available=None):
  s = create_session(db)

  if board_ids is not None and not isinstance(board_ids, list):
    board_ids = [board_ids]

  metrics = s.query(Metric)

  if sensor_type:
    metrics = metrics.filter(Metric.sensor_type == sensor_type)

  if board_ids:
    metrics = metrics.filter(Metric.board_id.in_(board_ids))

  if start:
    metrics = metrics.filter(Metric.last_update >= start)

  if end:
    metrics = metrics.filter(Metric.last_update <= end)

  if last_available:
    metrics = metrics.order_by(desc(Metric.id)).limit(last_available).from_self()

  return metrics.order_by(Metric.id).all()
