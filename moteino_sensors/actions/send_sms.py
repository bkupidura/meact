import logging
import timeout_decorator
import requests


LOG = logging.getLogger(__name__)


logging.getLogger("requests").setLevel(logging.CRITICAL)
requests.packages.urllib3.disable_warnings()

@timeout_decorator.timeout(5, use_signals=False)
def send_sms(data, action_config):
  if not action_config.get('enabled'):
    return False

  LOG.info('Sending SMS')

  url = action_config['endpoint']
  params = {
      'username': action_config['user'],
      'password': action_config['password'],
      'msisdn': action_config['recipient'],
      'message': data['message'],
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
