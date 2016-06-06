angular.module('dashboardApp').config(['$routeProvider',
  function($routeProvider) {
    $routeProvider.
      when('/status', {
        templateUrl: 'partials/status.html',
        controller: 'StatusCtrl'
      }).
      when('/board', {
        templateUrl: 'partials/board.html',
        controller: 'BoardCtrl',
        resolve: {
          defaults: function(){
            return {
              boards: Array(),
              boards_offline: Array()
            }
          }
        }
      }).
      when('/map', {
        templateUrl: 'partials/map.html',
        controller: 'MapCtrl',
        resolve: {
          defaults: function(){
            return {
              boards: Array(),
              boards_offline: Array()
            }
          }
        }
      }).
      when('/graph/:type', {
        templateUrl: 'partials/graph.html',
        controller: 'GraphCtrl'
      }).
      otherwise({
        redirectTo: '/status'
      });
  }
]);
