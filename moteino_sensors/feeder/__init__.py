#!/usr/bin/env python
from multiprocessing import Process, Manager
from threading import Event
import json
import logging
import time

from moteino_sensors import mqtt
from moteino_sensors import utils

class FeedsStatusAdapter(dict):
  def build_defaults(self, feed_name):
    self.setdefault(feed_name, {
      'last_feed': 0,
      'last_fail': 0
    })

  def check_last_feed(self, feed_name, feed_interval):
    now = int(time.time())
    last_feed = self[feed_name]['last_feed']
    if now - last_feed <= feed_interval:
      return False
    return True

  def check_last_fail(self, feed_name, fail_interval):
    now = int(time.time())
    last_fail = self[feed_name]['last_fail']
    if now - last_fail <= fail_interval:
      return False
    return True

  def update_last_feed(self, feed_name):
    now = int(time.time())
    self[feed_name]['last_feed'] = now

  def update_last_fail(self, feed_name):
    now = int(time.time())
    self[feed_name]['last_fail'] = now

class Feeder(mqtt.Mqtt):
  def __init__(self, conf, feeds_map_file):
    super(Feeder, self).__init__()
    self.name = 'feeder'
    self.enabled = Event()
    self.enabled.set()
    self.status = {'feeder': 1}
    self.mqtt_config = conf['mqtt']
    self.feeds_status = FeedsStatusAdapter()
    self.start_mqtt()
    self._validate_feeds(feeds_map_file)

  def _validate_feeds(self, feeds_map_file):
    feeds_map = utils.load_config(feeds_map_file)
    self.feeds_map = dict()

    for feed_name in feeds_map:
      feed_config = feeds_map[feed_name]
      validation_result, feed_config = utils.validate_feed_config(feed_config)

      if validation_result:
        self.feeds_map[feed_name] = feed_config
        self.status[self.name + '/' + feed_name] = 1

  def _feed_helper(self, feed_config):
    feed_name = feed_config['name']
    feed_func = FEEDS_MAPPING.get(feed_name)

    if not feed_func:
      LOG.warning('Unknown feed provider %s', feed_name)
      return

    feed_result = Manager().dict()
    feed_func_timeout = feed_config.get('timeout') or feed_func.get('timeout')

    p = Process(target=feed_func.get('func'), args=(feed_config, feed_result))
    p.start()
    p.join(feed_func_timeout)

    if p.is_alive():
      p.terminate()
      status = 255
    else:
      status = p.exitcode

    if status:
      LOG.error("Fail to execute feed provider '%s', exitcode '%d'", feed_name, status)
      return None
    else:
      return feed_result.get('sensor_data', None)

  def run(self):
    LOG.info('Starting')
    self.loop_start()
    self.publish_status()
    while True:
      self.enabled.wait()
      for feed_name in self.feeds_map:
        feed_config = self.feeds_map[feed_name]
        feed_enabled = int(self.status.get(self.name + '/' + feed_name, 1))

        self.feeds_status.build_defaults(feed_name)

        if not feed_enabled:
          continue

        if not self.feeds_status.check_last_feed(feed_name, feed_config['feed_interval']):
          continue

        if not self.feeds_status.check_last_fail(feed_name, feed_config['fail_interval']):
          continue

        LOG.debug("Geting feeds from '%s'", feed_name)
        feed_result = self._feed_helper(feed_config)

        if not feed_result:
          self.feeds_status.update_last_fail(feed_name)
          continue
        else:
          self.feeds_status.update_last_feed(feed_name)

        LOG.debug("Got feed provider response '%s'", feed_result)

        for sensor_data in feed_result:
          sensor_data = utils.prepare_sensor_data(sensor_data)
          if sensor_data:
            self.publish_metric(feed_config['mqtt_topic'], sensor_data)

      time.sleep(2)


LOG = logging.getLogger(__name__)
FEEDS_MAPPING = utils.load_feeds()

def main():
  parser = utils.create_arg_parser('Feeder')
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.config.json')
  feeds_map_file = args.dir + '/feeds.config.json'

  logging_conf = conf.get('logging', {})
  utils.create_logger(logging_conf)

  feeder = Feeder(conf=conf, feeds_map_file=feeds_map_file)
  feeder.run()


if __name__ == "__main__":
  main()
