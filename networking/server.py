#!/usr/bin/env python


class GameSession:
    def __init__(self, unique_id: int, host: str):
        self.uid = unique_id
        self.host = host
        self.players = [host, ]


class GameNetworkServer:
    pass

