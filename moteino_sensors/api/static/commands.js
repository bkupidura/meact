commands_mapping = {
    '1': [{'name': 'measure', 'command': '%(board)s:1', 'mqtt_topic': 'srl/write'}, {'name': 'reboot', 'command': '%(board)s:255', 'mqtt_topic': 'srl/write'}],
    'default': [{'name': 'reboot', 'command': '%(board)s:255', 'mqtt_topic': 'srl/write'}]
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
