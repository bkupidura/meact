commands = {
    '1': [{'name': 'measure', 'command': '%(board)s:1', 'mqtt_topic': 'srl/write'}, {'name': 'reboot', 'command': '%(board)s:255', 'mqtt_topic': 'srl/write'}],
    'default': [{'name': 'reboot', 'command': '%(board)s:255', 'mqtt_topic': 'srl/write'}]
}

function render_command(board){
    if (board in commands) {
        commands_for_board = $.extend(true, [], commands[board]);
    } else {
        commands_for_board = $.extend(true, [], commands['default']);
    }
    cmd = [];
    for (i=0; i<commands_for_board.length; i++){
        commands_for_board[i]['board'] = board;
        commands_for_board[i]['command'] = sprintf(commands_for_board[i]['command'], commands_for_board[i]);
        cmd.push(commands_for_board[i]);
    }
    return cmd;
}
