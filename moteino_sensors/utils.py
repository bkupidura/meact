from argparse import ArgumentParser
import json
import logging
import os
import pkgutil
import requests
import sys

from cerberus import Validator, cerberus

from moteino_sensors import actions

LOG = logging.getLogger(__name__)
logging.getLogger("requests").setLevel(logging.CRITICAL)
requests.packages.urllib3.disable_warnings()

def load_config(config_name):
  if not os.path.isfile(config_name):
    raise KeyError('Config {} is missing'.format(config_name))

  with open(config_name) as json_config:
    config = json.load(json_config)

  return config


class ActionValidator(Validator):
  def _validate_action(self, field, value):
      if not isinstance(value.get('name'), cerberus._str_type):
        self._error(field, "Must be action")
      failback = value.get('failback')
      if failback:
        for f in failback:
          self._validate_action(field, f)

  def _validate_isaction(self, isaction, field, value):
    if isaction:
      self._validate_action(field, value)


def validate_sensor_data(data):
  schema = {'board_id': {'required': True, 'empty': False,
                'type': 'string', 'regex': '^[a-zA-Z0-9]+$'},
            'sensor_type': {'required': True, 'empty': False, 'type': 'string'},
            'sensor_data': {'required': True, 'empty': False, 'type': 'string'}}
  v = Validator()
  return v.validate(data, schema)


def validate_sensor_config(data):
  schema = {'action_interval': {'required': True, 'type': 'integer', 'min': 0},
            'check_if_armed': {'required': True, 'type': 'dict', 'schema': {
                'default': {'required': True, 'anyof':
                    [{'type': 'integer', 'min': 0, 'max': 1},
                     {'type': 'boolean'}]},
                'except': {'required': True, 'type': 'list', 'schema':
                    {'empty': False, 'type': 'string', 'regex': '^[a-zA-Z0-9]+$'}}}},
            'action': {'required': True, 'type': 'list', 'schema':
                {'isaction': True, 'type': 'dict'},
                'noneof': [{'type': 'list', 'items': []}]},
            'threshold': {'required': True, 'empty': False, 'type': 'string'},
            'fail_count': {'required': True, 'type': 'integer', 'min': 0},
            'message_template': {'required': True, 'empty': False, 'type': 'string'},
            'fail_interval': {'required': True, 'type': 'integer', 'min': 0},
            'id': {'required': True, 'type': 'string', 'empty': False},
            'action_config': {'required': True, 'type': 'dict', 'valueschema':
                {'type': 'dict'}},
            'board_ids': {'required': True, 'type': 'list', 'schema':
                {'empty': False, 'type': 'string', 'regex': '^[a-zA-Z0-9]+$'}}
            }
  v = ActionValidator()
  return v.validate(data, schema)


def create_logger(conf=None):
  if conf is None:
    conf = {}

  level = conf.get('level', logging.INFO)
  log_file = conf.get('file')

  logger = logging.getLogger()
  logger.setLevel(level)
  formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

  if log_file:
    handler = logging.FileHandler(log_file)
  else:
    handler = logging.StreamHandler(sys.stdout)

  handler.setFormatter(formatter)
  logger.addHandler(handler)


def create_arg_parser(description):
  parser = ArgumentParser(description=description)
  parser.add_argument('--dir', required=True, help='Root directory, should cotains *.config.json')
  return parser


def http_request(url, method='GET', params=None, data=None, auth=None, headers=None, verify_ssl=False, timeout=2):
  try:
    req = requests.request(method, url, params=params,
            data=data, headers=headers, auth=auth, verify=verify_ssl, timeout=timeout)
    req.raise_for_status()
  except (requests.HTTPError, requests.ConnectionError, requests.exceptions.Timeout) as e:
    LOG.error('Fail to connect to url %s', e)
    return None

  return req


def load_json(data):
  try:
    return json.loads(data)
  except (ValueError, TypeError) as e:
    return {}


def load_actions():
    mapping = {}

    prefix = actions.__name__ + '.'
    for _, action_name, _ in pkgutil.iter_modules(actions.__path__):
        action_module = __import__(prefix + action_name,
                                   globals(), locals(), fromlist=[action_name, ])
        action_func = getattr(action_module, action_name)
        timeout = getattr(action_module, 'TIMEOUT', 10)
        mapping[action_name] = {'func': action_func, 'timeout': timeout}
        # TODO(prmtl): chec with 'inspect.getargspec' if method accepts correct arguments
    return mapping


