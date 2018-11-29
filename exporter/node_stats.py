from base import OSBase
import json
from osclient import session_adapter, get_ironic_client
from prometheus_client import CollectorRegistry, generate_latest, Gauge
import logging

logger = logging.getLogger(__name__)

FREEPOOL_AGGREGATE_ID = 1
LABELS = [
    'region',
    'name',
    'node_id',
    'maintenance',
    'provision_state',
    'node_type',
    'gpu',
    'project_name']


class NodeStats(OSBase):
    """Class to report the statistics on OpenStack Nodes"""

    def __init__(self, oscache, osclient):
        super(NodeStats, self).__init__(oscache, osclient)

    def build_cache_data(self):
        """Return list of stats to cache."""
        nodes = self.get_nodes()
        hosts = self.get_hosts_by_node_id()
        reservations = self.get_reservations_by_node_id()

        for node in nodes:
            node.node_type = hosts[node.uuid]['node_type']
            node.gpu = hosts[node.uuid]['gpu']
            node.project_name = reservations.get(node.uuid, None)

        cache_stats = (self._apply_labels(node) for node in nodes)

        return list(cache_stats)

    def get_nodes(self):
        """Return list of node objects returned by ironic client."""
        ironic_client = get_ironic_client()
        nodes = ironic_client.node.list(detail=True)

        # Add extra attrs to node objects
        def add_extra_attrs(node):
            setattr(node, 'node_type', None)
            setattr(node, 'gpu', None)
            setattr(node, 'project_name', None)
            return node

        return [add_extra_attrs(n) for n in nodes]

    def get_hosts_by_node_id(self):
        """Return dict of blazar hosts by hypervisor hostname."""
        blazar_api = session_adapter('reservation')
        hosts = blazar_api.get('os-hosts?detail=True').json()['hosts']

        return {
            h['hypervisor_hostname']:
                {'node_type': h['node_type'], 'gpu': h['gpu.gpu']}
            for h in hosts}

    def get_reservations_by_node_id(self):
        """Return dict of reserved nodes and their project names."""
        nova_api = session_adapter('compute')
        aggregates = nova_api.get('os-aggregates').json()['aggregates']
        project_names = self.get_project_names_by_id()

        reservations = dict()

        for agg in aggregates:
            # Ignore projects in freepool
            if agg['id'] == FREEPOOL_AGGREGATE_ID or not agg['hosts']:
                continue

            project_id = agg['metadata']['blazar:owner']

            for node_id in agg['hosts']:
                reservations[node_id] = project_names[project_id]

        return reservations

    def get_project_names_by_id(self):
        """Return dict of project id and names."""
        keystone_api = session_adapter('identity')
        projects = keystone_api.get('v3/projects').json()['projects']

        return {p['id']: p['name'] for p in projects}

    def _apply_labels(self, node):
        return dict(
            name=node.name,
            node_id=node.uuid,
            stat_value=1.0,
            maintenance=node.maintenance,
            provision_state=node.provision_state,
            node_type=node.node_type,
            gpu=node.gpu,
            project_name=node.project_name)

    def get_cache_key(self):
        return 'node_stats'

    def get_stats(self):
        registry = CollectorRegistry()
        labels = LABELS
        node_stats_cache = self.get_cache_data()
        for node_stat in node_stats_cache:
            stat_gauge = Gauge(
                'openstack_node_totals',
                'OpenStack Ironic Nodes statistic',
                labels,
                registry=registry)
            label_values = [self.osclient.region] + [
                node_stat.get(x, '') for x in LABELS[1:]]
            stat_gauge.labels(*label_values).set(node_stat['stat_value'])
        return generate_latest(registry)
