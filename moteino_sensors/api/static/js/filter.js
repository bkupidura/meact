angular.module('dashboardApp').filter('BoardOffline', function() {
  return function(items, offline_timeout){
    now = new Date() / 1000;
    return items.filter(function(element){
      if (now - element.last_update > offline_timeout){
        return true;
      }
    });
  }
});

angular.module('dashboardApp').filter('BoardByMetric', function() {
  return function(items, query){
    return items.filter(function(element){
      if (query == null){
        return true;
      } else {
        var re = new RegExp(query, "i");
        if (re.test(element.name) || re.test(element.desc) || query in element.data){
          return true;
        }
      }
    });
  }
});

angular.module('dashboardApp').filter('LastUpdate', function() {
  return function(last_update){
    now = new Date() / 1000;
    return parseInt(now - last_update);
  }
});
