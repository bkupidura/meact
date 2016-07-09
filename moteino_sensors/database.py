import logging
import time

from sqlalchemy import Column, Integer, Text, Index, ForeignKey, desc, DDL, event, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


Base = declarative_base()
LOG = logging.getLogger(__name__)

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
    return "<Board(board_id='%s', board_desc='%s')>" % (
            self.board_id,
            self.board_desc)


class Action(Base):
  __tablename__ = 'actions'

  id = Column(Integer, primary_key=True)
  board_id = Column(Text, ForeignKey("boards.board_id"), nullable=False)
  sensor_type = Column(Text, nullable=False)
  sensor_action_id = Column(Text, nullable=False)
  last_update = Column(Integer, nullable=False)

  __table_args__ = (Index('idx_actions', 'board_id', 'sensor_type', 'sensor_action_id', 'last_update'), )

  def __repr__(self):
    return "<Action(board_id='%s', sensor_type='%s', sensor_action_id='%s', last_update='%s')>" % (
            self.board_id,
            self.sensor_type,
            self.sensor_action_id,
            self.last_update)


def connect(connect_string):
  return create_engine(connect_string, connect_args={'check_same_thread': False})


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
  commit(s)


def insert_metric(db, sensor_data):
  s = create_session(db)

  now = int(time.time())

  s.add(Metric(board_id = sensor_data['board_id'],
          sensor_type = sensor_data['sensor_type'],
          sensor_data = sensor_data['sensor_data'],
          last_update = now))

  last_metric = s.query(LastMetric).filter(LastMetric.board_id == sensor_data['board_id'],
          LastMetric.sensor_type == sensor_data['sensor_type'])
  if last_metric.scalar():
    last_metric.update({'sensor_data': sensor_data['sensor_data'],
        'last_update': now})
  else:
    s.add(LastMetric(board_id = sensor_data['board_id'],
        sensor_type = sensor_data['sensor_type'],
        sensor_data = sensor_data['sensor_data'],
        last_update = now))
  commit(s)


def prepare_board_ids(board_ids=None):
  if board_ids is not None and not isinstance(board_ids, list):
    return [board_ids]

  return board_ids


def get_boards(db, board_ids=None):
  s = create_session(db)

  board_ids = prepare_board_ids(board_ids)

  boards = s.query(Board)

  if board_ids:
    boards = boards.filter(Board.board_id.in_(board_ids))

  return boards.all()


def prepare_metrics(db, table, board_ids=None, sensor_type=None, start=None, end=None):
  board_ids = prepare_board_ids(board_ids)

  s = create_session(db)

  query = s.query(table)

  if board_ids:
    query = query.filter(table.board_id.in_(board_ids))

  if sensor_type:
    query = query.filter(table.sensor_type == sensor_type)

  if start:
    query = query.filter(table.last_update >= start)

  if end:
    query = query.filter(table.last_update <= end)

  return query


def get_last_metrics(db, board_ids=None, sensor_type=None, start=None, end=None):
  last_metrics = prepare_metrics(db, LastMetric, board_ids, sensor_type, start, end)

  return last_metrics.all()


def get_metrics(db, board_ids=None, sensor_type=None, start=None, end=None, last_available=None):
  metrics = prepare_metrics(db, Metric, board_ids, sensor_type, start, end)

  if last_available:
    metrics = metrics.order_by(desc(Metric.id)).limit(last_available).from_self()

  return metrics.order_by(Metric.id).all()


def update_metric(db, metric_id=None, sensor_data=None):
  s = create_session(db)
  metric = s.query(Metric).filter(Metric.id == metric_id).first()
  if metric and sensor_data:
    metric.sensor_data = sensor_data
    commit(s)


def delete_metrics(db, record_ids=None):
  if record_ids:
    s = create_session(db)
    query = s.query(Metric).filter(Metric.id.in_(record_ids)).delete('fetch')
    commit(s)


def get_action(db, sensor_data, sensor_action_id, last_available=None):
  s = create_session(db)

  query = s.query(Action).filter(Action.board_id == sensor_data['board_id'])
  query = query.filter(Action.sensor_type == sensor_data['sensor_type'])
  query = query.filter(Action.sensor_action_id == sensor_action_id)

  if last_available:
    query.order_by(desc(Action.id)).limit(last_available).from_self()

  return query.all()


def insert_action(db, sensor_data, sensor_action_id):
  s = create_session(db)

  now = int(time.time())

  s.add(Action(board_id = sensor_data['board_id'],
          sensor_type = sensor_data['sensor_type'],
          sensor_action_id = sensor_action_id,
          last_update = now))

  commit(s)


def commit(session=None):
  if session:
    try:
      session.commit()
    except:
      LOG.error('Fail to commit data')
      session.rollback()
    finally:
      session.close()
  else:
    LOG.warning('No session was provided for commit')
