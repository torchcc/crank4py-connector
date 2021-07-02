crank4y-connector
-----

1. A python library that allows you to register python web service to one or more `API GATEWAY` [cranker routers](https://github.com/torchcc/crank4go)
2. it is the client endpoint of a `API GATEWAY` 

### Dependencies:
1. python >= 3.6
2. numpy(optional, for better performance)
3. requests
4. yarl
5. websocket-client == 1.1.0 

Usage
---

- There are mainly 4 steps:
  1. `pip install crank4py-connector`
  2. create a web service that hosts al requests on some path prefix, e.g. `/service-a/...`
  3. start a web service on a random port 
  4. construct a `Config` object and start a connector 
  
- example

```python
from flask import Flask
from crank4py_connector import Config
from crank4py_connector import create_and_start_connector

# suppose the contextpath of your py service is `service-a`
router_uris = ["wss://localhost:9070", "wss://localhost:9070"]  # the api gateway router instances which you want to register to
my_service_uri = "http://localhost:5000"  
config = Config(my_service_uri, "service-a", router_uris, component_name="service-a-component")
connector = create_and_start_connector(config)

app = Flask(__name__, static_url_path="")
@app.route("/service-a/hello")
def hello():
    return "hello"
app.run(host="localhost", port=5000) # port can be any random ephermeral port

# or you can refer to crank4py_connector
# and then you can query your api gateway to access your server-a. e.g. if your router listens on https://localhost:9000, then you can access  https://localhost:9000/service-a/hello,
```


