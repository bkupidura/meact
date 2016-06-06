angular.module('dashboardApp').filter('BoardOffline', function() {
  return function(items, offline_timeout){
    var now = new Date() / 1000;
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
        if (re.test(element.id) || re.test(element.desc) || query in element.data){
          return true;
        }
      }
    });
  }
});

angular.module('dashboardApp').filter('LastUpdate', function() {
  return function(last_update){
    var now = new Date() / 1000;
    return parseInt(now - last_update);
  }
});

angular.module('dashboardApp').filter('MetricUnit', function() {
  return function(metric_value, metric_type){
    switch (metric_type) {
      case 'voltage':
        return metric_value + ' V';
      case 'seen':
        return metric_value + ' seconds ago';
      case 'temperature':
        return metric_value + ' \u00B0C';
      default:
        return metric_value;
    }
  }
});
