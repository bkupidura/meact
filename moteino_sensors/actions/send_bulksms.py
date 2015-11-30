import logging
import requests
import sys


LOG = logging.getLogger(__name__)
TIMEOUT=5


logging.getLogger("requests").setLevel(logging.CRITICAL)
requests.packages.urllib3.disable_warnings()

def send_bulksms(data, action_config):
  if not action_config.get('enabled'):
    sys.exit(1)

  LOG.info('Sending SMS via bulksms.com')

  url = action_config['endpoint']
  params = {
      'username': action_config['user'],
      'password': action_config['password'],
      'msisdn': action_config['recipient'],
      'message': data['message'],
  }

  try:
    r = requests.get(url, params=params)
    r.raise_for_status()
  except (requests.HTTPError, requests.ConnectionError, requests.exceptions.Timeout) as e:
    LOG.warning("Got exception '%s' in send_bulksms", e)
    sys.exit(2)

  result = r.text.split('|')
  if result[0] != '0':
    LOG.warning("Fail in send_bulksms '%s' '%s'", result[0], result[1])
    sys.exit(2)

  sys.exit(0)
