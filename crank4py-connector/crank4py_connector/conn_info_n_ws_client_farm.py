# coding=utf-8
# author=torchcc
import math
from typing import NoReturn, Dict

from yarl import URL

from util import log


class ConnInfo(object):

    def __init__(self, router_uri: URL, conn_idx: int) -> None:
        self.router_uri: URL = router_uri
        self._conn_idx: int = conn_idx
        self._cur_conn_attempts: int = 0

    def on_connected_successfully(self) -> NoReturn:
        self._cur_conn_attempts = 0

    def on_conn_starting(self) -> NoReturn:
        self._cur_conn_attempts += 1

    def retry_after_millis(self) -> int:
        return 500 + min(10000, int(math.pow(2, self._cur_conn_attempts)))

    def __str__(self) -> str:
        return "ConnectionInfo{" + \
               "routerURI=" + str(self.router_uri) + \
               ", connIndex=" + str(self._conn_idx) + \
               ", curConnAttempts=" + str(self._cur_conn_attempts) + \
               "}"

    __repr__ = __str__


class WebsocketClientFarm(object):

    def __init__(self, sliding_window_size: int) -> None:
        self._max_slding_window_size = sliding_window_size * 2
        self._connector_socks: Dict[str, int] = dict()

    def add_ws(self, register_uri: str) -> NoReturn:
        if register_uri not in self._connector_socks:
            self._connector_socks[register_uri] = 0
        self._connector_socks[register_uri] += 1
        log.debug(f"add websocket for registerUrl={register_uri}, current websocketClientFarm={self}")

    def remove_ws(self, register_uri: str) -> NoReturn:
        self._connector_socks[register_uri] -= 1

    def is_safe_to_add_ws(self, register_uri: URL) -> bool:
        is_not_deregiste_path = not register_uri.path.startswith("/deregister")
        idle_sock_num = self._connector_socks.get(str(register_uri), 0)
        return is_not_deregiste_path and self._max_slding_window_size > idle_sock_num

    def to_map(self) -> Dict[str, int]:
        return self._connector_socks
