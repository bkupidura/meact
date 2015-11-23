commands = {
    '1': [{'name': 'measure', 'command': '%(board)s:1', 'mqtt_topic': 'srl/write'}, {'name': 'reboot', 'command': '%(board)s:255', 'mqtt_topic': 'srl/write'}],
    'default': [{'name': 'reboot', 'command': '%(board)s:255', 'mqtt_topic': 'srl/write'}]
}

function render_command(board){
    if (board in commands) {
        var commands_for_board = $.extend(true, [], commands[board]);
    } else {
        var commands_for_board = $.extend(true, [], commands['default']);
    }
    var cmd = [];
    for (i=0; i<commands_for_board.length; i++){
        commands_for_board[i]['board'] = board;
        commands_for_board[i]['command'] = sprintf(commands_for_board[i]['command'], commands_for_board[i]);
        cmd.push(commands_for_board[i]);
    }
    return cmd;
}

function toggle_command(board){
    var div = document.getElementById('command-'+board);
    var data = render_command(board);

    var source = $('#commandTemplate').html();
    var template = Handlebars.compile(source);
    var rendered = template(data);

    $(div).html(rendered);

}

function send_command(name, command, board, mqtt_topic){
    var msg = 'Send '+name+' to board '+board+'?';
    if (confirm(msg)){
        mqtt_msg = {'topic': mqtt_topic, 'data': command};
        $.postJSON(api_endpoint+'/action/mqtt', JSON.stringify(mqtt_msg));
    }
    return false;
}
