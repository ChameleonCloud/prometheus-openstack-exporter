from base import OSBase
from prometheus_client import CollectorRegistry, generate_latest, Gauge
from osclient import get_python_osclient
from itertools import chain
import logging
loggin.basicConfig(
	)

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

		nodes_total = (
			self._nodes_total(node) for node in node_list)
		nodes_provisioned = (
			self._check_node_provisioned(node) for node in node_list)
		nodes_maintenance = (
			self._check_maintenance_mode(node) for node in node_list)
		
		cache_stats = chain(
			nodes_total, nodes_provisioned, nodes_maintenance)

		return list(cache_stats)

	def _nodes_total(self, node):
		return dict(
			name=node['name'],
			stat_name='total_nodes',
			stat_value=1)

	def _check_node_provisioned(self, node):
		return dict(
			name=node['name'],
			stat_name='provisioned_nodes',
			stat_value=int(node['provision_state'] == 'active'))

	def _check_maintenance_mode(self, node):
		return dict(
			name=node['name'],
			stat_name='maintenance_mode_nodes',
			stat_value=int(node['maintenance']))

	def get_cache_key(self):
		return 'baremetal_stats'

	def get_stats(self):
		registry = CollectorRegistry()
		labels = []
		baremetal_stats_cache = self.get_cache_data()

		for baremetal_stat in baremetal_stats_cache:
			stat_gauge = Gauge(
				self.gauge_name_sanitize(
					baremetal_stat['stat_name']),
				'OpenStack Baremetal statistic',
				labels,
				registry=registry)
			label_values = []
			stat_gauge.labels(*label_values).set(baremetal_stat['stat_value'])
		return generate_latest(registry)
