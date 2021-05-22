# coding=utf-8
# author=torchcc
from uuid import uuid4
from typing import Union, List, NoReturn
from yarl import URL


class Config(object):

    def __init__(self, target_uri: Union[URL, str], target_service_name: str, router_uris: List[Union[URL, str]], component_name: str = "") -> None:
        """
        :param target_uri: e.g.: http:localhost:10086
        :param target_service_name: the path name when routing. e.g.: if the service hosts http://localhost:10086/my-service/ then the service name is "my-service"
        :param router_uris:  the cranker router registration web socket URIs it is going to connect, at least one is needed.
        :param component_name:
        """
        if isinstance(target_uri, str):
            target_uri = URL(target_uri)
        self.target_uri = target_uri
        self.target_service_name = target_service_name
        self.router_uris: List[URL] = []
        for uri in router_uris:
            if isinstance(uri, str):
                self.router_uris.append(URL(uri))
            elif isinstance(uri, URL):
                self.router_uris.append(uri)
            else:
                raise ValueError("URL must be str or yarl.URL type")
        self.component_name: str = component_name
        self.instance_id: str = str(uuid4())
        self.sliding_window_size: int = 2
        self.shutdown_hook_added: bool = False

    def set_sliding_window_size(self, sliding_window_size) -> NoReturn:
        """
        :param sliding_window_size: controls the idle socket windows of the pool size. please do not set this parameter unless you understand you need more
        """
        self.sliding_window_size = sliding_window_size

    def set_shutdown_hook_added(self, shutdown_hook_added: bool) -> NoReturn:
        self.shutdown_hook_added = shutdown_hook_added



