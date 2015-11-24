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

function getCommands(board){
    var cmd = [];

    if (board in commands_mapping) {
        var commands_for_board = $.extend(true, [], commands_mapping[board]);
    } else {
        var commands_for_board = $.extend(true, [], commands_mapping['default']);
    }

    commands_for_board.forEach(function(command) {
        command['board'] = board;
        command['command'] = sprintf(command['command'], command);
        cmd.push(command);
    });

    return cmd;
}

function showCommandDialog(board){
    var buttons = {}

    var commands_available = getCommands(board);

    commands_available.forEach(function(command) {
        buttons[command['name']] = {
            'className': 'btn-warning',
            'callback': function() {
                sendCommand(command['name'], command['command'], board, command['mqtt_topic']);
            }
        }
    });

    bootbox.dialog({
        message: "Which command you want to execute on board " + board + "?",
        title: "Send remote command",
        buttons: buttons
    });
}

function sendCommand(name, command, board, mqtt_topic){
    var msg = 'Send ' + name + ' to board ' + board + '?';
    bootbox.confirm(msg, function(result){
        if (result){
            mqtt_msg = {'topic': mqtt_topic, 'data': command};
            $.postJSON(api_endpoint + '/action/mqtt', JSON.stringify(mqtt_msg));
        }
    });
    return false;
}

function afterSetExtremes(e) {
    var chart = $('#graph').highcharts();
    var json_range = {'start': e.min/1000, 'end': e.max/1000, 'last_available': 10};
    var graph_type = chart.options.credits.text;

    chart.showLoading('Loading data from server...');

    $.postJSON(api_endpoint + '/graph/' + graph_type, JSON.stringify(json_range), function (data) {
        $.each(data, function(id_j, value){
            var name = data[id_j]['name']
            $.each(chart.series, function(id_s, value){
                if (chart.series[id_s]['name'] == name){
                    chart.series[id_s].setData(data[id_j]['data']);
                }
            });
        });
        chart.hideLoading();
    });
}

function handleGraphRequest(graph_type, data) {
    var chart_begin = new Date(new Date().setYear(new Date().getFullYear() - 2)).getTime();
    $('#graph').highcharts('StockChart', {
        chart: {
            type: graphs_mapping[graph_type]['chart_type'],
        },
        title: {
            text: graphs_mapping[graph_type]['graph_title'],
        },
        xAxis: {
            type: 'datetime',
            events : {
                afterSetExtremes : afterSetExtremes
            },
        },
        rangeSelector: {
            buttons: [{
                    type: 'hour',
                    count: 1,
                    text: '1h'
                }, {
                    type: 'day',
                    count: 1,
                    text: '1d'
                }, {
                    type: 'day',
                    count: 7,
                    text: '1w'
                }, {
                    type: 'month',
                    count: 1,
                    text: '1m'
                }, {
                    type: 'year',
                    count: 1,
                    text: '1y'
                }],
            inputEnabled: true, // it supports only days
            allButtonsEnabled: true,
            enabled: true,
            selected: 0,
        },
        navigator : {
            enabled: true,
            adaptToUpdatedData: false,
            series : {
                data : [[chart_begin, 0]],
            },
        },
        scrollbar: {
            enabled: false,
        },
        tooltip: {
            formatter: function() {
                var s = Highcharts.dateFormat('%A, %d-%m-%Y %H:%M:%S',new Date(this.x));
                var round = graphs_mapping[graph_type]['value_round'];
                s += '<br/>' + this.series.name + ': <b>' + this.y.toFixed(round) + '</b>';
                return s;
            },
            shared: false,
        },
        yAxis: {
            title: {
                text: graphs_mapping[graph_type]['y_axis_title'],
            },
        },
        legend: {
            enabled: true,
        },
        credits: {
            text: graph_type,
        },
        series: data
    });
}
