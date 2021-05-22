import os
from pathlib import Path

from flask import send_from_directory, request
from werkzeug.utils import secure_filename

here = Path(__file__).resolve().parent
here = os.path.join(here, "templates")


def start_flask_and_connector():
    from flask import Flask, render_template
    from crank4py_connector import Config
    from crank4py_connector import create_and_start_connector

    router_uris = ["wss://localhost:9070", "wss://localhost:9070"]
    my_service_uri = "http://localhost:5000"
    config = Config(my_service_uri, "service-a", router_uris, component_name="service-a-component")
    connector = create_and_start_connector(config)

    app = Flask(__name__, static_url_path='')
    app.config['UPLOAD_FOLDER'] = here

    @app.route("/service-a/hello.html")
    def hello():
        return send_from_directory(here, "hello.html")

    @app.route("/service-a/hi")
    def hi():
        return "hi"

    @app.route('/service-a/upload', methods=['GET', 'POST'])
    def upload_file():
        if request.method == 'POST':
            file = request.files['file']
            if file:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                return "uploaded"

        return '''
        <!doctype html>
        <title>Upload new File</title>
        <h1>Upload new File</h1>
        <form action="" method=post enctype=multipart/form-data>
          <p><input type=file name=file>
             <input type=submit value=Upload>
        </form>
        '''

    app.run(host="localhost", port=5000)

if __name__ == '__main__':
    start_flask_and_connector()