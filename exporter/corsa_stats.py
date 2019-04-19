from base import OSBase
from osclient import session_adapter, get_ironic_client
from os import environ
from prometheus_client import CollectorRegistry, generate_latest, Gauge
from utils import node_details
import logging
import re
import requests

logger = logging.getLogger(__name__)

GRANULARITY = 60
FILL = 'null'
AGGREGATION_METHOD = 'mean'
LABELS = [
    'region',
    'switch',
    'port',
    'node',
    'provision_state',
    'node_type',
    'project_name',
]
CORSA_STATS_TO_COLLECT = [
    'tx_packets',
    'tx_errors',
    'tx_bytes',
    'tx_dropped',
    'rx_packets',
    'rx_errors',
    'rx_bytes',
    'rx_dropped'
]


class CorsaClient():
    """Corsa API Client"""

    def __init__(self, address, token, verify=None):
        self.address = address
        self.token = token
        self.verify = verify
        self.api_base = '/api/v1'

    def get_path(self, path):
        headers = {'Authorization': self.token}
        url = '{}{}{}'.format(self.address, self.api_base, path)
        resp = requests.get(url, headers=headers, verify=self.verify)
        return resp.json()

    def get_stats_ports(self, port=None):
        path = '/stats/ports'
        if port:
            path = path + '?port=' + str(port)
        return self.get_path(path)


class CorsaStats(OSBase):
    """Class to report network statistics from CorsaSwitches"""

    def __init__(self, oscache, osclient, corsa_configs):
        super(CorsaStats, self).__init__(oscache, osclient)

        self.corsa_configs = corsa_configs

    def build_cache_data(self):
        """Return list of stats to cache."""
        cache_stats = []
        nodes = node_details.get_nodes()
        node_details.add_port_info(nodes)

        for switch in self.corsa_configs:
            corsa_client = CorsaClient(
                switch.get('address'),
                switch.get('token'),
                verify=switch.get('ssl_verify', True))

            def check_switch(switch_name):
                return switch_name == switch['name']

            switch_nodes = {
                n.port.local_link_connection['port_id'].split()[-1]: n
                for n in nodes
                if check_switch(n.port.local_link_connection['switch_info'])
            }

            port_stats = corsa_client.get_stats_ports()

            for stat in port_stats['stats']:
                for key, value in stat.items():
                    if key not in CORSA_STATS_TO_COLLECT:
                        continue

                    node = switch_nodes.get(stat['port'])

                    if not node:
                        continue

                    corsa_stat = dict(
                        stat_name='corsa_{}'.format(key),
                        switch=switch['name'],
                        port=stat['port'],
                        node=node.name,
                        provision_state=node.provision_state,
                        project_name=node.project_name,
                        stat_value=value)

                    cache_stats.append(corsa_stat)
        return cache_stats

    def get_cache_key(self):
        return 'corsa_stats'

    def get_stats(self):
        registry = CollectorRegistry()
        corsa_stats_cache = self.get_cache_data()
        for corsa_stat in corsa_stats_cache:
            stat_gauge = Gauge(
                corsa_stat.get('stat_name'),
                'Corsa Port Stat Statistics',
                LABELS,
                registry=registry)
            label_values = [self.osclient.region] + [
                corsa_stat.get(x, '') for x in LABELS[1:]]
            stat_gauge.labels(*label_values).set(corsa_stat['stat_value'])
        return generate_latest(registry)
