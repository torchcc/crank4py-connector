# coding=utf-8
# author=torchcc

import ssl
from concurrent.futures.thread import ThreadPoolExecutor
from enum import Enum
from typing import List, NoReturn

from yarl import URL

from crank4py_connector.conn_info_n_ws_client_farm import ConnInfo, WebsocketClientFarm
from crank4py_connector.connector_socket import ConnectorSocket
from cranker_protocol.protocol import CrankerProtocolVersion10
from util import log

from crank4py_connector.config import Config


class State(Enum):
    NOT_STARTED = 1
    RUNNING = 2
    SHUTTING_DOWN = 3
    SHUTDOWN = 4


class Connector(object):

    def __init__(self, router_uris: List[URL], target_uri: URL, target_service_name: str, sliding_window_size: int,
                 connector_instance_id: str, component_name: str) -> None:
        self._router_uris = router_uris
        self._target_uri = target_uri
        self._target_service_name = target_service_name
        self._sliding_window_size = sliding_window_size
        self._connector_instance_id = connector_instance_id
        self._ws_client_farm = WebsocketClientFarm(sliding_window_size)
        self._component_name = component_name
        self._state = State.NOT_STARTED

    def start(self) -> NoReturn:
        for uri in self._router_uris:
            register_uri = uri.join(
                URL.build(path="register/", query={"connectorInstanceID": self._connector_instance_id,
                                                   "componentName": self._component_name}))
            log.info("connecting to " + str(register_uri))
            for i in range(self._sliding_window_size):
                conn_info = ConnInfo(register_uri, i)
                self._connect_to_router(register_uri, conn_info)
                self._ws_client_farm.add_ws(str(register_uri))

        log.info(f"connector started for component={self._component_name}, for path=/{self._target_service_name}")
        self._state = State.RUNNING

    def _connect_to_router(self, register_uri, conn_info) -> NoReturn:
        upgrade_req_headers = {
            "CrankerProtocol": CrankerProtocolVersion10,
            "Route": self._target_service_name
        }
        sock = ConnectorSocket(register_uri, self._target_uri, conn_info,
                               self._ws_client_farm, self._component_name, headers=upgrade_req_headers)

        def runnable():
            try:
                if self._state in (State.SHUTDOWN, State.SHUTTING_DOWN):
                    log.info(
                        f"connector {self._connector_instance_id} will not reconnect to router as it is being shut down")
                elif self._ws_client_farm.is_safe_to_add_ws(register_uri):
                    log.info(f"connector {self._connector_instance_id} is adding another connectorSocket...")
                    self._connect_to_router(sock.register_uri, conn_info)
                    self._ws_client_farm.add_ws(str(sock.register_uri))
                else:
                    log.warning(f"unexpected error happened, will not add websocket for this connector with "
                                f"id {self._connector_instance_id}, current websocket client farm={self._ws_client_farm}")
            except Exception as e:
                log.error(f"can not replace socket to {register_uri}, err: {e}", exc_info=True)

        sock.when_consumed(runnable)
        if self._state != State.SHUTDOWN:
            conn_info.on_conn_starting()
            sock.thread_pool.submit(sock.run_forever, sslopt={"cert_reqs": ssl.CERT_NONE}, ping_interval=5)
        log.debug(f"connected to router, register url = {register_uri}")

    def shutdown(self) -> NoReturn:
        self._state = State.SHUTTING_DOWN
        for uri in self._router_uris:
            deregister: URL = uri.join(URL.build(path="/deregister/",
                                                 query={"connectorInstanceID": self._connector_instance_id,
                                                        "componentName": self._component_name}))
            log.info(f"desconnecting to {deregister}")
            deregister_info = ConnInfo(deregister, 0)
            self._connect_to_router(deregister, deregister_info)
        self._state = State.SHUTDOWN


def create_and_start_connector(c: Config) -> Connector:
    connector = Connector(c.router_uris, c.target_uri, c.target_service_name, c.sliding_window_size, c.instance_id,
                          c.component_name)
    try:
        connector.start()
    except Exception as e:
        log.error(
            f"error happened while connecting service {c.target_uri} {c.target_service_name} to {c.router_uris} with sliding window size {c.sliding_window_size}",
            exc_info=True)
        raise e
    return connector

