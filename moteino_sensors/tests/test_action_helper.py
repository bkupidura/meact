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
  action_details = copy.deepcopy(default_action)
  action_details['check_if_armed'] = check_if_armed

  ada = gateway.ActionDetailsAdapter(action_details)

  assert ada.should_check_if_armed(board_id) == expected

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
  action_details = copy.deepcopy(default_action)
  action_details['action_interval'] = action_interval

  ada = utils.validate_action_details(action_details)

  assert ada == expected

@pytest.mark.parametrize('fail_count, expected', integer_bigger_than_0_test_data)
def test_fail_count(fail_count, expected):
  action_details = copy.deepcopy(default_action)
  action_details['fail_count'] = fail_count

  ada = utils.validate_action_details(action_details)

  assert ada == expected

@pytest.mark.parametrize('fail_interval, expected', integer_bigger_than_0_test_data)
def test_fail_interval(fail_interval, expected):
  action_details = copy.deepcopy(default_action)
  action_details['fail_interval'] = fail_interval

  ada = utils.validate_action_details(action_details)

  assert ada == expected

@pytest.mark.parametrize('index, expected', integer_bigger_than_0_test_data)
def test_index(index, expected):
  action_details = copy.deepcopy(default_action)
  action_details['index'] = index

  ada = utils.validate_action_details(action_details)

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
  action_details = copy.deepcopy(default_action)
  action_details['threshold'] = threshold

  ada = utils.validate_action_details(action_details)

@pytest.mark.parametrize('message_template, expected', not_empty_string_test_data)
def test_message_template(message_template, expected):
  action_details = copy.deepcopy(default_action)
  action_details['message_template'] = message_template

  ada = utils.validate_action_details(action_details)

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
  action_details = copy.deepcopy(default_action)
  action_details['check_if_armed']['default'] = check_if_armed_default

  ada = utils.validate_action_details(action_details)

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
  action_details = copy.deepcopy(default_action)
  action_details['check_if_armed']['except'] = check_if_armed_except

  ada = utils.validate_action_details(action_details)

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
  action_details = copy.deepcopy(default_action)
  action_details['action'] = action

  ada = utils.validate_action_details(action_details)
