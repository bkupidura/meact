var dashboardControllers = angular.module('dashboardControllers', []);

dashboardControllers.controller('MenuCtrl', ['$scope', 'dashboardConfig',
  function ($scope, dashboardConfig){
    $scope.graphs = dashboardConfig['graphs'];
  }]);

dashboardControllers.controller('StatusCtrl', ['$scope', '$interval', 'dashboardConfig', 'StatusService',
  function ($scope, $interval, dashboardConfig, StatusService) {

    $scope.timers = Array();
    $scope.showDetail = {}

    updateStatus = function(){
      StatusService.getStatus().then(function(data) {
        $scope.status = Array();
        angular.forEach(data['data'], function(status_value, status_name){
          angular.forEach(dashboardConfig['status'], function(type_value , type_name){
            if (type_value.indexOf(status_name) !== -1){
              $scope.status.push({
                'name': status_name,
                'value': status_value,
                'type': type_name
              });
            }
          });
        });
      });
    }
    $scope.changeStatus = function(name){
      angular.forEach($scope.status, function(status_value, status_index){
        if (status_value['name'] == name){
            $scope.status[status_index]['value'] ^= 1;
            StatusService.setStatus(name, $scope.status[status_index]['value']);
        }
      });
    }

    updateStatus();

    $scope.timers.push($interval(updateStatus, 1000*60))

    $scope.$on("$destroy", function(){
      angular.forEach($scope.timers, function(value, key){
        $interval.cancel(value);
      });
    });

  }]);

dashboardControllers.controller('BoardCtrl', ['$scope', '$interval', '$filter', '$uibModal', 'dashboardConfig', 'BoardService', 'defaults',
  function ($scope, $interval, $filter, $uibModal, dashboardConfig, BoardService, defaults) {

    $scope.timers = Array();
    $scope.boards = defaults['boards'];
    $scope.boards_offline = defaults['boards_offline'];
    $scope.offline_timeout = dashboardConfig.offline_timeout;
    $scope.commands = dashboardConfig.commands;

    updateBoards = function(){
      var now = new Date() / 1000;
      BoardService.getBoard(now - $scope.offline_timeout, null, null).then(function(data){
        $scope.boards = data['data'];
      });
    }
    updateBoardsOffline = function(){
      BoardService.getBoard().then(function(data){
        $scope.boards_offline = $filter('BoardOffline')(data['data'], $scope.offline_timeout);
      });
    }
    getCommands = function(boardID) {
      if (boardID in $scope.commands) {
        return $scope.commands[boardID];
      } else {
        return $scope.commands['default'];
      }
    }
    $scope.actionOpen = function(boardID, boardDesc){
      var modalInstance = $uibModal.open({
        animation: true,
        templateUrl: 'BoardAction',
        controller: 'ActionModalCtrl',
        size: 'sm',
        resolve: {
          commands: function() {
            return getCommands(boardID);
          },
          boardID: function() {
            return boardID;
          },
          boardDesc: function() {
            return boardDesc;
          }
        }
      });
    }

    updateBoards();
    updateBoardsOffline();

    $scope.timers.push($interval(updateBoards, 1000*60));
    $scope.timers.push($interval(updateBoardsOffline, 1000*60));

    $scope.$on("$destroy", function(){
      angular.forEach($scope.timers, function(value, key){
        $interval.cancel(value);
      });
    });
  }]);

dashboardControllers.controller('ActionModalCtrl', function ($scope, $uibModalInstance, MQTTService, commands, boardID, boardDesc) {

  $scope.boardID = boardID;
  $scope.boardDesc = boardDesc;
  $scope.commands = commands;

  $scope.sendCommand = function(boardID, command){
    var cmd = sprintf(command['command'], {board: boardID});
    MQTTService.publish(cmd, command['mqtt_topic'], false);
    $uibModalInstance.close();
  }
});

dashboardControllers.controller('MapCtrl', ['$scope', '$interval', '$filter', '$uibModal', 'dashboardConfig', 'BoardService', 'defaults',
  function ($scope, $interval, $filter, $uibModal, dashboardConfig, BoardService, defaults) {

    $scope.timers = Array();
    $scope.boards = defaults['boards'];
    $scope.boards_offline = defaults['boards_offline'];
    $scope.offline_timeout = dashboardConfig.offline_timeout;

    updateBoards = function(){
      var now = new Date() / 1000;
      BoardService.getBoard(now - $scope.offline_timeout, null, null).then(function(data){
        $scope.boards = data['data'];
      });
    }
    updateBoardsOffline = function(){
      BoardService.getBoard().then(function(data){
        $scope.boards_offline = $filter('BoardOffline')(data['data'], $scope.offline_timeout);
      });
    }
    boardOpen = function(board){
      var modalInstance = $uibModal.open({
        animation: true,
        templateUrl: 'BoardDetail',
        controller: 'MapModalCtrl',
        size: 'sm',
        resolve: {
          board: function() {
            return board;
          }
        }
      });
    }
    updateMap = function(){
      var svg_map = d3.select('#svg-map');
      angular.forEach($scope.boards, function(value, key){
        var svg_board = svg_map.select("#board-" + value['id']);
        svg_board.on('click', function(){
          boardOpen(value);
        })
        svg_board.attr('class', 'map-board-online');
      });
      angular.forEach($scope.boards_offline, function(value, key){
        svg_map.select("#board-" + value['id']).attr('class', 'map-board-offline');
      });
    }

    updateBoards();
    updateBoardsOffline();

    $scope.$watch('boards', updateMap);
    $scope.$watch('boards_offline', updateMap);

    $scope.timers.push($interval(updateBoards, 1000*60));
    $scope.timers.push($interval(updateBoardsOffline, 1000*60));

    $scope.$on("$destroy", function(){
      angular.forEach($scope.timers, function(value, key){
        $interval.cancel(value);
      });
    });

  }]);

dashboardControllers.controller('MapModalCtrl', function ($scope, board) {
  $scope.board = board;
});

dashboardControllers.controller('GraphCtrl', ['$scope', '$interval', '$routeParams', '$filter', 'dashboardConfig', 'GraphService', 'BoardService',
  function ($scope, $interval, $routeParams, $filter, dashboardConfig, GraphService, BoardService) {

    $scope.timers = Array();
    $scope.selectedBoards = [];
    $scope.begin_offset = 60*60;
    $scope.graph_detail = dashboardConfig['graphs'][$routeParams['type']];

    Highcharts.setOptions({
      global : {
        useUTC : false,
      }
    });

    $scope.chartConfig = {
      options: {
        chart: {
          type: $scope.graph_detail['type'],
        },
        legend: {
          enabled: true,
        },
        tooltip: {
          shared: false,
          formatter: function() {
            var s = Highcharts.dateFormat('%A, %d-%m-%Y %H:%M:%S', this.x);
            s += '<br/>' + this.series.name + ': <b>' + this.y.toFixed($scope.graph_detail['yRound']) + '</b>';
            return s;
          }
        },
        rangeSelector: {
          enabled: true,
          buttons: [
            {type: 'hour', count: 1, text: '1h'},
            {type: 'day', count: 1, text: '1d'},
            {type: 'day', count: 7, text: '1w'},
            {type: 'month', count: 1, text: '1m'},
            {type: 'year', count: 1, text: '1y'},
          ],
          inputEnabled: false,
          allButtonsEnabled: true,
        },
        scrollbar: {
          enabled: false,
        },
      },
      loading: false,
      xAxis: {
        type: 'datetime',
        events: {
          setExtremes: setExtremes
        }
      },
      yAxis: {
        title: {
          text: $scope.graph_detail['yAxisLabel']
        }
      },
      series: [[null, null]],
      title: {
        text: $scope.graph_detail['title']
      },
      useHighStocks: true
    }

    function setExtremes(e){
      if (e.rangeSelectorButton != null){
        $scope.begin_offset = e.rangeSelectorButton['_range'] / 1000;
        $scope.graphData();
      }
    }
    updateBoards = function(){
      var sensor_type = $filter('lowercase')($routeParams['type']);
      BoardService.getBoard(null, null, sensor_type).then(function(data){
        $scope.boards = data['data'];
      });
    }
    $scope.graphData = function(){
      var graph_type = $filter('lowercase')($routeParams['type']);
      var start_time = $filter('LastUpdate')($scope.begin_offset);
      var board_ids = $scope.selectedBoards.map(function(x){ return x['id']});
      var graph_data = Array();

      if (board_ids.length > 0){
        $scope.chartConfig.loading = true;
        GraphService.getData(graph_type, start_time, board_ids, 10).then(function(data) {
          angular.forEach(data['data'], function(value, key){
            graph_data.push({
              'id': value['id'],
              'name': value['desc'],
              'data': value['data'],
            });
          });
          $scope.chartConfig.series = graph_data;
          $scope.chartConfig.loading = false;
          $scope.chartConfig.xAxis.currentMin = start_time * 1000;
          $scope.chartConfig.xAxis.currentMax = new Date().getTime();
        });
      }
    }

    updateBoards();

    $scope.timers.push($interval($scope.graphData, 1000*120));

    $scope.$on("$destroy", function(){
      angular.forEach($scope.timers, function(value, key){
        $interval.cancel(value);
      });
    });

  }]);
