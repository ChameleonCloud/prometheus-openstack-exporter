from osclient import get_ironic_client, session_adapter

def get_nodes(detail=False):
    ironic = get_ironic_client()
    return ironic.node.list(detail=detail)


def add_project_names(nodes):
    nova_api = session_adapter('compute')
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

    for node in nodes:
        setattr()


def add_port_info(nodes):
    pass
