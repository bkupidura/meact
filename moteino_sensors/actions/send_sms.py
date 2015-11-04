import logging

import requests


LOG = logging.getLogger(__name__)


def send_sms(data, action_config):
  if not action_config.get('enabled'):
    return False

  if 'message' in data:
    msg = data['message']
  else:
    msg = '{sensor_type} on board {board_desc} ({board_id}) reports value {sensor_data}'.format(**data)

  LOG.info('Sending SMS')

  url = action_config['endpoint']
  params = {
      'username': action_config['user'],
      'password': action_config['password'],
      'msisdn': action_config['recipient'],
      'message': msg,
  }

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
