FROM          ubuntu:16.04
MAINTAINER    Rakesh Patnaik (patsrakesh@gmail.com)

RUN           apt-get -y update \
              && apt-get -y install curl python-pip python-dev\
              && apt-get clean \
              && rm -rf /var/lib/apt/lists/*

COPY          requirements.txt /usr/local/bin/
RUN           pip install -r /usr/local/bin/requirements.txt  

RUN           mkdir /usr/local/bin/exporter
COPY          exporter /usr/local/bin/exporter
RUN           chmod +x /usr/local/bin/exporter/main.py

EXPOSE        9103

CMD           ["/usr/local/bin/exporter/main.py"]
