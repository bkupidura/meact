function refreshTab(href){
    var $link = $('li.active a[data-toggle="tab"]');
    $link.parent().removeClass('active');
    $(href).tab('show');
}

function invertStatus(status_name, value){
    var msg = 'Change ' + status_name + ' status?';
    if (value == 0){
        value = 1;
    } else {
        value = 0;
    }
    bootbox.confirm(msg, function(result) {
        if (result){
            var data = {};
            data[status_name] = value;
            $.postJSON(api_endpoint + '/action/status', JSON.stringify(data));
            setTimeout(refreshTab(document.getElementById('status-tab')), 500);
        }
    });
    return false;
}

jQuery["postJSON"] = function(url, data, callback) {
    if (jQuery.isFunction(data)) {
        callback = data;
        data = undefined;
    }
    return jQuery.ajax({
        url: url,
        type: "POST",
        contentType:"application/json; charset=utf-8",
        dataType: "json",
        data: data,
        success: callback
    });
};

function filterObject(obj, keys){
    return Object.keys(obj).filter(function(key){
        return keys.indexOf(key) >= 0}).reduce(function(prev, cur){
            prev[cur] = obj[cur]; return prev;
        }, {})
}

function deleteKeys(obj, keys){
    keys.forEach(function(key){
        delete obj[key]})
}
