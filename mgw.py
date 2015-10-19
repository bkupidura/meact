#!/usr/local/bin/python
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
# jeżeli masz jakieś zalezności spoza biblioteki standardowej,
# to zapisz sobie je w pliku requirements.txt i używaj pip do ich
# instalacji https://pip.readthedocs.org/en/stable/user_guide/#requirements-files
import argparse
import requests
import smtplib


# mozesz zainicjalizowac logger przez:
#
# LOG = logging.getLogger(__name__)
#
# i potem używać go w pliku
#
# LOG.debug('123')
#
# potem w "main" swojej aplikacji odpalasz tylko swoją
# funckje "create_logger" i już nie musisz przekazywać
# loggera do każdej funkcji:
#
# if __name__ == "__main__":
#   parser = argparse.ArgumentParser(description='Moteino gateway')
#   parser.add_argument('--dir', required=True, help='Root directory, should cotains *.config.json')
#   args = parser.parse_args()
#
#   create_logger()
#
#   mgmt = mgmt_Thread(appdir=args.dir)
#   mgmt.run()

def log(logger, data, action_config):
  logger.info("Log action for data: {}".format(data))
  return True

# hint: do funkcji przekazuj tylko tą konfigurację, której potrzebuje, czyli byłoby w tym przypadku, tak:
#
# sms_conf = action_confg['send_sms']
#
# def send_sms(data, conf):
# ...
#
# i wywołać:
#
# send_sms(data, sms_conf)
#
#
# ewentualnie, gdy musisz/chcesz przekazać całość, to wtedy, zeby nie pisać
# cały czas "action_config['send_sms']['costam'] przypisz to do zmienej i do niej się odwoływać:
# sms_conf = action_config['send_sms']
# sms_conf['costam']
def send_sms(logger, data, action_config):
  if not action_config['send_sms']['enabled']:
    return False

  if 'message' in data:
    msg = data['message']
  else:
    # hint: w formatowaniu możesz używać kluczy ze słownika:
    #
    #  msg = "{sensor_type} {board_desc} ...".foramt(**data)
    #
    msg = '{} on board {} ({}) reports value {}'.format(data['sensor_type'],
            data['board_desc'], data['board_id'], data['sensor_data'])

  logger.debug('Sending SMS')

  url = action_config['send_sms']['endpoint']
  params = {'username': action_config['send_sms']['user'],
          'password': action_config['send_sms']['password'],
          'msisdn': action_config['send_sms']['recipient'],
          'message': msg}

  logging.getLogger("urllib3").setLevel(logging.CRITICAL)
  try:
    r = requests.get(url, params=params, timeout=5)
    r.raise_for_status()
  except (requests.HTTPError, requests.ConnectionError) as e:
    logger.warning('Fail to send SMS: {}'.format(e))
    return False

  result = r.text.split('|')
  if result[0] != '0':
    logger.warning('Fail to send SMS: {} {}'.format(result[0], result[1]))
    return False

  return True

def send_mail(logger, data, action_config):
  if not action_config['send_mail']['enabled']:
    return False

  if 'message' in data:
    msg = data['message']
  else:
    msg = '{} on board {} ({}) reports value {}'.format(data['sensor_type'],
            data['board_desc'], data['board_id'], data['sensor_data'])

  logger.debug('Sending mail')

  message = "From: {}\nTo: {}\nSubject: {}\n\n{}\n\n".format(action_config['send_mail']['sender'],
          action_config['send_mail']['recipient'],
          action_config['send_mail']['subject'],
          msg)
  # hint: jeżeli nie chcesz stawiać sobie smtp, to możesz np. użyć Mandrilla (http://mandrill.com/)
  # tl;dr wysyłka e-maili po HTTP API
  try:
    s = smtplib.SMTP(action_config['send_mail']['host'], action_config['send_mail']['port'], timeout=5)
    s.starttls()
    s.login(action_config['send_mail']['user'], action_config['send_mail']['password'])
    s.sendmail(action_config['send_mail']['sender'], action_config['send_mail']['recipient'], message)
    s.quit()
  except (socket.gaierror, socket.timeout, smtplib.SMTPAuthenticationError, smtplib.SMTPDataError) as e:
    logger.warning('Fail to send mail: {}'.format(e))
    return False
  else:
    return True

def action_execute(logger, data, action, action_config):
  result = 0
  for a in action:
    logger.debug('Action execute for: {}'.format(a))
    if not eval(a['name'])(logger, data, action_config):
      if 'failback' in a:
        result += action_execute(logger, data, a['failback'], action_config)
    else:
      result += 1
  return result

def action_helper(logger, data, action_details, action_config=None):
  action_details.setdefault('check_if_armed', True)
  action_details.setdefault('action_interval', 0)
  action_details.setdefault('threshold', 'lambda x: True')
  action_details.setdefault('fail_count', 0)
  action_details.setdefault('fail_interval', 600)

  logger.debug('Action helper for data: {} action_details: {}'.format(data, action_details))
  now = int(time.time())

  action_status.setdefault(data['board_id'], {})
  action_status[data['board_id']].setdefault(data['sensor_type'], {'last_action': 0, 'last_fail': []})

  action_status[data['board_id']][data['sensor_type']]['last_fail'] = \
    [i for i in action_status[data['board_id']][data['sensor_type']]['last_fail'] if now - i < action_details['fail_interval']]

  if (action_details['check_if_armed']) and (not STATUS['armed']):
    return

  if not eval(action_details['threshold'])(data['sensor_data']):
    return

  if len(action_status[data['board_id']][data['sensor_type']]['last_fail']) <= action_details['fail_count']-1:
    action_status[data['board_id']][data['sensor_type']]['last_fail'].append(now)
    return

  if (now - action_status[data['board_id']][data['sensor_type']]['last_action'] <= action_details['action_interval']):
    return

  if action_execute(logger, data, action_details['action'], action_config):
    action_status[data['board_id']][data['sensor_type']]['last_action'] = now

def load_config(config_name):
  if not os.path.isfile(config_name):
    raise KeyError('Config {} is missing'.format(config_name))

  with open(config_name) as json_config:
    config = json.load(json_config)

  return config

def connect_db(db_file):
  db = sqlite3.connect(db_file)
  return db

def create_db(db_file, appdir, create_sensor_table=False):
  board_map = load_config(appdir + '/boards.config.json')
  db = connect_db(db_file)
  db.execute("DROP TABLE IF EXISTS board_desc");
  db.execute('''CREATE TABLE board_desc(board_id TEXT PRIMARY KEY, board_desc TEXT)''');

  for key in board_map:
    db.execute("INSERT INTO board_desc(board_id, board_desc) VALUES(?, ?)",
      (key, board_map[key]))
  db.commit()

  if (create_sensor_table):
    db.execute("DROP TABLE IF EXISTS metrics")
    db.execute('''CREATE TABLE metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, board_id TEXT, sensor_type TEXT,
      last_update TIMESTAMP DEFAULT (STRFTIME('%s', 'now')), data TEXT DEFAULT NULL)''')

    db.execute("DROP INDEX IF EXISTS idx_board_id")
    db.execute("CREATE INDEX idx_board_id ON metrics (board_id, sensor_type, last_update, data)")

  db.execute("DROP TABLE IF EXISTS last_metrics")
  db.execute("CREATE TABLE last_metrics (board_id TEXT, sensor_type TEXT, last_update TIMESTAMP, data TEXT)")

  db.execute("DROP TRIGGER IF EXISTS insert_metric")
  db.execute('''CREATE TRIGGER insert_metric INSERT ON metrics WHEN NOT EXISTS(SELECT 1 FROM last_metrics
    WHERE board_id=new.board_id and sensor_type=new.sensor_type) BEGIN INSERT into last_metrics
    values(new.board_id, new.sensor_type, new.last_update, new.data); END''')

  db.execute("DROP TRIGGER IF EXISTS update_metric")
  db.execute('''CREATE TRIGGER update_metric INSERT ON metrics WHEN EXISTS(SELECT 1 FROM last_metrics
    WHERE board_id=new.board_id and sensor_type=new.sensor_type) BEGIN UPDATE last_metrics
    SET data=new.data, last_update=new.last_update WHERE board_id==new.board_id
    and sensor_type==new.sensor_type; END''')

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

  return logger

class mgmt_Thread(threading.Thread):
  def __init__(self, appdir):
    # super(mgmt_Thread, self).__init__()
    threading.Thread.__init__(self)
    # a to nie działa tak jak chcesz?
    # self.name = 'mgmt'
    threading.current_thread().name = 'mgmt'
    self.daemon = True

    conf = load_config(appdir + '/global.config.json')
    board_map = load_config(appdir + '/boards.config.json')
    sensor_map = load_config(appdir + '/sensors.config.json')

    self.socket = conf['mgmt_socket']
    self.serial = serial.Serial(conf['serial']['device'],
            conf['serial']['speed'],
            timeout=conf['serial']['timeout'])
    self.logger = create_logger(conf['logging']['level'],
            conf['logging'].get('file'))

    self.msd = failure_Thread(name='msd', logger=self.logger,
            loop_sleep=conf['msd']['loop_sleep'],
            db_file=conf['db_file'],
            action_interval=conf['msd']['action_interval'],
            query=conf['msd']['query'],
            action=conf['msd']['action'],
            board_map=board_map,
            action_config=conf['action_config']) #Missing sensor detector
    self.mgw = mgw_Thread(logger=self.logger, ser=self.serial,
            loop_sleep=conf['loop_sleep'],
            gateway_ping_time=conf['gateway_ping_time'],
            db_file=conf['db_file'],
            board_map=board_map,
            sensor_map=sensor_map,
            action_config=conf['action_config'])

  def run(self):
    self.logger.info('Starting')

    self.msd.start()
    self.mgw.start()

    if os.path.exists(self.socket):
      os.remove(self.socket)

    self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    self.server.bind(self.socket)
    self.server.listen(1)
    while True:
      conn, addr = self.server.accept()
      data = conn.recv(1024)
      if data:
        try:
          data = json.loads(data)
        except (ValueError) as e:
          # hint: jak używasz loggera, to powinno się podstawianie wartości zostawić
          # loggerowi, jeżeli będą jakieś błędy, to wtedy on sobie z nimi poradzi i nie wywali ci skryptu:
          # logger.warning("Got exception %s while reading from socket", e)
          self.logger.warning('Got exception {} while reading from socket'.format(e))
          continue
        if 'action' in data:
          self.logger.info('Got {} on mgmt socket'.format(data))
          if data['action'] == 'status':
            conn.send(json.dumps(STATUS))
          elif data['action'] == 'send' and 'data' in data:
            try:
              # hint: .format() jest czytelniejszy:
              # r_cmd = "{node_id}:{cmd}".format(node_id=data[...], cmd=data[...])
              r_cmd = str(data['data']['nodeid'])+":"+str(data['data']['cmd'])
              self.serial.write(r_cmd)
            except (IOError, ValueError, serial.serialutil.SerialException) as e:
              self.logger.error('Fail to send command {} to remote node'.format(r_cmd))
          elif data['action'] == 'set' and 'data' in data:
            for key in data['data']:
              STATUS[key] = data['data'][key]
              if key == 'mgw_enabled':
                self.mgw.enabled.set() if data['data'][key] else self.mgw.enabled.clear()
              elif key == 'msd_enabled':
                self.msd.enabled.set() if data['data'][key] else self.msd.enabled.clear()

      conn.close()

class failure_Thread(threading.Thread):
  def __init__(self, name, logger, loop_sleep, db_file, action_interval,
          query, action, board_map, action_config):
    threading.Thread.__init__(self)
    self.name = name
    self.daemon = True
    self.enabled = threading.Event()
    if STATUS[name+'_enabled']:
      self.enabled.set()
    self.logger = logger
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
    action_details = {'check_if_armed': False, 'action_interval': self.action_interval, 'action': self.action}

    if self.name == 'msd':
      message = 'No update from {} ({}) since {} seconds'.format(self.board_map[board_id],
              board_id, now - value)

      data['message'] = message
      action_helper(self.logger, data, action_details, self.action_config)

  def run(self):
    self.logger.info('Starting')
    self.db = connect_db(self.db_file)
    while True:
      self.enabled.wait()
      now = int(time.time())

      for board_id, value in self.db.execute(self.query):
        self.handle_failed(board_id, value)

      time.sleep(self.loop_sleep)

class mgw_Thread(threading.Thread):
  def __init__(self, logger, ser, loop_sleep, gateway_ping_time,
          db_file, board_map, sensor_map, action_config):
    threading.Thread.__init__(self)
    self.name = 'mgw'
    self.daemon = True
    self.enabled = threading.Event()
    if STATUS["mgw_enabled"]:
      self.enabled.set()
    self.logger = logger
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
      self.logger.error('Failed to get measure from gateway: {}'.format(e))
    else:
      self.last_gw_ping = int(time.time())

  def run(self):
    self.logger.info('Starting')
    self.db = connect_db(self.db_file)

    #[ID][metric:value] / [10][voltage:3.3]
    re_data = re.compile('\[(\d+)\]\[(.+):(.+)\]')

    data = {}

    while True:
      self.enabled.wait()
      try:
        s_data = self.serial.readline().strip()
        m = re_data.match(s_data)
        #{"board_id": 0, "sensor_type": "temperature", "sensor_data": 2}
        #
        # to może być: data['board_id'], data['sensor_type'], data['sensor_data'] = m.groups()
        # doc: https://docs.python.org/2/library/re.html#re.MatchObject.groups
        data['board_id'], data['sensor_type'], data['sensor_data'] = [m.group(i) for i in range(1, 4)]

        # regexpy mogą mieć nazwane grupy: (?P<nazwa>regex)
        #
        # re_data = re.compile('\[(?P<id>\d+)\]\[(?P<sensor>.+):(?P<data>.+)\]')
        # m = re_data.match(s_match)
        # m.groupdict() => (na przykład) {'data': '3.3', 'id': '10', 'sensor': 'voltage'}
        #
        # doc: https://docs.python.org/2/library/re.html#re.MatchObject.groupdict
      except (IOError, ValueError, serial.serialutil.SerialException) as e:
        self.logger.error('Got exception {} while reading from serial'.format(e))
        self.serial.close()
        time.sleep(self.loop_sleep)
        try:
          self.serial.open()
        except (OSError) as e:
          self.logger.warning('Failed to open serial')
        continue
      except (AttributeError) as e:
        if len(s_data) > 0:
          self.logger.debug('> {}'.format(s_data))
        continue
      finally:
        if (int(time.time()) - self.last_gw_ping >= self.gateway_ping_time):
          self.ping_gateway()

      self.logger.debug('Got data from serial {}'.format(data))

      try:
        self.db.execute("INSERT INTO metrics(board_id, sensor_type, data) VALUES(?, ?, ?)",
                (data['board_id'], data['sensor_type'], data['sensor_data']))
        self.db.commit()
      except (sqlite3.IntegrityError) as e:
        self.logger.error('Integrity error {}'.format(e))
      except (sqlite3.OperationalError) as e:
        time.sleep(1+random.random())
        try:
          self.db.commit()
        except (sqlite3.OperationalError) as e:
          self.logger.error('Failed to commit data to DB');

      try:
        action_details = self.sensor_map[data['sensor_type']]
        action_details['action']
      except (KeyError) as e:
        self.logger.debug('Missing sensor_map/action for sensor_type {}'.format(data['sensor_type']))
      else:
        data['board_desc'] = self.board_map[str(data['board_id'])]
        action_helper(self.logger, data, action_details, self.action_config)

STATUS = {
  "armed": 1,
  "msd_enabled": 1,
  "mgw_enabled": 1,
}
action_status = {}

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Moteino gateway')
  parser.add_argument('--dir', required=True, help='Root directory, should cotains *.config.json')
  args = parser.parse_args()

  mgmt = mgmt_Thread(appdir=args.dir)
  mgmt.run()
