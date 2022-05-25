#!/usr/bin/env python

import json
from socket import socket
from typing import Dict


class GameNetworkClient:
    game_server_ip: str

    def __init__(self):
        self.ip_address = ''  # TODO: find client's ip adress
        self.port = None  # TODO: assign random, unused port
        self.is_host = False  # TODO: assigning host-role to client if player opens new PvP game
        self.other_players_ip_addresses = []

    def connect_to_server(self):
        pass

    def send(self, data):
        pass

    def parse_received_data(self, raw_data):
        pass

    def prepare_data_to_sending(self, units):
        return json.dumps({
            'events': {},
            'positions': {u.id: u.position for u in units}
        })

    def disconnect(self):
        pass
