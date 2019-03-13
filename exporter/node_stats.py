from base import OSBase
import json
from osclient import session_adapter, get_ironic_client
from utils import node_details
from prometheus_client import CollectorRegistry, generate_latest, Gauge
import logging

logger = logging.getLogger(__name__)

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
        nodes = node_details.get_nodes(detail=True)

        cache_stats = (self._apply_labels(node) for node in nodes)

        return list(cache_stats)

    def _apply_labels(self, node):
        return dict(
            name=node.name,
            node_id=node.uuid,
            stat_value=1.0,
            maintenance=node.maintenance,
            provision_state=node.provision_state,
            node_type=node.node_type,
            gpu='gpu_' in node.node_type,
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
