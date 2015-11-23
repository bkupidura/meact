graphs = {
    'temperature': {chart_type: 'line', graph_title: 'Nodes temperature', y_axis_title: 'Temperature (C)', value_round: 1},
    'voltage': {chart_type: 'line', graph_title: 'Nodes voltage', y_axis_title: 'Voltage (V)', value_round: 2},
    'uptime': {chart_type: 'line', graph_title: 'Nodes uptime', y_axis_title: 'Uptime', value_round: 0},
    'failedreport': {chart_type: 'scatter', graph_title: 'Number of failed reports', y_axis_title: 'Failed reports', value_round: 0},
    'motion': {chart_type: 'scatter', graph_title: 'Detected motion', y_axis_title: 'Motion', value_round: 0},
    'rssi': {chart_type: 'line', graph_title: 'Nodes RSSI', y_axis_title: 'RSSI', value_round: 0}
}
var menu = document.getElementById('dropdown-menu');
for (var key in graphs){
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
    var json_range = '{"start":'+e.min/1000+',"end":'+e.max/1000+', "last_available": 10}';
    var what = chart.options.credits.text;
    chart.showLoading('Loading data from server...');
    $.postJSON(api_endpoint+'/graph/'+what, json_range, function (data) {
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
