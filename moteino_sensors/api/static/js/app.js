var dashboardApp = angular.module('dashboardApp', [
  'ngRoute',
  'ngResource',
  'dashboardControllers',
  'ngAnimate',
  'ui.bootstrap',
  'nvd3'
]);

dashboardApp.constant('dashboardConfig', {
  commands: {
    '1': [{'name': 'measure', 'command': '%(board)s:1', 'mqtt_topic': 'srl/write'}, {'name': 'reboot', 'command': '%(board)s:255', 'mqtt_topic': 'srl/write'}],
    'default': [{'name': 'reboot', 'command': '%(board)s:255', 'mqtt_topic': 'srl/write'}, {'name': 'blink', 'command': '%(board)s:11', 'mqtt_topic': 'srl/write'}]
  },
  offline_timeout: 1800,
});
