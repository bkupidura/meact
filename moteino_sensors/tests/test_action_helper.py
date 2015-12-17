import copy
import os
import sys

import pytest

from moteino_sensors import gateway
from moteino_sensors import utils

default_action = {
  'check_if_armed': {
    'default': True,
    'except': [],
  },
  'action_interval': 0,
  'threshold': 'lambda x: True',
  'fail_count': 0,
  'fail_interval': 0,
  'index': 0,
  'message_template': 'Template message for {board_id}',
  'action': [{'name': 'action'}],
  'action_config': {'action_name': {'test': 10}},
  'board_ids': []
}


board_id = '1'
check_if_armed_test_data = (
  (
    {
      'default': True,
      'except': [],
    },
    True
  ),
  (
    {
      'default': False,
      'except': [],
    },
    False
  ),
  (
    {
      'default': True,
      'except': [board_id, ],
    },
    False
  ),
  (
    {
      'default': False,
      'except': [board_id, ],
    },
    True
  ),
)

@pytest.mark.parametrize('check_if_armed, expected', check_if_armed_test_data)
def test_should_check_if_armed(check_if_armed, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['check_if_armed'] = check_if_armed

  ada = gateway.SensorConfigAdapter(sensor_config)

  assert ada.should_check_if_armed(board_id) == expected

config_for_board_test_data = (
  (
    'asd',
    False
  ),
  (
    ['asd'],
    False
  ),
  (
    ['asd-1'],
    False
  ),
  (
    [],
    True
  ),
  (
    [board_id, ],
    True
  ),
  (
    [board_id, 'asd'],
    True
  ),
)

@pytest.mark.parametrize('board_ids, expected', config_for_board_test_data)
def test_config_for_board(board_ids, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['board_ids'] = board_ids

  ada = gateway.SensorConfigAdapter(sensor_config)

  assert ada.config_for_board(board_id) == expected

board_ids_test_data = (
  (
    ['test'],
    True
  ),
  (
    ['test-1'],
    False
  ),
  (
    '',
    False
  ),
  (
    10,
    False
  ),
  (
    [],
    True
  ),
  (
    [1, ],
    False
  ),
  (
    {},
    False
  ),
  (
    {'test': 10},
    False
  ),
  (
    None,
    False
  ),
  (
    True,
    False
  ),
  (
    False,
    False
  )
)

@pytest.mark.parametrize('board_ids, expected', board_ids_test_data)
def test_board_ids(board_ids, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['board_ids'] = board_ids

  ada = utils.validate_sensor_config(sensor_config)

  assert ada == expected

dict_test_data = (
  (
    {},
    True
  ),
  (
    {'1': 10},
    True
  ),
  (
    {'1': {'1': 'asd'}},
    True
  ),
  (
    [],
    False
  ),
  (
    [1],
    False
  ),
  (
    'asd',
    False
  ),
)

@pytest.mark.parametrize('action_config, expected', dict_test_data)
def test_action_config(action_config, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['action_config'] = action_config

  ada = utils.validate_sensor_config(sensor_config)

  assert ada == expected

integer_bigger_than_0_test_data = (
  (
    10,
    True
  ),
  (
    0,
    True
  ),
  (
    -10,
    False
  ),
  (
    'asd',
    False
  ),
  (
    [],
    False
  ),
  (
    [1, ],
    False
  ),
  (
    {},
    False
  ),
  (
    {'test': 10},
    False
  ),
  (
    None,
    False
  ),
)

@pytest.mark.parametrize('action_interval, expected', integer_bigger_than_0_test_data)
def test_action_interval(action_interval, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['action_interval'] = action_interval

  ada = utils.validate_sensor_config(sensor_config)

  assert ada == expected

@pytest.mark.parametrize('fail_count, expected', integer_bigger_than_0_test_data)
def test_fail_count(fail_count, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['fail_count'] = fail_count

  ada = utils.validate_sensor_config(sensor_config)

  assert ada == expected

@pytest.mark.parametrize('fail_interval, expected', integer_bigger_than_0_test_data)
def test_fail_interval(fail_interval, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['fail_interval'] = fail_interval

  ada = utils.validate_sensor_config(sensor_config)

  assert ada == expected

@pytest.mark.parametrize('index, expected', integer_bigger_than_0_test_data)
def test_index(index, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['index'] = index

  ada = utils.validate_sensor_config(sensor_config)

  assert ada == expected

not_empty_string_test_data = (
  (
    'test',
    True
  ),
  (
    '',
    False
  ),
  (
    10,
    False
  ),
  (
    [],
    False
  ),
  (
    [1, ],
    False
  ),
  (
    {},
    False
  ),
  (
    {'test': 10},
    False
  ),
  (
    None,
    False
  ),
  (
    True,
    False
  ),
  (
    False,
    False
  ),
)

@pytest.mark.parametrize('threshold, expected', not_empty_string_test_data)
def test_threshold(threshold, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['threshold'] = threshold

  ada = utils.validate_sensor_config(sensor_config)

@pytest.mark.parametrize('message_template, expected', not_empty_string_test_data)
def test_message_template(message_template, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['message_template'] = message_template

  ada = utils.validate_sensor_config(sensor_config)

boolean_integer_test_data = (
  (
    True,
    True
  ),
  (
    False,
    True
  ),
  (
    0,
    True
  ),
  (
    1,
    True
  ),
  (
    10,
    False
  ),
  (
    -10,
    False
  ),
  (
    [],
    False
  ),
  (
    [1, ],
    False
  ),
  (
    {},
    False
  ),
  (
    {'test': 10},
    False
  ),
  (
    None,
    False
  ),
)

@pytest.mark.parametrize('check_if_armed_default, expected', boolean_integer_test_data)
def test_check_if_armed_default(check_if_armed_default, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['check_if_armed']['default'] = check_if_armed_default

  ada = utils.validate_sensor_config(sensor_config)

check_if_armed_except_test_data = (
  (
    [],
    True
  ),
  (
    ['test'],
    True
  ),
  (
    ['10', '20'],
    True
  ),
  (
    10,
    False
  ),
  (
    [10],
    False
  ),
  (
    [1, ],
    False
  ),
  (
    {},
    False
  ),
  (
    [{}],
    False
  ),
  (
    {'test': 10},
    False
  ),
  (
    [{'test': 10}],
    False
  ),
  (
    None,
    False
  ),
  (
    [None],
    False
  ),
  (
    True,
    False
  ),
  (
    [True],
    False
  ),
  (
    False,
    False
  ),
  (
    [False],
    False
  ),
)

@pytest.mark.parametrize('check_if_armed_except, expected', check_if_armed_except_test_data)
def test_check_if_armed_default(check_if_armed_except, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['check_if_armed']['except'] = check_if_armed_except

  ada = utils.validate_sensor_config(sensor_config)

action_test_data = (
  (
    [{'name': 'test'}],
    True
  ),
  (
    [{'name': 'test'}, {'name': 'test2'}],
    True
  ),
  (
    [{'name': 'test', 'failback': [{'name': 'test2'}]}, {'name': 'test3'}],
    True
  ),
  (
    [{'name': 'test', 'failback': [{'name': 'test2', 'failback': [{'name': 'test3'}]}, {'name': 'test4'}]}],
    True
  ),
  (
    [],
    False
  ),
  (
    10,
    False
  ),
  (
    [10],
    False
  ),
  (
    [1, ],
    False
  ),
  (
    {},
    False
  ),
  (
    [{}],
    False
  ),
  (
    {'test': 10},
    False
  ),
  (
    [{'test': 10}],
    False
  ),
  (
    None,
    False
  ),
  (
    [None],
    False
  ),
  (
    True,
    False
  ),
  (
    [True],
    False
  ),
  (
    False,
    False
  ),
  (
    [False],
    False
  ),
  (
    [{'name': 'test'}, {'action': 'test2'}],
    False
  ),
  (
    [{'name': 10}],
    False
  ),
  (
    [{'name': None}],
    False
  ),
  (
    [{'name': False}],
    False
  ),
  (
    [{'name': 'test', 'failback': [{'action': 'test2'}]}, {'name': 'test3'}],
    False
  ),
)

@pytest.mark.parametrize('action, expected', action_test_data)
def test_action(action, expected):
  sensor_config = copy.deepcopy(default_action)
  sensor_config['action'] = action

  ada = utils.validate_sensor_config(sensor_config)
