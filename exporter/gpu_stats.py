from base import OSBase
from collections import defaultdict
from osclient import session_adapter
from os import environ
from prometheus_client import CollectorRegistry, generate_latest, Gauge
import logging
import re

logger = logging.getLogger(__name__)

GRANULARITY = 60
FILL = 'null'
AGGREGATION_METHOD = 'mean'
LABELS = ['region', 'stat_name', 'gpu_type', 'gpu_index']


class GPUStats(OSBase):
    """Class to report the statistics on NVIDIA GPUs"""

    def __init__(self, oscache, osclient):
        super(GPUStats, self).__init__(oscache, osclient)

        self.gnocchi_api = session_adapter('metric')

    def build_cache_data(self):
        """Return list of stats to cache"""
        cache_stats = []

        for gpu_type, metrics in self.get_metrics_by_gpu_type().items():
            iter = 0

            for metric, gpu_indices in metrics.items():
                metric_name = str(metric).split('.')[-1]

                for gpu, metric_ids in gpu_indices.items():
                    stat = dict(
                        stat_name=metric_name,
                        gpu_type=gpu_type,
                        gpu_index=gpu)

                    stat['stat_value'] = self.get_aggregate(metric_ids)
                    cache_stats.append(stat)

                    # Add gpu count if first iteration
                    if iter == 0:
                        count = dict(
                            stat_name='gpu_count',
                            gpu_type=gpu_type,
                            gpu_index=gpu)

                        count['stat_value'] = len(metric_ids)
                        cache_stats.append(count)
                iter += 1

        return list(cache_stats)

    def get_gpu_type_by_resource_id(self):
        """Return dict of blazar hosts by hypervisor hostname."""
        blazar_api = session_adapter('reservation')
        hosts = blazar_api.get('os-hosts?detail=True').json()['hosts']

        return {
            h['hypervisor_hostname']: h['node_type']
            for h in hosts
            if h['gpu.gpu']}

    def get_metrics_by_gpu_type(self):
        """Return dict of metrics for resource type cuda from gnocchi."""
        cuda_resouce_url = 'v1/search/resource/cuda'
        req = self.gnocchi_api.post(cuda_resouce_url)

        resources = req.json()
        resource_gpu_types = self.get_gpu_type_by_resource_id()
        metrics_by_gpu_type = {}

        for resource in resources:
            resource_id = resource['id']
            gpu_type = resource_gpu_types[resource_id]

            if gpu_type not in metrics_by_gpu_type:
                metrics_by_gpu_type[gpu_type] = {}

            metrics = resource['metrics']

            for metric, metric_id in metrics.items():
                gpu_index = re.findall(r'\d+', str(metric))[0]

                if metric not in metrics_by_gpu_type[gpu_type]:
                    metrics_by_gpu_type[gpu_type][metric] = defaultdict(list)

                metrics_by_gpu_type[gpu_type][str(metric)][gpu_index].append(
                    str(metric_id))

        return metrics_by_gpu_type

    def get_aggregate(self, metric_ids):
        """Get aggregation measures for one or more metrics."""
        metric_params = 'metric={}'.format('&metric='.join(metric_ids))
        aggregation_param = 'aggregation={}'.format(AGGREGATION_METHOD)
        fill_param = 'fill={}'.format(FILL)
        granularity_param = 'granularity={}'.format(str(GRANULARITY))

        url = "{endpoint}?{metrics}&{aggregation}&{fill}&{granularity}".format(
            endpoint='v1/aggregation/metric',
            metrics=metric_params,
            aggregation=aggregation_param,
            fill=fill_param,
            granularity=granularity_param)

        req = self.gnocchi_api.get(url)
        stat_value = req.json()[-1][-1]

        return stat_value

    def get_cache_key(self):
        return 'gpu_stats'

    def get_stats(self):
        registry = CollectorRegistry()
        gpu_stats_cache = self.get_cache_data()
        for gpu_stat in gpu_stats_cache:
            stat_gauge = Gauge(
                'gnocchi_gpu_stats',
                'Gnocchi GPU statistics',
                LABELS,
                registry=registry)
            label_values = [self.osclient.region] + [
                gpu_stat.get(x, '') for x in LABELS[1:]]
            stat_gauge.labels(*label_values).set(gpu_stat['stat_value'])
        return generate_latest(registry)
