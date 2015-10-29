# mgw - Moteino Gateway
MGW is responsible for handling metric reported by Moteino boards (http://lowpowerlab.com/moteino/).
It reads input from serial console and perform various actions.

MGW contains a few sub services:
* MGW - main daemon resposible for reading serial and executing actions.
* API - JSON API to talk to MGW via local unix socket.
* Fence - script which handle 'armed' status via API (it use external geofancing api to make a decision).

## Hardware:
* Moteino boards (+FTDI adapter to upload board code).
* Rassberry PI (or any other python compatible computer).

## What we use:
* python
* sqlite
* bottle
* highcharts/highstock (graphs)
* handlebars (templates)
* twitter bootstrap

## Instalation:
* git clone https://github.com/bkupidura/mgw.git
* cd mgw
* pip install -r requirements.txt
* cp global.config.json.example global.config.json
* cp boards.config.json.example boards.config.json
* cp sensors.config.json.example sensors.config.json
* modify all json config files 
* python mgw.py --dir /dir/with/mgw --create-db
* start mgw services (use supervisor if needed)

> python mgw.py --dir /dir/with/mgw

> python api.py --dir /dir/with/mgw/api

> python fence.py --dir /dir/with/mgw/fence

### global.config.json
Fields:
* 'logging' - python logging configuration
* 'serial' - serial configuration
* 'msd' - MSD configuration
* 'action_config' - sensor action configuration

If you want to run another failure_Thread, simply add new entity ex. 'exm' to global.config.json.
After that modify mgw mgmt_Thread.__init__ and add new thread.

### boards.config.json
List of boards inside yours env with descriptions.

### sensors.config.json
List of metrics you want to handle.
Fields:
* 'action' - list of actions (python functions) to execute in case of failure, it supports nested failback.
* 'check_if_armed' - check if STATUS['armed'] should be true, supports exceptions.
* 'action_interval' - how offen perform action.
* 'threshold' - check if value reported by board should trigger action (we use python lambda here).
* 'fail_count' - how many failures should occur before action.
* 'fail_interval' - time window for fail_count, older values will be removed.

### Supervisor
> [program:mgw]
> command=/usr/bin/python /root/mgw/main/mgw.py --dir /root/mgw/main

> [program:mgw-api]
> command=/usr/bin/python /root/mgw/main/api/api.py --dir /root/mgw/main/api

> [program:mgw-fence]
> command=/usr/bin/python /root/mgw/main/fence/fence.py --dir /root/mgw/main/fence

## MGW details
MGW expect on serial input in format:

[BOARD_ID][METRIC_NAME:METRIC_VALUE]

[10][voltage:3.3]

Moteino code compatible with MGW can be found at https://github.com/bkupidura/moteino

MGW use python threads:
* mgmt_Thread - thread used to manage other threads, communicate over socket with external services.
* failure_Thread - thread(s) to perform asynchronous db queries (ex. find missind boards).
* mgw_Thread - thread responsible for reading serial and executing actions.

STATUS dict can contain any parameter you want. Used parameters:
* armed - check if alarm is armed, mgw-fence is changing it automatically.
* msd - if MSD (missing sensor detector [failure_Thread]) is enabled.
* mgw - if MGW (mgw_Thread) is enabled.
* fence - if fence is enabled.

If you want to introduce new service, simply add it to STATUS and in service
get STATUS via API and verify if service should be running.

MGW to communicate with external world (ex. API) use local unix socket.

Examples:
Send command 255 (reboot) to board with id 1:
> {"action": "send", "data":{"nodeid": 1, "cmd":255}}

Set STATUS dict keys mgw and msd to 1:
> {"action": "set", "data":{"mgw": 1, "msd":1}}

Get current STATUS dict from mgw:
> {"action": "status"}
