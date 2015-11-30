import logging
import time
import sys
from gsmmodem.modem import GsmModem, SentSms
from gsmmodem.exceptions import TimeoutException


LOG = logging.getLogger(__name__)
TIMEOUT=30

logging.getLogger("gsmmodem.modem.GsmModem").setLevel(logging.CRITICAL)

def send_sms_at(data, action_config):
  if not action_config.get('enabled'):
    sys.exit(1)

  LOG.info('Sending SMS via AT')

  modem = GsmModem(action_config['port'], action_config['speed'])


  while True:
    try:
      modem.connect()
      modem.waitForNetworkCoverage()
    except TimeoutException:
      pass
    else:
      break

  for rcpt in action_config['recipient']:
    try:
      sms = modem.sendSms(rcpt, data['message'])
    except TimeoutException:
      LOG.warning('Got exception in send_sms_at')
      sys.exit(2)
  modem.close()
  sys.exit(0)
