# coding=utf-8
# author=torchcc
import threading
import time
from concurrent.futures.thread import ThreadPoolExecutor
from typing import NoReturn, ClassVar, Optional, Callable, Union
from uuid import UUID, uuid4

import six
from requests import Response
from websocket import WebSocket as WebSocket_, WebSocketTimeoutException, ABNF, getdefaulttimeout, WebSocketException, \
    STATUS_UNEXPECTED_CONDITION, STATUS_NORMAL
from websocket import WebSocketApp
from yarl import URL

from crank4py_connector.conn_info_n_ws_client_farm import WebsocketClientFarm, ConnInfo
from crank4py_connector.intermediate_request import IntermediateRequest
from cranker_protocol.protocol import ProtocolRequest, ProtocolResponseBuilder, ProtocolResponse, HeadersBuilder
from util import HttpClient, log, create_http_client


class WebSocket(WebSocket_):

    def __init__(self, *args, **kwargs) -> NoReturn:
        self.ping_count = 0
        self.sock_id = kwargs.pop("sock_id", None)
        super().__init__(*args, **kwargs)

    def ping(self, payload: str = "") -> NoReturn:
        local_addr = self.sock.getsockname()
        remote_addr = self.sock.getpeername()
        self.ping_count += 1
        # it is a must to make ping_str to be bytes, or else there will be bug.
        ping_str = bytes(f"send ping from {local_addr} to {remote_addr} and sockId={self.sock_id} countTime={self.ping_count}", encoding="utf-8")
        super().ping(ping_str)


class ConnectorSocket(WebSocketApp):
    _http_client: ClassVar[HttpClient] = create_http_client()

    def __init__(self, src_uri: URL, target_uri: URL, conn_info: ConnInfo,
                 ws_clien_farm: WebsocketClientFarm, component_name: str, **kwargs):
        self.register_uri: URL = src_uri
        self.target_uri: URL = target_uri
        self.conn_info: ConnInfo = conn_info
        self.sock_id: UUID = uuid4()
        self.create_time: int = int(time.time() * 1000)
        self.ws_client_farm: WebsocketClientFarm = ws_clien_farm
        self._component_name: str = component_name
        self.req_to_target: Optional[IntermediateRequest] = None
        self.had_error: bool = False
        self.req_complete: bool = False
        self.new_sock_added: bool = False
        self.new_sock_added: bool = False
        self.when_consumed_action: Optional[Callable] = None
        self.thread_pool = ThreadPoolExecutor(max_workers=2)

        super().__init__(
            url=str(self.register_uri),
            header=kwargs.pop("headers", {}),
            on_open=self.on_websocket_connect,
            on_message=self.on_message,
            on_error=self.on_websocket_error,
            on_close=self.on_websocket_close,
        )

    def run_forever(self, sockopt=None, sslopt=None,
                    ping_interval=0, ping_timeout=None,
                    ping_payload="",
                    http_proxy_host=None, http_proxy_port=None,
                    http_no_proxy=None, http_proxy_auth=None,
                    skip_utf8_validation=True,
                    host=None, origin=None, dispatcher=None,
                    suppress_origin=False, proxy_type=None):
        """
        run event loop for WebSocket framework.
        This loop is infinite loop and is alive during websocket is available.
        sockopt: values for socket.setsockopt.
            sockopt must be tuple
            and each element is argument of sock.setsockopt.
        sslopt: ssl socket optional dict.
        ping_interval: automatically send "ping" command
            every specified period(second)
            if set to 0, not send automatically.
        ping_timeout: timeout(second) if the pong message is not received.
        http_proxy_host: http proxy host name.
        http_proxy_port: http proxy port. If not set, set to 80.
        http_no_proxy: host names, which doesn't use proxy.
        skip_utf8_validation: skip utf8 validation.
        host: update host header.
        origin: update origin header.
        dispatcher: customize reading data from socket.
        suppress_origin: suppress outputting origin header.

        Returns
        -------
        False if caught KeyboardInterrupt
        True if other exception was raised during a loop
        """

        if ping_timeout is not None and ping_timeout <= 0:
            ping_timeout = None
        if ping_timeout and ping_interval and ping_interval <= ping_timeout:
            raise WebSocketException("Ensure ping_interval > ping_timeout")
        if not sockopt:
            sockopt = []
        if not sslopt:
            sslopt = {}
        if self.sock:
            raise WebSocketException("socket is already opened")
        thread = None
        self.keep_running = True
        self.last_ping_tm = 0
        self.last_pong_tm = 0

        def teardown(close_frame=None):
            """
            Tears down the connection.
            If close_frame is set, we will invoke the on_close handler with the
            statusCode and reason from there.
            """
            if thread and thread.isAlive():
                event.set()
                thread.join()
            self.keep_running = False
            if self.sock:
                self.sock.close()
            close_args = self._get_close_args(
                close_frame.data if close_frame else None)
            self._callback(self.on_close, *close_args)
            self.sock = None

        try:
            self.sock = WebSocket(
                self.get_mask_key, sockopt=sockopt, sslopt=sslopt,
                fire_cont_frame=self.on_cont_message is not None,
                skip_utf8_validation=skip_utf8_validation,
                enable_multithread=True if ping_interval else False,
                sock_id=self.sock_id
            )
            self.sock.settimeout(getdefaulttimeout())
            self.sock.connect(
                self.url, header=self.header, cookie=self.cookie,
                http_proxy_host=http_proxy_host,
                http_proxy_port=http_proxy_port, http_no_proxy=http_no_proxy,
                http_proxy_auth=http_proxy_auth, subprotocols=self.subprotocols,
                host=host, origin=origin, suppress_origin=suppress_origin,
                proxy_type=proxy_type)
            if not dispatcher:
                dispatcher = self.create_dispatcher(ping_timeout)

            self._callback(self.on_open)

            if ping_interval:
                event = threading.Event()
                thread = threading.Thread(
                    target=self._send_ping, args=(ping_interval, event, ping_payload))
                thread.setDaemon(True)
                thread.start()

            def read():
                if not self.keep_running:
                    return teardown()

                op_code, frame = self.sock.recv_data_frame(True)
                if op_code == ABNF.OPCODE_CLOSE:
                    return teardown(frame)
                elif op_code == ABNF.OPCODE_PING:
                    self._callback(self.on_ping, frame.data)
                elif op_code == ABNF.OPCODE_PONG:
                    self.last_pong_tm = time.time()
                    self._callback(self.on_pong, frame.data)
                elif op_code == ABNF.OPCODE_CONT and self.on_cont_message:
                    self._callback(self.on_data, frame.data,
                                   frame.opcode, frame.fin)
                    self._callback(self.on_cont_message,
                                   frame.data, frame.fin)
                else:
                    data = frame.data
                    if six.PY3 and op_code == ABNF.OPCODE_TEXT:
                        data = data.decode("utf-8")
                    self._callback(self.on_data, data, frame.opcode, True)
                    self._callback(self.on_message, data)

                return True

            def check():
                if (ping_timeout):
                    has_timeout_expired = time.time() - self.last_ping_tm > ping_timeout
                    has_pong_not_arrived_after_last_ping = self.last_pong_tm - self.last_ping_tm < 0
                    has_pong_arrived_too_late = self.last_pong_tm - self.last_ping_tm > ping_timeout

                    if (self.last_ping_tm
                            and has_timeout_expired
                            and (has_pong_not_arrived_after_last_ping or has_pong_arrived_too_late)):
                        raise WebSocketTimeoutException("ping/pong timed out")
                return True

            dispatcher.read(self.sock.sock, read, check)
        except (Exception, KeyboardInterrupt, SystemExit) as e:
            self._callback(self.on_error, e)
            if isinstance(e, SystemExit):
                # propagate SystemExit further
                raise
            teardown()
            return not isinstance(e, KeyboardInterrupt)

    def when_consumed(self, runnable: Callable) -> NoReturn:
        self.when_consumed_action = runnable

    def reconnect_to_ws_server(self) -> NoReturn:
        if self.had_error:
            log.info(f"received error for {self.conn_info}, but it was already handled so ignoring it")
            return
        self.had_error = True
        if not self.new_sock_added:
            self.ws_client_farm.remove_ws(str(self.register_uri))
            delay: int = self.conn_info.retry_after_millis()
            log.info(f"going to reconnect to router after {delay} ms")

            def delay_task():
                time.sleep(delay / 1000)
                self.when_consumed_action()
                self.new_sock_added = True
            self.thread_pool.submit(delay_task)

    @staticmethod
    def on_websocket_connect(self, *args) -> NoReturn:
        """on open"""
        log.debug(f"connected to {self.sock.sock.getpeername()}, sockeId={self.sock.sock_id}")

    @staticmethod
    def on_websocket_error(self, err: Exception) -> NoReturn:
        log.warning(f"websocket error: {err}", exc_info=True)
        self.reconnect_to_ws_server()

    @staticmethod
    def on_websocket_close(self, code: int, reason: str) -> NoReturn:
        log.debug(f"connection {self.sock_id} closed: {code} - {reason}")
        if not self.new_sock_added:
            log.debug(f"going to reconnect to router, webswocket close code: {code}")
            self.ws_client_farm.remove_ws(str(self.register_uri))
            self.when_consumed_action()
            self.new_sock_added = True
        if not self.req_complete and self.req_to_target is not None:
            if code != STATUS_UNEXPECTED_CONDITION:
                log.info(f"websocket closed before the target response was processed, This may be because the user"
                         f"closed therire browser, Going to cancel request to target {self.req_to_target.url}")
                self.req_to_target.abort(Exception("Socket to Router closed"))

    @staticmethod
    def on_message(self, msg: Union[str, bytes]) -> NoReturn:
        if isinstance(msg, str):
            self.on_websocket_text(msg)
        elif isinstance(msg, bytes):
            self.on_websocket_binary(msg)
        else:
            log.warning(f"got unexpected msg type {type(msg)}")

    def on_websocket_binary(self, payload: bytes) -> NoReturn:
        if payload:
            self.req_to_target.content.append(payload)

    def on_websocket_text(self, msg: str) -> NoReturn:
        ptc_req = ProtocolRequest(msg)

        # fire the request to target service only when end_marker is RequestHasNoBodyMarker: str = "_2" or RequestBodyEnededMarker: str = "_3"
        if self.req_to_target is None:
            self._on_req_received()
            self._new_req_to_target(ptc_req)
            if ptc_req.req_has_no_body():
                self._send_req_to_target()
            elif ptc_req.req_body_pending():
                log.debug(f"request body pending, sockId={self.sock_id}")
        elif ptc_req.req_body_ended():
            log.debug(f"no further request body is coming, sockId={self.sock_id}")
            self._send_req_to_target()

    def _on_req_received(self) -> NoReturn:
        self.ws_client_farm.remove_ws(str(self.register_uri))
        self.conn_info.on_connected_successfully()
        self.when_consumed_action()
        self.new_sock_added = True

    def _new_req_to_target(self, ptc_req: ProtocolRequest) -> NoReturn:
        ptc_resp = ProtocolResponseBuilder.new_builder()
        req_dest: str = ptc_req.dest
        ptc_resp.with_src_url(req_dest).with_method(ptc_req.method)
        dest: URL = self.target_uri.join(URL(req_dest))
        log.info(f"going to send {ptc_req} to {dest}, component is {self._component_name}")
        self.req_to_target = IntermediateRequest(ptc_req.method, str(dest), self._http_client)
        self._put_headers_to(self.req_to_target, ptc_req)

        def on_resp_begin(resp: Response):
            ptc_resp.with_resp_status(resp.status_code).with_resp_reason(resp.reason)

        def on_resp_headers(resp: Response):
            try:
                ptc_resp.with_resp_headers(self._parse_headers(dict(resp.headers)))
                ptc_resp_msg: ProtocolResponse = ProtocolResponse(ptc_resp.build())
                self.send(ptc_resp_msg.to_protocol_msg())
            except OSError as e:
                log.warning(f"error occurred while sending header back to routr: {e}", exc_info=True)

        self.req_to_target.on_resp_begin(on_resp_begin).on_resp_headers(on_resp_headers).set_ws_session(self)

    def _send_req_to_target(self) -> NoReturn:
        def callabck(result: IntermediateRequest.Result):
            if result.is_succeeded:
                self.req_complete = True
                log.debug("closing websocet because response is fully processed")
                self.close(status=STATUS_NORMAL, reason=b"Proxy complete")
            else:
                self.req_complete = False
                if self.sock:
                    self.close(status=STATUS_UNEXPECTED_CONDITION, reason=b"Proxy failure")

        log.debug("request headers received")
        self.req_to_target.fire_req_from_connector_to_target_service(callabck)
        log.debug("request body is fully sent")

    @staticmethod
    def _put_headers_to(req_to_target: IntermediateRequest, ptc_req: ProtocolRequest) -> NoReturn:
        for line in ptc_req.headers:
            if ":" in line:
                pos = line.index(":")
                header, value = line[0:pos], line[pos + 1:]
                req_to_target.update_header(header, value)
        req_to_target.update_header("Via", "1.1 crnk")

    @staticmethod
    def _parse_headers(header_fields: dict) -> HeadersBuilder:
        headers = HeadersBuilder()
        for name, value in header_fields.items():
            headers.append_header(name, value)
        return headers
