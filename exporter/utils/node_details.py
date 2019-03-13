from osclient import get_ironic_client, session_adapter

FREEPOOL_AGGREGATE_ID = 1


def get_nodes(detail=False):
    """Return list of ironic client node objects."""
    ironic_client = get_ironic_client()

    nodes = ironic_client.node.list(detail=detail)
    add_project_names(nodes)
    add_node_type(nodes)

    return nodes


def add_project_names(nodes):
    """Add project names to list of ironic client node objects."""
    nova_api = session_adapter('compute')
    keystone_api = session_adapter('identity')

    aggregates = nova_api.get('os-aggregates').json()['aggregates']
    projects = keystone_api.get('v3/projects').json()['projects']

    project_names = {p['id']: p['name'] for p in projects}
    reservations = dict()

    for agg in aggregates:
        # Ignore projects in freepool
        if agg['id'] == FREEPOOL_AGGREGATE_ID or not agg['hosts']:
            continue

        project_id = agg['metadata']['blazar:owner']

        for node_id in agg['hosts']:
            reservations[node_id] = project_names[project_id]

    for node in nodes:
        if node.uuid in reservations:
            setattr(node, 'project_name', reservations[node.uuid])
        else:
            setattr(node, 'project_name', None)


def add_node_type(nodes):
    """Add node_type to list of ironic client node objects."""
    blazar_api = session_adapter('reservation')
    hosts = blazar_api.get('os-hosts?detail=True').json()['hosts']

    node_types = {h['hypervisor_hostname']: h['node_type'] for h in hosts}

    for node in nodes:
        setattr(node, 'node_type', node_types[node.uuid])


def add_port_info(nodes, detail=True):
    """Add ironic port object to list of ironic client node objects."""
    ironic_client = get_ironic_client()
    ports = ironic_client.port.list(detail=detail)

    ports_by_node = {p.node_uuid: p for p in ports}

    for node in nodes:
        setattr(node, 'port', ports_by_node[node.uuid])
