from base import OSBase
from prometheus_client import CollectorRegistry, generate_latest, Gauge
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s:%(levelname)s:%(message)s")
logger = logging.getLogger(__name__)

class NodeStats(OSBase):

	VALUE_MAP = {
		''
	}

	def __init__(self, oscache, osclient):
		super(NodeStats, self).__init__(oscache, osclient)

	def build_cache_data(self):

		r = self.osclient.get('ironic', 'os-nodes/detail')

		if not r:
			logger.warning("Could not get ironic nodes.")
			return

		node_list = r.json().get("nodes", [])

		cache_stats = (
			self._apply_labels(node) for node in node_list)
		
		return list(cache_stats)

	def _labels(self, node):
		return dict(
			name=node['name'],
			stat_value=1.0,
			maintenance=node['maintenance'],
			provision_state=node['provision_state'])

	def get_cache_key(self):
		return 'baremetal_stats'

	def get_stats(self):
		registry = CollectorRegistry()
		labels = ['region', 'name']
		node_stats_cache = self.get_cache_data()
		for node_stat in node_stats_cache:
			stat_gauge = Gauge(
				'ironic_node_totals',
				'OpenStack Ironic Nodes statistic',
				labels,
				registry=registry)
			label_values = [
				self.osclient.region,
				node_stat.get('name', ''),
				node_stat.get('maintenance', ''),
				node_stat.get('provision_state', '')]
			stat_gauge.labels(*label_values).set(baremetal_stat['stat_value'])
		return generate_latest(registry)
