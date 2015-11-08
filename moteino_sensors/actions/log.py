import logging
import timeout_decorator


LOG = logging.getLogger(__name__)

@timeout_decorator.timeout(2, use_signals=False)
def log(data, action_config):
  LOG.info("Log action '%s'", data['message'])
  return True
