import logging
import requests
import sys


LOG = logging.getLogger(__name__)
TIMEOUT=5


logging.getLogger("requests").setLevel(logging.CRITICAL)
requests.packages.urllib3.disable_warnings()

def send_ifttt_maker(data, action_config):
  """Send request to IFTTT Maker channel

  Sensor_type will be used as event name.
  {{value1}} will be set to data['message']
  {{value2}} will be set to data['sensor_data']
  {{value3}} will be set to data['board_id']

  MGW configuration:
  action_config = {
    "endpoint": "https://maker.ifttt.com/trigger",
    "auth_key": "authkey",
    "enabled": 1
  }
  """
  if not action_config.get('enabled'):
    sys.exit(1)

  LOG.info('Sending request to IFTTT maker')

  url = '{}/{}/with/key/{}'.format(action_config['endpoint'], data['sensor_type'], action_config['auth_key'])

  params = {
      'value1': data['message'],
      'value2': data['sensor_data'],
      'value3': data['board_id']
  }

  try:
    r = requests.put(url, params=params)
    r.raise_for_status()
  except (requests.HTTPError, requests.ConnectionError, requests.exceptions.Timeout) as e:
    LOG.warning("Got exception '%s' in send_ifttt_maker", e)
    sys.exit(2)

  sys.exit(0)
