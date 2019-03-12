from base import OSBase
from osclient import session_adapter, get_ironic_client
from os import environ
from prometheus_client import CollectorRegistry, generate_latest, Gauge
import logging
import re

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
        self.ironic_client = get_ironic_client()
        self.keystone_api = session_adapter('identity')

    def build_cache_data(self):
        """Return list of stats to cache."""
        cache_stats = []

        ports = self.get_ports_by_corsa_idx()
        nodes = self.get_nodes_by_id()
        projects = self.get_projects_by_id()

        for switch in self.corsa_configs:
            corsa_client = CorsaClient(
                switch.get('address'),
                switch.get('token'),
                verify=switch.get('ssl_verify', True))

            port_stats = corsa_client.get_stats_ports()

            for stat in port_stats['stats']:
                for key, value in stat.items():
                    if key not in CORSA_STATS_TO_COLLECT:
                        continue

                    port = ports.get(stat['port'])

                    if not port:
                        continue
                    if port.switch_info != switch['name']:
                        continue

                    node = nodes[port.uuid]
                    project = node.get(node['project_id'], {})

                    corsa_stat = dict(
                        stat_name='corsa_{}'.format(key),
                        switch=switch['name'],
                        port=stat['port'],
                        node=node.name,
                        provision_stat=node.provision_state,
                        project_name=project['name'],
                        stat_value=value)

                    cache_stats.append(corsa_stat)
        return cache_stats

    def get_ports_by_corsa_idx(self):
        """Return mapping of Corsa port numbers to baremetal port uuids."""
        ports = self.ironic_client.port.list(detail=True)
        return {
            p.local_link_connection['port_id'].split()[-1]: p
            for p in ports}

    def get_nodes_by_id(self):
        """Return dicitonary of baremetal node objects by uuid."""
        nodes = self.ironic_client.node.list()
        return {n.uuid: n for n in nodes}

    def get_projects_by_id(self):
        """Return mapping of project uuids to project names."""
        projects = self.keystone_api.get('v3/projects').json()['projects']
        return {p['id']: p['name'] for p in projects}

    def get_cache_key(self):
        return 'corsa_stats'

    def get_stats(self):
        registry = CollectorRegistry
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
