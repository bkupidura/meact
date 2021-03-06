angular.module('dashboardApp').factory('BoardService', function($http) {
  return {
    getBoard: function(start_time, end_time, sensor_type) {
      return $http.post('/api/board', {start: start_time,
          end: end_time,
          sensor_type: sensor_type,
      });
    }
  }
});

angular.module('dashboardApp').factory('StatusService', function($http) {
  return {
    getStatus: function() {
      return $http.get('/api/status');
    },
    setStatus: function(key, value) {
      var data = {}
      data[key] = value;
      return $http.post('/api/status', data);
    }
  }
});

angular.module('dashboardApp').factory('MQTTService', function($http) {
  return {
    publish: function(data, topic, retain) {
      return $http.post('/api/mqtt', {data: data, topic: topic, retain: retain});
    }
  }
});

angular.module('dashboardApp').factory('GraphService', function($http) {
  return {
    getData: function(graph_type, start_time, board_ids, last_available) {
      return $http.post('/api/graph/' + graph_type, {start: start_time,
          board_id: board_ids,
          last_available: last_available
      });
    }
  }
});
