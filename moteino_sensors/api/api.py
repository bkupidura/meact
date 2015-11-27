#!/usr/bin/env python
import json
import os
import time

import bottle
import netaddr

from moteino_sensors import mqtt
from moteino_sensors import utils
from moteino_sensors import database


app = bottle.Bottle()

@app.hook('after_request')
def after_request():
  bottle.response.headers['Access-Control-Allow-Origin'] = '*'


@app.hook('before_request')
def before_request():
  client_ip = bottle.request.environ['REMOTE_ADDR']
  allowed = bool(netaddr.all_matching_cidrs(client_ip, app.config['appconfig']['allowed_cidrs']))
  if not allowed:
    raise bottle.HTTPError(403, 'Forbidden')


@app.route('/')
@app.route('/front')
@app.route('/front/')
def redirect2index():
  bottle.redirect('/front/index.html')


@app.route('/front/<filepath:path>')
def static(filepath):
  return bottle.static_file(filepath, root=app.config['appconfig']['static_dir'])


@app.route('/api/action/status')
def get_action_status():
  return app.config['mqtt'].status


@app.route('/api/action/status', method=['POST'])
def set_action_status():
  data = bottle.request.json
  if data:
    app.config['mqtt'].publish_status(data)


@app.route('/api/action/mqtt', method=['POST'])
def set_action_mqtt():
  if (bottle.request.json):
    topic = bottle.request.json.get('topic')
    data = bottle.request.json.get('data')
    retain = bottle.request.json.get('retain', False)
    if topic and data:
      app.config['mqtt'].publish(topic, data, retain)


@app.route('/api/node', method=['GET', 'POST'])
@app.route('/api/node/', method=['GET', 'POST'])
@app.route('/api/node/<board_id>', method=['GET', 'POST'])
def get_nodes(board_id=False):
  now = int(time.time())
  start = now - 60 * 60 * 1
  end = now

  if (bottle.request.json):
    start = bottle.request.json.get('start', start)
    end = bottle.request.json.get('end', end)

  boards = database.get_boards(app.config['db'])

  output = list()
  for board in boards:
    output.append({"name": board.board_id, "desc": board.board_desc, "data": []})

    metrics = database.get_last_metrics(app.config['db'], board_ids=board.board_id, start=start, end=end)

    for metric in metrics:
      output[-1]['data'].append((metric.sensor_type, metric.sensor_data))

  return json.dumps(output)


@app.route('/api/graph/<graph_type>', method=['GET', 'POST'])
def get_graph(graph_type='uptime'):
  now = int(time.time())
  start = now - 60 * 60 * 24
  end = now
  last_available = 0

  if (bottle.request.json):
    start = bottle.request.json.get('start', start)
    end = bottle.request.json.get('end', end)
    last_available = bottle.request.json.get('last_available', last_available)

  boards = database.get_boards(app.config['db'])

  board_ids = [board.board_id for board in boards]
  board_desc = dict((board.board_id, board.board_desc) for board in boards)

  last_metrics = database.get_last_metrics(app.config['db'], board_ids=board_ids, sensor_type=graph_type)

  output = list()

  for last_metric in last_metrics:
    output.append({"name": board_desc[last_metric.board_id], "data": []})

    metrics = database.get_metrics(app.config['db'], board_ids=last_metric.board_id, sensor_type=graph_type, start=start, end=end)
    if not metrics and last_available:
      metrics = database.get_metrics(app.config['db'], board_ids=last_metric.board_id, sensor_type=graph_type, last_available=last_available)

    for metric in metrics:
      data = ((metric.last_update * 1000), float(metric.sensor_data))
      output[-1]['data'].append(data)

  return json.dumps(output)


class SyncThread(mqtt.MqttThread):
  def __init__(self, conf):
    super(SyncThread, self).__init__()
    self.app_config = conf
    self.daemon = True
    self.mqtt_config = conf['mqtt']
    self.start_mqtt()

  def run(self):
    while True:
      self.mqtt.loop()


def main():
  parser = utils.create_arg_parser('Moteino gateway API')
  args = parser.parse_args()

  api_config = utils.load_config(args.dir + '/global.config.json')

  # static_dir in config file should be specified only if
  # static files are located somewhere else than app package
  if not api_config.get('static_dir'):
      api_config['static_dir'] = os.path.join(os.path.dirname(__file__), 'static')

  app.config['appconfig'] = api_config

  app.config['mqtt'] = SyncThread(app.config['appconfig'])
  app.config['mqtt'].start()

  app.config['db'] = database.connect(app.config['appconfig']['db'])

  app.run(host='0.0.0.0', port=8080, debug=app.config['appconfig']['debug'])


if __name__ == "__main__":
  main()
