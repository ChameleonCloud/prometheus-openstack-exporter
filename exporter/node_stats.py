from base import OSBase
import json
from osclient import session_adapter, get_ironic_client
from prometheus_client import CollectorRegistry, generate_latest, Gauge
import logging

logger = logging.getLogger(__name__)

class NodeStats(OSBase):
    """Class to report the statistics on OpenStack Nodes"""

    def __init__(self, oscache, osclient):
        super(NodeStats, self).__init__(oscache, osclient)

    def build_cache_data(self):

        ironic_client = get_ironic_client()
        blazar_api = session_adapter('reservation')
        keystone_api = session_adapter('identity')
        nova_api = session_adapter('compute')

        nodes = ironic_client.node.list(detail=True)
        hosts = blazar_api.get('os-hosts?detail=True').json()['hosts']
        servers = nova_api.get(
            'servers/detail?all_tenants=True&status=ACTIVE').json()['servers']
        projects = keystone_api.get('v3/projects').json()['projects']
        freepool = nova_api.get('os-aggregates/1').json()['aggregate']['hosts']

        node_types = {
                h['hypervisor_hostname']: {
                    'node_type': h['node_type'],
                    'gpu': h['gpu.gpu'],
                }
                for h in hosts}

        hostname_key = 'OS-EXT-SRV-ATTR:hypervisor_hostname'
        project_names_by_id = {p['id']: p['name'] for p in projects}
        project_names_by_node = {
            s[hostname_key]: project_names_by_id[s['tenant_id']]
            for s in servers}

        cache_stats = (
            self._apply_labels(
                node, node_types, project_names_by_node, freepool)
            for node in nodes)

        return list(cache_stats)

    def _apply_labels(self, node, node_types, project_names_by_node, freepool):

        return dict(
            name=node.name,
            node_id=node.uuid,
            stat_value=1.0,
            maintenance=node.maintenance,
            provision_state=node.provision_state,
            node_type=node_types[node.uuid]['node_type'],
            gpu=node_types[node.uuid]['gpu'],
            project_name=project_names_by_node.get(node.uuid, None),
            reserved=not(node.uuid in freepool))

    def get_cache_key(self):
        return 'node_stats'

    def get_stats(self):
        registry = CollectorRegistry()
        labels = [
            'region',
            'name',
            'node_id',
            'maintenance',
            'provision_state',
            'node_type',
            'gpu',
            'project_name',
            'reserved']
        node_stats_cache = self.get_cache_data()
        for node_stat in node_stats_cache:
            stat_gauge = Gauge(
                'openstack_node_totals',
                'OpenStack Ironic Nodes statistic',
                labels,
                registry=registry)
            label_values = [
                self.osclient.region,
                node_stat.get('name', ''),
                node_stat.get('node_id', ''),
                node_stat.get('maintenance', ''),
                node_stat.get('provision_state', ''),
                node_stat.get('node_type', ''),
                node_stat.get('gpu', ''),
                node_stat.get('project_name', ''),
                node_stat.get('reserved', '')]
            stat_gauge.labels(*label_values).set(node_stat['stat_value'])
        return generate_latest(registry)
