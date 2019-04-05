from base import OSBase
from osclient import session_adapter
from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client import Counter as prometheus_counter
from utils import node_details
from datetime import datetime, timedelta
from collections import Counter, namedtuple
import logging

logger = logging.getLogger(__name__)

LABELS = [
    'region',
    'project_id',
    'project_name']


class LaunchFailures(OSBase):
    """Class to report the statistics on OpenStack Nodes"""

    def __init__(self, oscache, osclient):
        super(LaunchFailures, self).__init__(oscache, osclient)
        self.refresh_interval = oscache.refresh_interval
        self.registry = CollectorRegistry()
        self.project_counters = {}

    def build_cache_data(self):
        """
        Return list of stats to cache.

        TODO>> Add prometheus Counter paradigm to main functionality.

        This does not return items to cache because prometheus Counter cannnot
        be cached. However, this function is called in the main workflow to
        initiate scraping of data so rather than return a list of data to
        cache, it creates new prometheus counters or increments counters
        stored in the object itself. This way get_stats need only return
        what is generated from the registry.
        """
        launch_failures = self.get_launch_failures()

        for launch_failure in launch_failures:
            label_values = [self.osclient.region] + [
                getattr(launch_failure, x, '') for x in LABELS[1:]]
            if launch_failure.project_id in self.project_counters:
                self.project_counters[launch_failure.project_id].labels(
                    *label_values).inc(launch_failure.stat_value)
            else:
                stat_counter = prometheus_counter(
                    'launch_failure',
                    'OpenStack Launch Failures by Project',
                    LABELS,
                    registry=self.registry)
                stat_counter.labels(*label_values).inc(
                    launch_failure.stat_value)
                self.project_counters[
                    launch_failure.project_id] = stat_counter
        return []

    def get_launch_failures(self):
        """Return list of stats to cache."""
        nova_api = session_adapter('compute')
        keystone_api = session_adapter('identity')

        nodes = node_details.get_nodes(detail=True)
        servers = nova_api.get(
            'servers/detail?all_tenants=True').json()['servers']

        projects = keystone_api.get('v3/projects').json()['projects']
        project_names = {p['id']: p['name'] for p in projects}

        LaunchFailure = namedtuple(
            'LaunchFailure',
            ['project_id', 'project_name', 'stat_value'])

        instance_failures = [
            LaunchFailure(
                s['tenant_id'],
                project_names.get(s['tenant_id']),
                None)
            for s in servers
            if self._valid_failure(s['status'] == 'ERROR', s['updated'])]

        node_failures = [
            LaunchFailure(n.project_id, n.project_name, None)
            for n in nodes
            if self._valid_failure(n.last_error is not None, n.updated_at)
        ]

        return [
            k._replace(stat_value=v) for k, v
            in Counter(instance_failures + node_failures).items()]

    def _valid_failure(self, error, update_time):
        update_time = datetime.strptime(
            update_time[:19], '%Y-%m-%dT%H:%M:%S')
        time_since_scrape = (
            datetime.utcnow() - timedelta(0, self.refresh_interval))

        return error and (update_time > time_since_scrape)

    def get_cache_key(self):
        return 'launch_failures'

    def get_stats(self):
        return generate_latest(self.registry)
