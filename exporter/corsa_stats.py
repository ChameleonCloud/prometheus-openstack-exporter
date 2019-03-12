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
        self.keystone_api = session_adapter('identity')
        self.nova_api = session_adapter('compute')

    def build_cache_data(self):
        """Return list of stats to cache."""
        cache_stats = []

        nodes = node_details.get_nodes()
        node_details.add_project_names(nodes)
        node_details.add_port_info(nodes)

        for switch in self.corsa_configs:
            corsa_client = CorsaClient(
                switch.get('address'),
                switch.get('token'),
                verify=switch.get('ssl_verify', True))

            switch_nodes = {
                n.port.local_link_connection['port_id'].split()[-1]: n
                for n in nodes
                if n.port.local_link_connection[
                    'switch_info'] == switch['name']
            }

            port_stats = corsa_client.get_stats_ports()

            for stat in port_stats['stats']:
                for key, value in stat.items():
                    if key not in CORSA_STATS_TO_COLLECT:
                        continue

                    node = switch_nodes[stat['port']]
                    corsa_stat = dict(
                        stat_name='corsa_{}'.format(key),
                        switch=switch['name'],
                        port=stat['port'],
                        node=node.name,
                        provision_stat=node.provision_state,
                        project_name=node.project_name,
                        stat_value=value)

                    cache_stats.append(corsa_stat)
        return cache_stats

    def get_project_names_by_node(self):
        """Return dict of reserved nodes and their project names."""
        aggregates = nova_api.get('os-aggregates').json()['aggregates']
        project_names = self.get_projects_by_id()

        reservations = dict()

        for agg in aggregates:
            # Ignore projects in freepool
            if agg['id'] == FREEPOOL_AGGREGATE_ID or not agg['hosts']:
                continue

            project_id = agg['metadata']['blazar:owner']

            for node_id in agg['hosts']:
                reservations[node_id] = project_names[project_id]

        return reservations

    def get_nodes_by_corsa_port(self):
        nodes = self.ironic_client_node.list()
        ports = self.ironic_client.port.list(detail=True)
        project_names = self.get_project_names_by_node()

        for node in nodes:
            setattr(node, 'port', )
            setattr(node, 'project_name', project_names.get())

        return nodes

    def get_ports_by_corsa_port(self):
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
