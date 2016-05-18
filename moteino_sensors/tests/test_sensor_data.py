import copy
import os
import sys

import pytest

from moteino_sensors import utils

default_metric = {
  'board_id': '10',
  'sensor_type': 'voltage',
  'sensor_data': '123'
}

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

@pytest.mark.parametrize('board_id, expected', not_empty_string_test_data)
def test_board_id(board_id, expected):
  metric = copy.deepcopy(default_metric)
  metric['board_id'] = board_id

  ada, data = utils.validate_sensor_data(metric)

  assert ada == expected

@pytest.mark.parametrize('sensor_type, expected', not_empty_string_test_data)
def test_sensor_type(sensor_type, expected):
  metric = copy.deepcopy(default_metric)
  metric['sensor_type'] = sensor_type

  ada, data = utils.validate_sensor_data(metric)

  assert ada == expected

@pytest.mark.parametrize('sensor_data, expected', not_empty_string_test_data)
def test_sensor_data(sensor_data, expected):
  metric = copy.deepcopy(default_metric)
  metric['sensor_data'] = sensor_data

  ada, data = utils.validate_sensor_data(metric)

  assert ada == expected
