var dashboardControllers = angular.module('dashboardControllers', []);

dashboardControllers.controller('MenuCtrl', ['$scope', 'dashboardConfig',
  function ($scope, dashboardConfig){
    $scope.graphs = dashboardConfig['graphs'];
  }]);

dashboardControllers.controller('StatusCtrl', ['$scope', '$interval', 'dashboardConfig', 'StatusService',
  function ($scope, $interval, dashboardConfig, StatusService) {

    $scope.timers = Array();

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
      BoardService.getBoard(start_time = now - $scope.offline_timeout).then(function(data){
        $scope.boards = data['data'];
      });
    }
    updateBoardsOffline = function(){
      BoardService.getBoard().then(function(data){
        $scope.boards_offline = $filter('BoardOffline')(data['data'], $scope.offline_timeout);
      });
    }
    function getCommands(boardID) {
      if (boardID in $scope.commands) {
        return $scope.commands[boardID];
      } else {
        return $scope.commands['default'];
      }
    }
    $scope.actionOpen = function(boardID){
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

dashboardControllers.controller('ActionModalCtrl', function ($scope, $uibModalInstance, MQTTService, commands, boardID) {

  $scope.boardID = boardID;
  $scope.commands = commands;

  $scope.sendCommand = function(boardID, command){
    var cmd = sprintf(command['command'], {board: boardID});
    MQTTService.publish(data = cmd, topic = command['mqtt_topic'], retain = false);
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
      BoardService.getBoard(start_time = now - $scope.offline_timeout).then(function(data){
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
        var svg_board = svg_map.select("#board-" + value['name']);
        svg_board.on('click', function(){
          boardOpen(value);
        })
        svg_board.attr('fill', '#008000');
      });
      angular.forEach($scope.boards_offline, function(value, key){
        svg_map.select("#board-" + value['name']).attr('fill', '#FF0000');
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
    $scope.graphs = dashboardConfig['graphs'];
    $scope.selectedBoards = [];

    $scope.graph_detail = $scope.graphs[$routeParams['type']];

    var test =new Date(new Date().setYear(new Date().getFullYear() - 2)).getTime();

    $scope.chartConfig = {
      options: {
        chart: {
          zoomType: 'x',
          type: $scope.graph_detail['type'],
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
          selected: 0,
        },
        navigator: {
          enabled: true,
          adaptToUpdatedData: true,
          series: {
            data: [[test,0]]
          }
        },
        legend: {
          enabled: true,
        }
      },
      xAxis: {
        events: {
          setExtremes: setExtremes
        }
      },
      yAxis: {
        title: {
          text: $scope.graph_detail['yAxisLabel']
        }
      },
      series: [],
      title: {
        text: $scope.graph_detail['title']
      },
      useHighStocks: true
    }
    function setExtremes(e){
      if (e.rangeSelectorButton != null){
        var now = new Date()/1000;
        var requested_time = e.rangeSelectorButton['_range']/1000;
        graphData($routeParams['type'], now - requested_time);
      }
    }
    function graphData(graph_type, start_time){
      graph_type = $filter('lowercase')(graph_type);
      var board_ids = $scope.selectedBoards.map(function(x){ return x['name']});
      var graph_data = Array();
      GraphService.getData(graph_type, start_time=start_time, board_ids=board_ids, last_available=10).then(function(data) {
        angular.forEach(data['data'], function(value, key){
          graph_data.push({
            'name': value['name'],
            'data': value['data'],
          });
        });
        $scope.chartConfig.series = graph_data;
      });
    }
    updateBoards = function(){
      BoardService.getBoard().then(function(data){
        $scope.boards = data['data'];
      });
    }
    $scope.fClose = function(){
      var now = new Date()/1000 - 60*60; //By default get last 60m
      graphData($routeParams['type'], now);
    }

    updateBoards();

    $scope.$on("$destroy", function(){
      angular.forEach($scope.timers, function(value, key){
        $interval.cancel(value);
      });
    });

  }]);
