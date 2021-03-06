#!/usr/bin/env python
import json
import logging
from configparser import ConfigParser

import requests
import pyautogui

from werkzeug.wrappers import Request, Response
from werkzeug.serving import run_simple

from controller.jsonrpc import request_error
from controller.window import Window
from controller import JsonRpcMethods, JsonRpcClient, InputController

class ControllerServer:
    def __init__(self, controller, config):
        self.controller = controller
        self.window = controller.window
        self.config = config
        self.logger = logging.getLogger('werkzeug')
        self.log_level = config['Debug']['LogLevel'].upper()
        self.jsonrpc_methods = JsonRpcMethods(controller)
        self.jsonrpc_client = None

        self.running = False
        self.listeners = {}

        self.setup_logger()
        self.setup_listeners()

    def setup_logger(self):
        if self.log_level != 'DEBUG':
            self.logger.setLevel(getattr(logging, self.log_level))

    def setup_listeners(self):
        self.jsonrpc_methods.add_method('start', self.on_start)
        self.jsonrpc_methods.add_method('stop', self.on_stop)

    def on_start(self):
        if self.running:
            return 'Controller already running'
        self.running = True
        self.window.listen_for_escape(self.stop_command_server)
        return 'OK'

    def on_stop(self):
        if not self.running:
            return 'Controller not running'
        self.running = False
        return 'OK'

    def stop_command_server(self):
        print('Stopping command server...')
        try:
            self.jsonrpc_client.stop()
            self.running = False
            print('Command server stopped')
        except requests.HTTPError:
            print('Failed to stop the command server!')

    def listen(self, port, command_port, command_endpoint):
        self.jsonrpc_client = JsonRpcClient(command_port, path=command_endpoint)
        run_simple('localhost', port, self.application)

    @Request.application
    def application(self, request):
        data = request.data.decode('utf-8')
        print(data)

        data = json.loads(data)
        method = data['method']
        if self.running or method in self.jsonrpc_methods.methods:
            data = self.jsonrpc_methods.handle_request(data)
        else:
            data = request_error(data['id'], 'Controller not running!')

        return Response(json.dumps(data), mimetype='application/json')

def read_config(filename):
    config = ConfigParser()
    config.read(filename, encoding='utf-8')
    return config

def main():
    config = read_config('config.ini')
    controller_port = int(config['Controller']['ListenerPort'])
    command_port = int(config['Server']['ListenerPort'])
    command_endpoint = config['Server']['JsonRpcEndpoint']
    window = Window({
        'Language': config['General']['Language'].lower(),
        'MouseSpeed': float(config['Inputs']['MouseSpeed']),
        'MouseSpeedBase': float(config['Inputs']['MouseSpeedBase']),
        'MouseClickDelay': float(config['Inputs']['DelayInMsBetweenMouseDownAndUp']),
        'MouseClickRandomDelay': float(config['Inputs']['RandomDelayInMsBetweenMouseDownAndUp']),
        'MouseTween': getattr(pyautogui, config['Controller']['MouseTween']),
        'ExitKeyCode': int(config['Inputs']['ExitKeyCode'])
    })
    controller = InputController(window)
    ControllerServer(controller, config).listen(controller_port, command_port, command_endpoint)

if __name__ == '__main__':
    main()
