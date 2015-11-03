#!/usr/bin/env python
import serial
import time
import json
import sqlite3
import threading
import random
import logging
import sys
import os
import socket
import re
import argparse
import requests
import smtplib

from moteino_sensors import utils


class ActionDetailsAdapter(dict):
  """Adapter for action details

  Provides helpers and functions that allows
  to easily work on action details
  """
  def should_check_if_armed(self, board_id):
    """Should action be checked for given board?"""
    return (
      self['check_if_armed']['default']
      ^
      (board_id in self['check_if_armed']['except'])
    )


def log(data, action_config):
  LOG.info("Log action for '%s'", data)
  return True


def send_sms(data, action_config):
  if not action_config.get('enabled'):
    return False

  if 'message' in data:
    msg = data['message']
  else:
    msg = '{sensor_type} on board {board_desc} ({board_id}) reports value {sensor_data}'.format(**data)

  LOG.debug('Sending SMS')

  url = action_config['endpoint']
  params = {'username': action_config['user'],
          'password': action_config['password'],
          'msisdn': action_config['recipient'],
          'message': msg}

  logging.getLogger("urllib3").setLevel(logging.CRITICAL)
  try:
    r = requests.get(url, params=params, timeout=5)
    r.raise_for_status()
  except (requests.HTTPError, requests.ConnectionError, requests.exceptions.Timeout) as e:
    LOG.warning("Got exception '%s' in send_sms", e)
    return False

  result = r.text.split('|')
  if result[0] != '0':
    LOG.warning("Fail in send_sms '%s' '%s'", result[0], result[1])
    return False

  return True


def send_mail(data, action_config):
  if not action_config.get('enabled'):
    return False

  if 'message' in data:
    msg = data['message']
  else:
    msg = '{sensor_type} on board {board_desc} ({board_id}) reports value {sensor_data}'.format(**data)

  LOG.debug('Sending mail')

  message = "From: {sender}\nTo: {recipient}\nSubject: {subject}\n\n{msg}\n\n".format(msg=msg, **action_config)
  try:
    s = smtplib.SMTP(action_config['host'], action_config['port'], timeout=5)
    s.starttls()
    s.login(action_config['user'], action_config['password'])
    s.sendmail(action_config['sender'], action_config['recipient'], message)
    s.quit()
  except (socket.gaierror, socket.timeout, smtplib.SMTPAuthenticationError, smtplib.SMTPDataError) as e:
    LOG.warning("Got exception '%s' in send_mail", e)
    return False
  else:
    return True


def action_execute(data, action, action_config):
  result = 0
  for a in action:
    LOG.debug("Action execute '%s'", a)
    if not eval(a['name'])(data, action_config.get(a['name'])):
      if 'failback' in a:
        result += action_execute(data, a['failback'], action_config)
    else:
      result += 1
  return result


def action_helper(data, action_details, action_config=None):
  action_details.setdefault('check_if_armed', {'default': True})
  action_details['check_if_armed'].setdefault('except', [])
  action_details.setdefault('action_interval', 0)
  action_details.setdefault('threshold', 'lambda x: True')
  action_details.setdefault('fail_count', 0)
  action_details.setdefault('fail_interval', 600)

  action_details = ActionDetailsAdapter(action_details)

  LOG.debug("Action helper '%s' '%s'", data, action_details)
  now = int(time.time())

  ACTION_STATUS.setdefault(data['board_id'], {})
  ACTION_STATUS[data['board_id']].setdefault(data['sensor_type'], {'last_action': 0, 'last_fail': []})

  ACTION_STATUS[data['board_id']][data['sensor_type']]['last_fail'] = \
    [i for i in ACTION_STATUS[data['board_id']][data['sensor_type']]['last_fail'] if now - i < action_details['fail_interval']]

  if action_details.should_check_if_armed(data['board_id']) and not STATUS['armed']:
    return

  if not eval(action_details['threshold'])(data['sensor_data']):
    return

  if len(ACTION_STATUS[data['board_id']][data['sensor_type']]['last_fail']) <= action_details['fail_count']-1:
    ACTION_STATUS[data['board_id']][data['sensor_type']]['last_fail'].append(now)
    return

  if (now - ACTION_STATUS[data['board_id']][data['sensor_type']]['last_action'] <= action_details['action_interval']):
    return

  if action_execute(data, action_details['action'], action_config):
    ACTION_STATUS[data['board_id']][data['sensor_type']]['last_action'] = now


def connect_db(db_file):
  db = sqlite3.connect(db_file)
  return db


# NOTE(prmtl): this could be also loaded from file to save
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


def create_db(db_file, appdir, create_metrics_table=False):
  board_map = utils.load_config(appdir + '/boards.config.json')
  db = connect_db(db_file)

  db.executescript(BOARDS_TABLE_SQL)

  db.executemany(
    "INSERT INTO board_desc(board_id, board_desc) VALUES(?, ?)",
    board_map.iteritems()
  )
  db.commit()

  if create_metrics_table:
    db.executescript(METRICS_TABLE_SQL)

  db.executescript(LAST_METRICS_TABLE_SQL)


def create_logger(level, log_file=None):
  logger = logging.getLogger()
  logger.setLevel(level)
  formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')

  if log_file:
    handler = logging.FileHandler(log_file)
  else:
    handler = logging.StreamHandler(sys.stdout)

  handler.setFormatter(formatter)
  logger.addHandler(handler)


class mgmt_Thread(threading.Thread):
  def __init__(self, appdir):
    super(mgmt_Thread, self).__init__()
    self.name = 'mgmt'

    conf = utils.load_config(appdir + '/global.config.json')
    board_map = utils.load_config(appdir + '/boards.config.json')
    sensor_map = utils.load_config(appdir + '/sensors.config.json')

    self.socket = conf['mgmt_socket']
    self.serial = serial.Serial(
      conf['serial']['device'],
      conf['serial']['speed'],
      timeout=conf['serial']['timeout']
    )

    # Missing sensor detector thread
    self.msd = failure_Thread(
      name='msd',
      loop_sleep=conf['msd']['loop_sleep'],
      db_file=conf['db_file'],
      action_interval=conf['msd']['action_interval'],
      query=conf['msd']['query'],
      action=conf['msd']['action'],
      board_map=board_map,
      action_config=conf['action_config'])

    self.mgw = mgw_Thread(
      ser=self.serial,
      loop_sleep=conf['loop_sleep'],
      gateway_ping_time=conf['gateway_ping_time'],
      db_file=conf['db_file'],
      board_map=board_map,
      sensor_map=sensor_map,
      action_config=conf['action_config'])

  def handle_action(self, data):
    if 'action' not in data:
      LOG.debug('No action to handle')

    if data['action'] == 'status':
      return STATUS

    if data['action'] == 'send' and 'data' in data:
      try:
        r_cmd = "{nodeid}:{cmd}".format(**data['data'])
        self.serial.write(r_cmd)
      except (IOError, ValueError, serial.serialutil.SerialException) as e:
        LOG.error("Got exception '%s' in mgmt thread", e)

    if data['action'] == 'set' and 'data' in data:
      STATUS.update(data['data'])

      if 'mgw' in data['data']:
        self.mgw.enabled.set() if data['data']['mgw'] else self.mgw.enabled.clear()
      if 'msd' in data['data']:
        self.msd.enabled.set() if data['data']['msd'] else self.msd.enabled.clear()

  def run(self):
    LOG.info('Starting')

    self.msd.start()
    self.mgw.start()

    if os.path.exists(self.socket):
      os.remove(self.socket)

    # TODO(prmtl): write a socket server class that will abstract this?
    self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    self.server.bind(self.socket)
    self.server.listen(1)

    while True:
      # TODO(prmtl): check if we can do it onece
      conn, addr = self.server.accept()
      data = conn.recv(1024)

      LOG.debug("Got '%s' on mgmt socket", data)

      if not data:
        continue

      try:
        data = json.loads(data)
      except (ValueError) as e:
        LOG.warning("Cannot decode recieved data in mgmt thread: %s", e)
        continue

      response = self.handle_action(data)
      if response:
        conn.send(json.dumps(response))

      conn.close()


class failure_Thread(threading.Thread):
  def __init__(self, name, loop_sleep, db_file, action_interval,
          query, action, board_map, action_config):
    super(failure_Thread, self).__init__()
    self.name = name
    self.daemon = True
    self.enabled = threading.Event()
    if STATUS[name]:
      self.enabled.set()
    self.loop_sleep = loop_sleep
    self.db_file = db_file
    self.action_interval = action_interval
    self.query = query
    self.action = action
    self.board_map = board_map
    self.action_config = action_config
    self.failed = {}

  def handle_failed(self, board_id, value):
    now = int(time.time())
    data = {'board_id': board_id, 'sensor_data': 1, 'sensor_type': self.name}
    action_details = {'check_if_armed': {'default': 0}, 'action_interval': self.action_interval, 'action': self.action}

    if self.name == 'msd':
      message = 'No update from {} ({}) since {} seconds'.format(self.board_map[board_id],
              board_id, now - value)

      data['message'] = message
      action_helper(data, action_details, self.action_config)

  def run(self):
    LOG.info('Starting')
    self.db = connect_db(self.db_file)
    while True:
      self.enabled.wait()
      now = int(time.time())

      for board_id, value in self.db.execute(self.query):
        self.handle_failed(board_id, value)

      time.sleep(self.loop_sleep)


class mgw_Thread(threading.Thread):

  # [ID][metric:value] / [10][voltage:3.3]
  _re_sensor_data = re.compile(
    '\[(?P<board_id>\d+)\]\[(?P<sensor_type>.+):(?P<sensor_data>.+)\]')

  def __init__(self, ser, loop_sleep, gateway_ping_time,
          db_file, board_map, sensor_map, action_config):
    super(mgw_Thread, self).__init__()
    self.name = 'mgw'
    self.daemon = True
    self.enabled = threading.Event()
    if STATUS["mgw"]:
      self.enabled.set()
    self.serial = ser
    self.loop_sleep = loop_sleep
    self.last_gw_ping = 0
    self.gateway_ping_time = gateway_ping_time
    self.db_file = db_file
    self.sensor_map = sensor_map
    self.board_map = board_map
    self.action_config = action_config

  def ping_gateway(self):
    try:
      self.serial.write('1:1')
      time.sleep(1)
    except (IOError, ValueError, serial.serialutil.SerialException) as e:
      LOG.error("Got exception '%' in ping_gateway", e)
    else:
      self.last_gw_ping = int(time.time())

  def _read_sensors_data(self):
    data = {}
    try:
      s_data = self.serial.readline().strip()
      m = self._re_sensor_data.match(s_data)
      # {"board_id": 0, "sensor_type": "temperature", "sensor_data": 2}
      data = m.groupdict()
    except (IOError, ValueError, serial.serialutil.SerialException) as e:
      LOG.error("Got exception '%' in mgw thread", e)
      self.serial.close()
      time.sleep(self.loop_sleep)
      try:
        self.serial.open()
      except (OSError) as e:
        LOG.warning('Failed to open serial')
    except (AttributeError) as e:
      if len(s_data) > 0:
        LOG.debug('> %s', s_data)
    finally:
      if (int(time.time()) - self.last_gw_ping >= self.gateway_ping_time):
        self.ping_gateway()

    return data

  def _save_sensors_data(self, data):
    try:
      self.db.execute(
        "INSERT INTO metrics(board_id, sensor_type, data) VALUES(?, ?, ?)",
        (data['board_id'], data['sensor_type'], data['sensor_data'])
      )
      self.db.commit()
    except (sqlite3.IntegrityError) as e:
      LOG.error("Got exception '%' in mgw thread", e)
    except (sqlite3.OperationalError) as e:
      time.sleep(1 + random.random())
      try:
        self.db.commit()
      except (sqlite3.OperationalError) as e:
        LOG.error("Got exception '%' in mgw thread", e)

  def run(self):
    LOG.info('Starting')
    self.db = connect_db(self.db_file)

    while True:
      self.enabled.wait()

      sensor_data = self._read_sensors_data()
      if not sensor_data:
        continue

      LOG.debug("Got data from serial '%s'", sensor_data)

      self._save_sensors_data(sensor_data)

      sensor_type = sensor_data['sensor_type']

      sensor_config = self.sensor_map.get(sensor_type)
      if not sensor_config or not sensor_config.get('action'):
        LOG.debug("Missing sensor_map/action for sensor_type '%s'", sensor_type)
        continue

      board_id = str(sensor_data['board_id'])
      sensor_data['board_desc'] = self.board_map[board_id]
      action_helper(sensor_data, sensor_config, self.action_config)


STATUS = {
  "armed": 1,
  "msd": 1,
  "mgw": 1,
  "fence": 1,
}

ACTION_STATUS = {}

LOG = logging.getLogger(__name__)


def main():
  parser = argparse.ArgumentParser(description='Moteino gateway')
  parser.add_argument('--dir', required=True, help='Root directory, should cotains *.config.json')
  parser.add_argument('--create-db', required=False, help='Crate mgw database. CAUTION: IT WILL REMOVE OLD DATA', action="store_true")
  parser.add_argument('--sync-db-desc', required=False, help='Sync boards description', action="store_true")
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.config.json')

  if args.create_db or args.sync_db_desc:
    create_db(conf['db_file'], args.dir, args.create_db)
    sys.exit(0)

  create_logger(conf['logging']['level'])

  mgmt = mgmt_Thread(appdir=args.dir)
  mgmt.start()


if __name__ == "__main__":
  main()
