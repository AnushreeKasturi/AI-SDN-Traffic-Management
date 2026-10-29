"""
topology.py
Defines the simulated SDN network topology.

We model a small enterprise/campus network:
    - 8 OpenFlow switches (s1..s8) forming a partial mesh (multiple paths exist
      between most switch pairs, which is what makes adaptive routing useful)
    - 6 hosts (h1..h6) attached to edge switches
    - Every link has a capacity (Mbps) and a base propagation delay (ms)

This is deliberately similar to a topology you would build in Mininet with
`addLink(s1, s2, bw=100, delay='2ms')`, so the same graph could later be
dropped into a real Mininet + Ryu/POX setup with minimal changes.
"""

import networkx as nx


def build_topology() -> nx.Graph:
    G = nx.Graph()

    switches = [f"s{i}" for i in range(1, 9)]
    hosts = [f"h{i}" for i in range(1, 7)]

    G.add_nodes_from(switches, kind="switch")
    G.add_nodes_from(hosts, kind="host")

    # Core switch mesh (partial mesh -> redundant paths between s1 and s8)
    core_links = [
        ("s1", "s2", 100, 2),
        ("s1", "s3", 100, 3),
        ("s2", "s4", 80, 2),
        ("s3", "s4", 60, 2),
        ("s2", "s5", 60, 4),
        ("s3", "s6", 80, 3),
        ("s4", "s7", 100, 2),
        ("s5", "s7", 60, 2),
        ("s6", "s7", 60, 2),
        ("s5", "s8", 80, 3),
        ("s6", "s8", 100, 2),
        ("s7", "s8", 100, 1),
    ]
    for u, v, bw, delay in core_links:
        G.add_edge(u, v, capacity_mbps=bw, base_delay_ms=delay, kind="core")

    # Edge (access) links connecting hosts to switches
    edge_links = [
        ("h1", "s1", 1000, 0.5),
        ("h2", "s2", 1000, 0.5),
        ("h3", "s3", 1000, 0.5),
        ("h4", "s6", 1000, 0.5),
        ("h5", "s7", 1000, 0.5),
        ("h6", "s8", 1000, 0.5),
    ]
    for u, v, bw, delay in edge_links:
        G.add_edge(u, v, capacity_mbps=bw, base_delay_ms=delay, kind="edge")

    return G


HOST_PAIRS = [
    ("h1", "h6"),
    ("h2", "h5"),
    ("h3", "h4"),
    ("h1", "h5"),
    ("h2", "h6"),
    ("h4", "h5"),
]



def build_nsfnet() -> nx.Graph:
    """14-node, 21-link NSFNET T1 backbone (the topology most used in routing
    papers), with heterogeneous capacities and propagation delays roughly
    proportional to the geographic distance between the PoPs. 8 hosts are
    attached at PoPs spread across the map."""
    G = nx.Graph()
    G.add_nodes_from((f"s{i}" for i in range(1, 15)), kind="switch")
    core_links = [
        ("s1", "s2", 100, 4), ("s1", "s3", 100, 5), ("s1", "s8", 80, 9),
        ("s2", "s3", 60, 2), ("s2", "s4", 100, 7), ("s3", "s6", 80, 9),
        ("s4", "s5", 100, 3), ("s4", "s11", 60, 9), ("s5", "s6", 60, 4),
        ("s5", "s7", 80, 3), ("s6", "s10", 100, 6), ("s6", "s14", 80, 9),
        ("s7", "s8", 100, 3), ("s8", "s9", 100, 2), ("s9", "s10", 60, 3),
        ("s9", "s12", 80, 3), ("s9", "s13", 80, 3), ("s11", "s12", 100, 4),
        ("s11", "s13", 60, 5), ("s12", "s14", 100, 3), ("s13", "s14", 100, 2),
    ]
    for u, v, bw, delay in core_links:
        G.add_edge(u, v, capacity_mbps=bw, base_delay_ms=delay, kind="core")
    for i, s in enumerate(["s1", "s2", "s5", "s7", "s9", "s11", "s13", "s14"], start=1):
        G.add_node(f"h{i}", kind="host")
        G.add_edge(f"h{i}", s, capacity_mbps=1000, base_delay_ms=0.5, kind="edge")
    return G


NSFNET_HOST_PAIRS = [
    ("h1", "h8"), ("h2", "h7"), ("h3", "h6"), ("h1", "h5"),
    ("h4", "h8"), ("h2", "h6"), ("h3", "h7"), ("h4", "h1"),
]

TOPOLOGIES = {
    "campus8": (build_topology, HOST_PAIRS),
    "nsfnet14": (build_nsfnet, NSFNET_HOST_PAIRS),
}

if __name__ == "__main__":
    for name, (build, pairs) in TOPOLOGIES.items():
        g = build()
        print(f"{name}: Nodes: {g.number_of_nodes()}, Edges: {g.number_of_edges()}, host pairs: {len(pairs)}")
