import json
import logging
import os
import pkgutil
import sys

from cerberus import Validator, cerberus

from moteino_sensors import actions

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
  schema = {'board_id': {'type': 'string'},
            'sensor_type': {'type': 'string'},
            'sensor_data': {'type': 'string'}}
  v = Validator()
  return v.validate(data, schema)


def validate_action_details(data):
  schema = {'action_interval': {'type': 'integer', 'min': 0},
            'check_if_armed': {'type': 'dict', 'schema': {
                'default': {'anyof':
                    [{'type': 'integer', 'min': 0, 'max': 1},
                     {'type': 'boolean'}]},
                'except': {'type': 'list', 'schema': {'type': 'integer', 'min': 0, 'max': 255}}}},
            'action': {'type': 'list', 'schema':
                {'type': 'dict', 'isaction': True}},
            'threshold': {'type': 'string'},
            'fail_count': {'type': 'integer', 'min': 0},
            'message_template': {'type': 'string'},
            'fail_interval': {'type': 'integer', 'min': 0}
            }
  v = ActionValidator()
  return v.validate(data, schema)


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


def load_json(data):
  try:
    return json.loads(data)
  except (ValueError) as e:
    return {}


def _load_actions():
    mapping = {}

    prefix = actions.__name__ + '.'
    for _, action_name, _ in pkgutil.iter_modules(actions.__path__):
        action_module = __import__(prefix + action_name,
                                   globals(), locals(), fromlist=[action_name, ])
        action_func = getattr(action_module, action_name)
        timeout = getattr(action_module, 'TIMEOUT', None)
        mapping[action_name] = {'func': action_func, 'timeout': timeout}
        # TODO(prmtl): chec with 'inspect.getargspec' if method accepts correct arguments
    return mapping


ACTIONS_MAPPING = _load_actions()
