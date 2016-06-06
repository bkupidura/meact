#!/usr/bin/env python
import json
import logging
import os
import time

import bottle
import netaddr

from moteino_sensors import mqtt
from moteino_sensors import utils
from moteino_sensors import database


app = bottle.Bottle()
logging.getLogger('tornado.access')

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
  static_content = bottle.static_file(filepath, root=app.config['appconfig']['user_static_dir'])
  if static_content._status_code == 404:
    static_content = bottle.static_file(filepath, root=app.config['appconfig']['static_dir'])

  return static_content


@app.route('/api/mqtt', method=['POST'])
def post_mqtt():
  if (bottle.request.json):
    topic = bottle.request.json.get('topic')
    data = bottle.request.json.get('data')
    retain = bottle.request.json.get('retain', False)
    if topic and data:
      app.config['mqtt'].publish(topic, data, retain)


@app.route('/api/status', method=['GET'])
def get_status():
  return app.config['mqtt'].status


@app.route('/api/status', method=['POST'])
def post_status():
  data = bottle.request.json
  if data:
    app.config['mqtt'].publish_status(data)

def handle_board_endpoint(board_id = None, sensor_type = None, start = None, end = None):
  boards = database.get_boards(app.config['db'], board_ids=board_id)

  board_ids = [board.board_id for board in boards]
  board_desc = dict((board.board_id, board.board_desc) for board in boards)

  last_metrics = database.get_last_metrics(app.config['db'], board_ids=board_ids, start=start, end=end, sensor_type=sensor_type)

  output = dict()

  for metric in last_metrics:
    output.setdefault(metric.board_id, {'id': metric.board_id,
        'desc': board_desc[metric.board_id],
        'data': {},
        'last_update': 0
    })
    output[metric.board_id]['data'][metric.sensor_type] = metric.sensor_data
    if output[metric.board_id]['last_update'] < metric.last_update:
      output[metric.board_id]['last_update'] = metric.last_update

  return output

@app.route('/api/board', method=['GET'])
@app.route('/api/board/', method=['GET'])
@app.route('/api/board/<board_id>', method=['GET'])
def get_board(board_id = None):
  output = handle_board_endpoint(board_id)
  return json.dumps(output.values())


@app.route('/api/board', method=['POST'])
@app.route('/api/board/', method=['POST'])
@app.route('/api/board/<board_id>', method=['POST'])
def post_board(board_id = None):
  if (bottle.request.json):
    board_id = bottle.request.json.get('board_id', board_id)
    sensor_type = bottle.request.json.get('sensor_type', None)
    start = bottle.request.json.get('start', None)
    end = bottle.request.json.get('end', None)

    output = handle_board_endpoint(board_id, sensor_type, start, end)
  else:
    output = handle_board_endpoint(board_id)

  return json.dumps(output.values())


def handle_graph_endpoint(board_id = None, graph_type = None, start = None, end = None, last_available = None):
  boards = database.get_boards(app.config['db'])

  board_desc = dict((board.board_id, board.board_desc) for board in boards)

  last_metrics = database.get_last_metrics(app.config['db'], board_ids=board_id, sensor_type=graph_type)

  output = list()

  for last_metric in last_metrics:
    output.append({
        'id': last_metric.board_id,
        'desc': board_desc[last_metric.board_id],
        'data': []
    })

    metrics = database.get_metrics(app.config['db'], board_ids=last_metric.board_id, sensor_type=graph_type, start=start, end=end)
    if not metrics and last_available:
      metrics = database.get_metrics(app.config['db'], board_ids=last_metric.board_id, sensor_type=graph_type, last_available=last_available)

    for metric in metrics:
      data = (metric.last_update*1000, float(metric.sensor_data))
      output[-1]['data'].append(data)

  return output

@app.route('/api/graph/<graph_type>', method=['GET'])
def get_graph(graph_type = None):
  now = int(time.time())
  output = handle_graph_endpoint(graph_type = graph_type, start = now - 60*60)
  return json.dumps(output)

@app.route('/api/graph/<graph_type>', method=['POST'])
def post_graph(graph_type = None):
  now = int(time.time())
  if (bottle.request.json):
    board_id = bottle.request.json.get('board_id', None)
    start = bottle.request.json.get('start', now - 60*60)
    end = bottle.request.json.get('end', None)
    last_available = bottle.request.json.get('last_available', None)

    output = handle_graph_endpoint(board_id, graph_type, start, end, last_available)
  else:
    output = handle_graph_endpoint(graph_type = graph_type, start = now - 60*60)

  return json.dumps(output)


class Api(mqtt.Mqtt):
  def __init__(self, conf):
    super(Api, self).__init__()
    self.name = 'api'
    self.mqtt_config = conf['mqtt']
    self.start_mqtt()


def main():
  parser = utils.create_arg_parser('Moteino gateway API')
  args = parser.parse_args()

  api_config = utils.load_config(args.dir + '/global.config.json')

  # static_dir in config file should be specified only if
  # static files are located somewhere else than app package
  if not api_config.get('static_dir'):
      api_config['static_dir'] = os.path.join(os.path.dirname(__file__), 'static')

  app.config['appconfig'] = api_config

  app.config['mqtt'] = Api(app.config['appconfig'])
  app.config['mqtt'].loop_start()

  utils.create_logger()

  app.config['db'] = database.connect(app.config['appconfig']['db_string'])

  app.run(host='0.0.0.0', port=8080, debug=app.config['appconfig']['debug'], server='tornado')


if __name__ == "__main__":
  main()
