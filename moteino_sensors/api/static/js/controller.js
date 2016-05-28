var dashboardControllers = angular.module('dashboardControllers', []);

dashboardControllers.controller('StatusCtrl', ['$scope', '$http', '$interval', 'StatusService',
  function ($scope, $http, $interval, StatusService) {
      
    updateStatus = function(){
      StatusService.getStatus().then(function(data) {
        $scope.status = data['data'];
      });
    }

    updateStatus();
    $interval(updateStatus, 1000*60);

    $scope.changeStatus = function(name){
      $scope.status[name] ^= 1;
      StatusService.setStatus(name, $scope.status[name]);
    }

  }]);

dashboardControllers.controller('BoardCtrl', ['$scope', '$http', '$interval', '$filter', '$uibModal', 'dashboardConfig', 'BoardService', 'defaults',
  function ($scope, $http, $interval, $filter, $uibModal, dashboardConfig, BoardService, defaults) {

    $scope.boards = defaults['boards'];
    $scope.boards_offline = defaults['boards_offline'];
    $scope.offline_timeout = dashboardConfig.offline_timeout;
    $scope.commands = dashboardConfig.commands;

    updateBoards = function(){
      now = new Date() / 1000;
      BoardService.getBoard(start_time = now - $scope.offline_timeout).then(function(data){
        $scope.boards = data['data'];
      });
    }
    updateBoardsOffline = function(){
      BoardService.getBoard().then(function(data){
        $scope.boards_offline = $filter('BoardOffline')(data['data'], $scope.offline_timeout);
      });
    }

    updateBoards();
    updateBoardsOffline();

    $interval(updateBoards, 1000*60);
    $interval(updateBoardsOffline, 1000*60);

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

  }]);

dashboardControllers.controller('ActionModalCtrl', function ($scope, $uibModalInstance, MQTTService, commands, boardID) {
  $scope.boardID = boardID;
  $scope.commands = commands;

  $scope.sendCommand = function(boardID, command){
    cmd = sprintf(command['command'], {board: boardID});
    MQTTService.publish(data = cmd, topic = command['mqtt_topic'], retain = false);
    $uibModalInstance.close();
  }
});

dashboardControllers.controller('MapCtrl', ['$scope', '$http', '$interval', '$filter', '$timeout', 'dashboardConfig', 'BoardService', 'defaults',
  function ($scope, $http, $interval, $filter, $timeout, dashboardConfig, BoardService, defaults) {
    $scope.boards = defaults['boards'];
    $scope.boards_offline = defaults['boards_offline'];
    $scope.offline_timeout = dashboardConfig.offline_timeout;

    updateBoards = function(){
      now = new Date() / 1000;
      BoardService.getBoard(start_time = now - $scope.offline_timeout).then(function(data){
        $scope.boards = data['data'];
      });
    }
    updateBoardsOffline = function(){
      BoardService.getBoard().then(function(data){
        $scope.boards_offline = $filter('BoardOffline')(data['data'], $scope.offline_timeout);
      });
    }
    updateMap = function(){
      svg_map = d3.select('#svg-map');
      angular.forEach($scope.boards, function(value, key){
        svg_board = svg_map.select("#board-" + value['name']);
        svg_board.attr('fill', '#008000');
        svg_board.attr('uib-popover-template', "\"'BoardDetail'\"");
        svg_board.attr('popover-trigger', 'mouseenter');
        svg_board.attr('popover-placement', 'auto top');
        svg_board.attr('popover-title', 'Details');
      });
      angular.forEach($scope.boards_offline, function(value, key){
        svg_map.select("#board-" + value['name']).attr('fill', '#FF0000');
      });
    }

    updateBoards();
    updateBoardsOffline();

    $scope.$watch('boards', updateMap);
    $scope.$watch('boards_offline', updateMap);

    $interval(updateBoards, 1000*60);
    $interval(updateBoardsOffline, 1000*60);

  }]);

