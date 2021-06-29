# coding=utf-8
# author=torchcc

import setuptools
from distutils.util import convert_path

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

main_ns = {}
version_path = convert_path("crank4py_connector/version.py")
with open(version_path) as ver_file:
    exec(ver_file.read(), main_ns)

setuptools.setup(
    name="crank4py_connector",
    version=main_ns["version"],
    author="torchcc",
    author_email="1553765526@qq.com",
    description="A python library that allows web services to be registered to one or more cranker routers(Api gateway)",
    long_description=long_description,
    install_requires=[
        "websocket-client==1.1.0",
        "requests",
        "yarl",
    ],
    long_description_content_type="text/markdown",
    url="https://github.com/torchcc/crank4py-connector",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
