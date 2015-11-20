<?php
ini_set('error_reporting', 0);
ini_set('display_errors', 0);

$valid_devices = array('AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE');
$valid_passwords = array("user" => "pass");
$data_file = '../geofencing.txt';
$ignore_auth_for_devices = 1;

function get_data($data_file){
    if (file_exists($data_file)){
        $data = file_get_contents($data_file);
        return json_decode($data, true);
    } else
        return Array();
}
function dump_data($data, $data_file){
    $data = json_encode($data);
    file_put_contents($data_file, $data);
}
function get_value($where, $what){
    if (isset($where[$what]) && !empty($where[$what]))
        return $where[$what];
    else
        return '';
}
function validate_user($user, $pass, $valid_passwords, $skip){
    if ($skip)
        return 1;

    $valid_users = array_keys($valid_passwords);
    if (in_array($user, $valid_users) && $pass == $valid_passwords[$user])
        return 1;
    else
        return 0;
}
function validate_device($device, $valid_devices){
    if (in_array($device, $valid_devices))
        return 1;
    else
        return 0;
}

$user = get_value($_SERVER, 'PHP_AUTH_USER');
$pass = get_value($_SERVER, 'PHP_AUTH_PW');
$device = get_value($_POST, 'device-id');
$action = get_value($_POST, 'action');

$data = get_data($data_file);

if (validate_device($device, $valid_devices)){
    if (validate_user($user, $pass, $valid_passwords, $ignore_auth_for_devices)){
        $entry = array('action' => $action, 'time' => time());
        $data[$device] = $entry;

        dump_data($data, $data_file);

        header('HTTP/1.0 200');
        die();
    }
}

if (validate_user($user, $pass, $valid_passwords, 0)){
    echo json_encode($data);
} else {
    header('HTTP/1.0 403 Forbidden');
    die ("Not authorized");
}

?>
