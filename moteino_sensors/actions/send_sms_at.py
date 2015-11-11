import logging
import time
from gsmmodem.modem import GsmModem, SentSms


LOG = logging.getLogger(__name__)


logging.getLogger("gsmmodem.modem.GsmModem").setLevel(logging.CRITICAL)

def send_sms_at(data, action_config):
  if not action_config.get('enabled'):
    return False

  LOG.info('Sending SMS via AT')

  modem = GsmModem(action_config['port'], action_config['speed'])
  modem.connect()
  try:
    modem.waitForNetworkCoverage(2)
  except TimeoutException:
    LOG.warning('Got exception in send_sms_at')
    return False
  for rcpt in action_config['recipient']:
    try:
      sms = modem.sendSms(rcpt, data['message'])
    except TimeoutException:
      LOG.warning('Got exception in send_sms_at')
      return False
  modem.close()
  return True
