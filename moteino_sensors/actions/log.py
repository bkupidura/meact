import logging


LOG = logging.getLogger(__name__)


def log(data, action_config):
  LOG.info("Log action for '%s'", data)
  return True
