# coding=utf-8
# author=torchcc
from abc import ABCMeta, abstractmethod
from copy import deepcopy
from typing import NoReturn, List, Optional

__all__ = [
    "HeadersBuilder",
    "ProtocolRequestBuilder",
    "ProtocolResponseBuilder",
    "ProtocolRequest",
    "ProtocolResponse",
    "CrankerProtocolVersion10",
]

SupportingHttpVersion = "HTTP/1.1"
CrankerProtocolVersion10 = "1.0"

RequestBodyPendingMarker = "_1"
RequestHasNoBodyMarker = "_2"
RequestBodyEndedMarker = "_3"


class IProtocolMsg(metaclass=ABCMeta):
    @abstractmethod
    def to_protocol_msg(self):
        pass


class HeadersBuilder(object):

    def __init__(self):
        self._headers: str = ""

    def append_header(self, header: str, value: str) -> NoReturn:
        self._headers += header + ":" + value + "\n"

    def append_headers(self, headers: List[str]) -> NoReturn:
        for h in headers:
            self._headers += h + "\n"

    def __str__(self) -> str:
        return self._headers

    __repr__ = __str__


"""
 CRANKER PROTOCOL_ VERSION_1_0
 request msg format:
 <p>
 ==== msg without body =====
  GET /modules/uui-allocation/1.0.68/uui-allocation.min.js.map HTTP/1.1\n
  [headers]\n
  \n
  endmarker
 <p>
 <p>
 OR
 <p>
 ==== msg with body part 1 ====
  GET /modules/uui-allocation/1.0.68/uui-allocation.min.js.map HTTP/1.1\n
  [headers]\n
  \n
  endmarker
 ==== msg with body part 2 ====
 [BINARY BODY]
 ==== msg with body part 3 ====
  endmarker
"""


# Request from router to connector
class ProtocolRequest(IProtocolMsg):

    def to_protocol_msg(self):
        if self._req_line is not None and self.headers is not None:
            headers_str = ""
            for hl in self.headers:
                headers_str += hl + "\n"
            return self._req_line + "\n" + headers_str + self._end_marker
        else:
            return self._end_marker

    def __init__(self, msg: str) -> None:

        self.method: str = ""
        self.dest: str = ""
        self.headers: List[str] = []
        self._end_marker: str = ""
        self._req_line: str = ""

        if msg == RequestBodyEndedMarker:
            self._end_marker = msg
        else:
            msg_arr = msg.split("\n")
            self._req_line = req = msg_arr[0]
            bits = req.split(" ")
            self.method = bits[0]
            self.dest = bits[1]
            self.headers = deepcopy(msg_arr[1:-1])
            self._end_marker = msg_arr[-1]

    def req_body_pending(self) -> bool:
        return self._end_marker == RequestBodyPendingMarker

    def req_has_no_body(self) -> bool:
        return self._end_marker == RequestHasNoBodyMarker

    def req_body_ended(self) -> bool:
        return self._end_marker == RequestBodyEndedMarker

    def __str__(self) -> str:
        return "ProtocolRequest{" + self.method + " " + self.dest + "}"

    __repr__ = __str__


class ProtocolRequestBuilder(object):

    def __init__(self) -> None:
        self._req_line: str = ""
        self._headers: Optional[HeadersBuilder] = None
        self._end_marker: str = ""

    @staticmethod
    def new_builder() -> "ProtocolRequestBuilder":
        return ProtocolRequestBuilder()

    def with_req_line(self, req_line: str) -> "ProtocolRequestBuilder":
        self._req_line = req_line
        return self

    def with_req_headers(self, headers: HeadersBuilder) -> "ProtocolRequestBuilder":
        self._headers = headers
        return self

    def with_req_body_pending(self) -> "ProtocolRequestBuilder":
        self._end_marker = RequestBodyPendingMarker
        return self

    def with_req_has_no_body(self) -> "ProtocolRequestBuilder":
        self._end_marker = RequestHasNoBodyMarker
        return self

    def with_req_body_ended(self) -> "ProtocolRequestBuilder":
        self._end_marker = RequestBodyEndedMarker
        return self

    def build(self) -> str:
        if self._req_line is not None and self._headers is not None:
            return self._req_line + "\n" + str(self._headers) + "\n" + self._end_marker


""" 
 CRANKER PROTOCOL_ VERSION_1_0
 <p>
 response msg format:
 <p>
 ==== part 1 ====
  HTTP/1.1 200 OK\n
  GET /appstore/api/health
  [headers]\n
  \n
 ==== part 2 (if msg has body) ====
  Binary Content
 """


class ProtocolResponseBuilder(object):

    def __init__(self) -> None:
        self._src_url: str = ""
        self._method: str = ""
        self._status: int = 0
        self._reason: str = ""
        self._headers: Optional[HeadersBuilder] = None

    @staticmethod
    def new_builder() -> "ProtocolResponseBuilder":
        return ProtocolResponseBuilder()

    def with_resp_status(self, status: int) -> "ProtocolResponseBuilder":
        self._status = status
        return self

    def with_resp_reason(self, reason: str) -> "ProtocolResponseBuilder":
        self._reason = reason
        return self

    def with_resp_headers(self, headers: HeadersBuilder) -> "ProtocolResponseBuilder":
        self._headers = headers
        return self

    def with_src_url(self, req_dest: str) -> "ProtocolResponseBuilder":
        self._src_url = req_dest
        return self

    def with_method(self, method: str) -> "ProtocolResponseBuilder":
        self._method = method
        return self

    def build(self) -> str:
        return SupportingHttpVersion + " " + str(self._status) + " " + self._reason + "\n" + self._method + " " + self._src_url + "\n" + str(self._headers)


# response from connector to router
class ProtocolResponse(IProtocolMsg):

    def __init__(self, msg: str) -> None:
        self.headers: List[str] = []
        self.status: int = 0
        self._reason: str = ""
        self.src_url: str = ""
        self.method: str = ""

        msg_arr = msg.split("\n")
        bits = msg_arr[0].split(" ")
        self.status = int(bits[1])
        if len(bits) >= 3:
            self._reason = bits[2]

        origin_req: str = msg_arr[1]
        req_bits: List[str] = origin_req.split(" ")
        self.method = req_bits[0]
        if len(req_bits) >= 2:
            self.src_url = req_bits[1]
        self.headers = deepcopy(msg_arr[2:])

    def to_protocol_msg(self):
        builder = HeadersBuilder()
        builder.append_headers(self.headers)
        return ProtocolResponseBuilder().with_method(
            self.method).with_src_url(
            self.src_url).with_resp_reason(
            self._reason).with_resp_status(
            self.status).with_resp_headers(
            builder).build()

    def __str__(self) -> str:
        return "CrankerProtocolResponse{" + \
               "headers=" + str(self.headers) + \
               ", status=" + str(self.status) + \
               ", reason=" + self._reason + \
               ", sourceUrl=" + self.src_url + \
               ", httpMethod=" + self.method + \
               "}"

    __repr__ = __str__

