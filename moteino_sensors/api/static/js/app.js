var dashboardApp = angular.module('dashboardApp', [
  'ngRoute',
  'ngResource',
  'dashboardControllers',
  'ngAnimate',
  'ui.bootstrap',
  'isteven-multi-select',
  'highcharts-ng',
]);

dashboardApp.constant('dashboardConfig', {
  commands: {
    '1': [{'name': 'measure', 'command': '%(board)s:1', 'mqtt_topic': 'srl/write'}, {'name': 'reboot', 'command': '%(board)s:255', 'mqtt_topic': 'srl/write'}],
    'default': [{'name': 'reboot', 'command': '%(board)s:255', 'mqtt_topic': 'srl/write'}, {'name': 'blink', 'command': '%(board)s:11', 'mqtt_topic': 'srl/write'}]
  },
  status: {
    'service': ['dbsm', 'fence', 'srl', 'mgw', 'msd'],
    'general': ['armed']
  },
  graphs: {
    'Voltage': {'type': 'line', 'yAxisLabel': 'Voltage (V)', 'yRound': '2', 'title': 'Board voltage'},
    'Uptime': {'type': 'line', 'yAxisLabel': 'Uptime', 'yRound': '0', 'title': 'Board uptime'},
    'Temperature': {'type': 'line', 'yAxisLabel': 'Temperature (C)', 'yRound': '1', 'title': 'Board temperature'},
    'Failedreport': {'type': 'scatter', 'yAxisLabel': 'Failed reports', 'yRound': '0', 'title': 'Number of failed reports'},
    'Motion': {'type': 'scatter', 'yAxisLabel': 'Motion', 'yRound': '0', 'title': 'Detected motion'},
    'RSSI': {'type': 'line', 'yAxisLabel': 'RSSI', 'yRound': '0', 'title': 'Board RSSI'}
  },
  offline_timeout: 1800,
});
