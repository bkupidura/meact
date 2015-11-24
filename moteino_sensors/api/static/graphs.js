graphs_mapping = {
    'temperature': {chart_type: 'line', graph_title: 'Nodes temperature', y_axis_title: 'Temperature (C)', value_round: 1},
    'voltage': {chart_type: 'line', graph_title: 'Nodes voltage', y_axis_title: 'Voltage (V)', value_round: 2},
    'uptime': {chart_type: 'line', graph_title: 'Nodes uptime', y_axis_title: 'Uptime', value_round: 0},
    'failedreport': {chart_type: 'scatter', graph_title: 'Number of failed reports', y_axis_title: 'Failed reports', value_round: 0},
    'motion': {chart_type: 'scatter', graph_title: 'Detected motion', y_axis_title: 'Motion', value_round: 0},
    'rssi': {chart_type: 'line', graph_title: 'Nodes RSSI', y_axis_title: 'RSSI', value_round: 0}
}

var menu = document.getElementById('dropdown-menu');
for (var key in graphs_mapping){
    var li = document.createElement("li");

    var href = document.createElement("a");
    href.setAttribute('href', '#graph');
    href.setAttribute('tabindex', '-1');
    href.setAttribute('data-toggle', 'tab')

    var txt = document.createTextNode(key);

    href.appendChild(txt);
    li.appendChild(href);

    menu.appendChild(li);
}

Highcharts.setOptions({
    global: {
        useUTC: false,
    }
});

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
