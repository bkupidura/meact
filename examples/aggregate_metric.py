#!/usr/bin/env python
import logging
from argparse import ArgumentParser

from moteino_sensors import database
from moteino_sensors import utils

LOG = logging.getLogger(__name__)

def check_data_type(type_to_check, current_type, sensor_data):
  if not current_type:
    try:
      type_to_check(sensor_data)
      return type_to_check
    except ValueError:
      return None

  return current_type
    

def aggregate_metrics(db, start, end, sensor_type, execute):
  metrics = database.get_metrics(db, start=start, end=end, sensor_type=sensor_type)
  LOG.info('Got %d metrics between %s and %s', len(metrics), start, end)

  new_records = dict()
  ids_to_delete = []
  for metric in metrics:

    if metric.sensor_type not in new_records:
      data_type = check_data_type(int, None, metric.sensor_data)
      data_type = check_data_type(float, data_type, metric.sensor_data)

      if not data_type:
        LOG.warning("Unknown data type for sensor '%s' data '%s'", metric.sensor_type, metric.sensor_data)
        continue

      new_records[metric.sensor_type] = dict()

      new_records[metric.sensor_type].setdefault('boards', {})
      new_records[metric.sensor_type].setdefault('type', data_type)

    new_records[metric.sensor_type]['boards'].setdefault(metric.board_id, {})
    new_records[metric.sensor_type]['boards'][metric.board_id].setdefault('sensor_sum', 0)
    new_records[metric.sensor_type]['boards'][metric.board_id].setdefault('sensor_num', 0)
    new_records[metric.sensor_type]['boards'][metric.board_id].setdefault('id', metric.id)

    if data_type == float:
      new_records[metric.sensor_type].setdefault('prec', len(metric.sensor_data.split('.')[1]))

    if new_records[metric.sensor_type]['boards'][metric.board_id]['id'] != metric.id:
      ids_to_delete.append(metric.id)

    new_records[metric.sensor_type]['boards'][metric.board_id]['sensor_sum'] += new_records[metric.sensor_type]['type'](metric.sensor_data)
    new_records[metric.sensor_type]['boards'][metric.board_id]['sensor_num'] += 1

  for record in new_records:
    for board in new_records[record]['boards']:
      record_data = new_records[record]['boards'][board]
      new_data = record_data['sensor_sum'] / record_data['sensor_num']

      if new_records[record]['type'] == float:
        new_data = round(new_data, new_records[record]['prec'])

      LOG.info("Update record with id '%d' for sensor_type '%s' for board_id '%s' with value '%s'",
              record_data['id'],
              record,
              board,
              new_data)
      if execute:
        database.update_metric(db, record_data['id'], new_data)

  LOG.info("Delete %d metrics", len(ids_to_delete))
  if execute:
    database.delete_metrics(db, ids_to_delete)

# Map policy name to seconds
policy_map = {
  'hour': 60*60,
  'day': 60*60*24,
  'week': 60*60*24*7,
  'month': 60*60*24*7*4
}

def main():
  parser = ArgumentParser('Aggregate metrics from MGW')
  parser.add_argument('--start', required=True, help='Start time for aggregate (seconds since epoch)')
  parser.add_argument('--end', required=True, help='End time for aggregate (seconds since epoch)')
  parser.add_argument('--db-string', required=True, help='Connection string for DB. Ex. sqlite:////etc/mgw/mgw.db')
  parser.add_argument('--policy', required=True, help='Aggregate policy, aggregate per hour/day/week/month')
  parser.add_argument('--sensor-type', required=False, help='sensor_type for aggregate, if missing we will aggregate all sensor_type')
  parser.add_argument('--execute', required=False, help='Execute data aggregation, without this DB will not be changed', action="store_true")
  args = parser.parse_args()

  db = database.connect(args.db_string)

  utils.create_logger()

  LOG.info("""Starting metric aggregation for data:
    db = '%s'
    policy = '%s'
    sensor_type == '%s'
  """,
    args.db_string,
    args.policy,
    args.sensor_type,
  )

  policy_start = int(args.start)
  policy_end = int(args.start) + policy_map[args.policy]

  while (policy_end <= int(args.end)):
    aggregate_metrics(db, policy_start, policy_end, args.sensor_type, args.execute)
    policy_start += policy_map[args.policy]
    policy_end += policy_map[args.policy]

if __name__ == "__main__":
  main()
