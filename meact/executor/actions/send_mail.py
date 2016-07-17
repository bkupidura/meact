import logging
import smtplib
import socket
import sys

LOG = logging.getLogger(__name__)
TIMEOUT=5

def send_mail(data, action_config):
  """Send mail via SMTP

  Meact configuration:
  action_config = {
    "sender": "root@example.com",
    "recipient": ["user@example.com"],
    "subject": "RPI notification",
    "host": "email-smtp.eu-west-1.amazonaws.com",
    "port": 587,
    'tls': 1,
    "user": "user",
    "password": "password",
    "enabled": 1
  }
  """
  if not action_config.get('enabled'):
    sys.exit(1)

  LOG.info('Sending mail via SMTP')

  smtp_details = {
    'sender': action_config['sender'],
    'subject': action_config.get('subject', 'RPI notification'),
    'host': action_config['host'],
    'port': action_config.get('port', 587),
    'tls': action_config.get('tls', 1),
    'user': action_config['user'],
    'password': action_config['password']
  }

  for rcpt in action_config['recipient']:
    message = "From: {sender}\nTo: {recipient}\nSubject: {subject}\n\n{msg}\n\n".format(msg=data['message'], recipient=rcpt, **smtp_details)
    try:
      s = smtplib.SMTP(smtp_details['host'], smtp_details['port'])
      if smtp_details['tls']:
        s.starttls()
      s.login(smtp_details['user'], smtp_details['password'])
      s.sendmail(smtp_details['sender'], rcpt, message)
      s.quit()
    except (socket.gaierror, socket.timeout, smtplib.SMTPAuthenticationError, smtplib.SMTPDataError) as e:
      LOG.warning("Got exception '%s' in send_mail", e)
      sys.exit(2)
    else:
      sys.exit(0)
