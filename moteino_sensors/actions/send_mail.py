import logging
import smtplib
import socket
import timeout_decorator

LOG = logging.getLogger(__name__)

@timeout_decorator.timeout(5, use_signals=False)
def send_mail(data, action_config):
  if not action_config.get('enabled'):
    return False

  LOG.info('Sending mail')

  message = "From: {sender}\nTo: {recipient}\nSubject: {subject}\n\n{msg}\n\n".format(msg=data['message'], **action_config)
  try:
    s = smtplib.SMTP(action_config['host'], action_config['port'], timeout=5)
    s.starttls()
    s.login(action_config['user'], action_config['password'])
    s.sendmail(action_config['sender'], action_config['recipient'], message)
    s.quit()
  except (socket.gaierror, socket.timeout, smtplib.SMTPAuthenticationError, smtplib.SMTPDataError) as e:
    LOG.warning("Got exception '%s' in send_mail", e)
    return False
  else:
    return True
