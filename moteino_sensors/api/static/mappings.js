commands_mapping = {
    '1': [{'name': 'measure', 'command': '%(board)s:1', 'mqtt_topic': 'srl/write'}, {'name': 'reboot', 'command': '%(board)s:255', 'mqtt_topic': 'srl/write'}],
    'default': [{'name': 'reboot', 'command': '%(board)s:255', 'mqtt_topic': 'srl/write'}]
}

graphs_mapping = {
    'temperature': {chart_type: 'line', graph_title: 'Nodes temperature', y_axis_title: 'Temperature (C)', value_round: 1},
    'voltage': {chart_type: 'line', graph_title: 'Nodes voltage', y_axis_title: 'Voltage (V)', value_round: 2},
    'uptime': {chart_type: 'line', graph_title: 'Nodes uptime', y_axis_title: 'Uptime', value_round: 0},
    'failedreport': {chart_type: 'scatter', graph_title: 'Number of failed reports', y_axis_title: 'Failed reports', value_round: 0},
    'motion': {chart_type: 'scatter', graph_title: 'Detected motion', y_axis_title: 'Motion', value_round: 0},
    'rssi': {chart_type: 'line', graph_title: 'Nodes RSSI', y_axis_title: 'RSSI', value_round: 0}
}

status_mapping = {
    'Service': ['msd', 'mgw', 'srl', 'fence'],
    'Status': ['armed']
}
/* Allow to disable any element from dashboard based on ID
 * If you want to disable ex. graph tab and map tab
 * disabled_elems = ['graph-tab', 'map-tab']
 *
 */
disabled_elems = []
