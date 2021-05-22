# coding=utf-8
# author=torchcc

from typing import List, Optional, Callable, Any, NoReturn

from requests import Response
from websocket import WebSocketApp, ABNF

from util import HttpClient


class IntermediateRequest(object):
    _chunk_size: int = 16384

    def __init__(self, method: str = "GET", url: str = "", client: HttpClient = None) -> None:
        self.method: str = method
        self.url: str = url
        self.client: HttpClient = client
        self.content: List[bytes] = []
        self.headers: dict = dict()
        self._on_resp_begin: Optional[Callable[[Response], Any]] = None
        self._on_resp_headers: Optional[Callable[[Response], Any]] = None
        self._ws_session: Optional[WebSocketApp] = None
        self.result_error: Optional[Exception] = None

    def update_header(self, header, value) -> NoReturn:
        self.headers[header] = value

    def on_resp_begin(self, runnalbe: Optional[Callable[[Response], Any]]) -> "IntermediateRequest":
        self._on_resp_begin = runnalbe
        return self
    
    def on_resp_headers(self, runnalbe: Optional[Callable[[Response], Any]]) -> "IntermediateRequest":
        self._on_resp_headers = runnalbe
        return self
    
    def set_ws_session(self, ws: WebSocketApp) -> "IntermediateRequest":
        self._ws_session = ws
        return self

    def abort(self, e: Exception):
        self.result_error = e

    class Result(object):
        def __init__(self):
            self.is_succeeded: bool = False
            self.failure: Optional[Exception] = None

    def fire_req_from_connector_to_target_service(self, callback: Callable[[Result], Any]):
        data = b"".join(self.content)
        result = self.Result()
        try:
            if self.result_error is not None:
                raise self.result_error
            resp: Response = self.client.request(self.method, self.url, headers=self.headers, data=data, stream=True)
            self._on_resp_begin(resp)
            self._on_resp_headers(resp)
            for chunk in resp.iter_content(chunk_size=self._chunk_size):
                if not chunk:
                    break
                self._ws_session.send(chunk, opcode=ABNF.OPCODE_BINARY)
            result.is_succeeded = True
        except Exception as e:
            result.failure = e
        finally:
            callback(result)

