import logging
import smtplib
import socket
import sys

LOG = logging.getLogger(__name__)
TIMEOUT=5

def send_mail(data, action_config):
  if not action_config.get('enabled'):
    sys.exit(1)

  LOG.info('Sending mail')

  message = "From: {sender}\nTo: {recipient}\nSubject: {subject}\n\n{msg}\n\n".format(msg=data['message'], **action_config)
  try:
    s = smtplib.SMTP(action_config['host'], action_config['port'])
    s.starttls()
    s.login(action_config['user'], action_config['password'])
    s.sendmail(action_config['sender'], action_config['recipient'], message)
    s.quit()
  except (socket.gaierror, socket.timeout, smtplib.SMTPAuthenticationError, smtplib.SMTPDataError) as e:
    LOG.warning("Got exception '%s' in send_mail", e)
    sys.exit(2)
  else:
    sys.exit(0)
