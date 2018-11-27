from base import OSBase
from osclient import get_keystone_session
from prometheus_client import CollectorRegistry, generate_latest, Gauge
import logging

logger = logging.getLogger(__name__)

GNOCCHI_ENDPOINT = 'https://chi.tacc.chameleoncloud.org:8041/v1'
GRANULARITY = 60
AGGREGATION_METHOD = 'max'
LABELS = ['region', 'stat_name']


class GPUStats(OSBase):
    """Class to report the statistics on NVIDIA GPUs"""

    def __init__(self, oscache, osclient):
        super(GPUStats, self).__init__(oscache, osclient)

        self.sess = get_keystone_session()

    def build_cache_data(self):
        """Return list of stats to cache"""
        metrics = self.get_cuda_metrics()
        cache_stats = (self.get_aggregate(*x) for x in metrics.items())

        return list(cache_stats)

    def get_cuda_metrics(self):
        """Return dict of metrics for resource type cuda from gnocchi."""
        cuda_resouce_url = GNOCCHI_ENDPOINT + '/search/resource/cuda'
        req = self.sess.post(cuda_resouce_url)

        metric_dict = req.json()['metrics']
        metrics_by_name = {}

        for metric, metric_id in metric_dict.items():
            metric_name = str(metric).split('.')[-1]

            if metric_name in metrics_by_name.keys():
                metrics_by_name[metric_name] = []

            metrics_by_name[metric_name].append(str(metric_id))

        return metrics_by_name

    def get_aggregate(self, metric_name, metric_ids):
        """Get aggregation measures for one or more metrics."""
        metric_params = 'metric={}'.format('&metric='.join(metric_ids))
        aggregation_param = 'aggregation={}'.format(AGGREGATION_METHOD)
        granularity_param = 'granularity={}'.format(str(GRANULARITY))

        url = '{endpoint}?{metrics}&{aggregation}&{granularity}'.format(
            endpoint=GNOCCHI_ENDPOINT + '/aggregation/metric',
            metrics=metric_params,
            aggregation=aggregation_param,
            granularity=granularity_param)

        req = self.sess.get(url)
        stat_value = req.json()[-1][-1]

        return dict(stat_name=metric_name, stat_value=stat_value)

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
