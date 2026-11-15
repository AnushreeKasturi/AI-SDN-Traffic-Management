"""Reproduce review findings without starting Mininet or changing project files.

Run with Python 3; no third-party packages are needed for these focused checks:
    python reproduce_findings.py /path/to/AI-SDN-Traffic-Management
Controller methods are taken directly from the reviewed source; OpenFlow
messages, packet objects, and time are stubbed for these focused checks.
"""

import ast
import contextlib
import io
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace as NS

if len(sys.argv) != 2:
    raise SystemExit("Usage: python3 reproduce_findings.py /path/to/AI-SDN-Traffic-Management")

ROOT = Path(sys.argv[1]).resolve()


def method(path, name, namespace):
    tree = ast.parse((ROOT / path).read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, str(ROOT / path), "exec"), namespace)
    return namespace[name]


packet_types = {kind: NS(**{kind: object()}) for kind in ("ipv4", "tcp", "udp")}


class Packet:
    def __init__(self, destination_port=5001):
        self.destination_port = destination_port

    def get_protocols(self, kind):
        if kind is packet_types["ipv4"].ipv4:
            return [NS(src="10.0.0.1", dst="10.0.0.2")]
        if kind is packet_types["tcp"].tcp:
            return [NS(src_port=45000, dst_port=self.destination_port)]
        return []


def controller_flow_check(filename, adaptive):
    namespace = dict(packet_types)
    namespace.update(
        ether_types=NS(ETH_TYPE_IP=0x800),
        out_port_on=lambda graph, src, dst: 3,
        classify_by_port=runpy.run_path(str(ROOT / "mininet_sdn/traffic_classes.py"))["classify_by_port"],
    )
    handler = method(filename, "_handle_ip", namespace)
    installed, messages = [], []
    state = NS(
        G={},
        ip_to_attach={"10.0.0.2": (2, 7, "00:00:00:00:00:02")},
        installed_flows={},
        _compute_path=lambda *args: [1, 2],
        _install_path=lambda path, match, **kwargs: installed.append((dict(match), kwargs)),
    )
    dp = NS(
        id=1,
        ofproto=NS(OFP_NO_BUFFER=0xFFFFFFFF),
        ofproto_parser=NS(OFPActionOutput=lambda port: port, OFPPacketOut=lambda **kwargs: kwargs),
        send_msg=messages.append,
    )
    msg = NS(buffer_id=0xFFFFFFFF, data=b"packet")
    with contextlib.redirect_stdout(io.StringIO()):
        handler(state, dp, 1, Packet(), msg)
        assert len(installed) == 1
        # The installed switch rules can expire after idle_timeout=30;
        # the Python cache has no corresponding removal or TTL.
        installed.clear()
        handler(state, dp, 1, Packet(), msg)
        assert not installed, "Expected stale-cache shortcut from reviewed source"
    print(f"CONFIRMED {filename}: cached packet sends PacketOut and does not reinstall an expired rule")
    if adaptive:
        state.installed_flows.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            handler(state, dp, 1, Packet(5001), msg)
            handler(state, dp, 1, Packet(5060), msg)
        assert len(installed) == 2
        assert installed[0][0] == installed[1][0]
        print("CONFIRMED adaptive controller: TCP 5001 and TCP 5060 produce identical match fields with different priorities")


controller_flow_check("mininet_sdn/controller_static.py", False)
controller_flow_check("mininet_sdn/controller_adaptive.py", True)

namespace = {"time": NS(time=lambda: 3.0)}
handler = method("mininet_sdn/controller_adaptive.py", "port_stats_reply_handler", namespace)
current_util = method("mininet_sdn/controller_adaptive.py", "_current_util", namespace)
state = NS(
    G={1: {2: {"capacity_mbps": 100}}, 2: {1: {"capacity_mbps": 100}}},
    port_to_neighbor={(1, 1): 2, (2, 1): 1},
    last_port_bytes={(1, 1): (0, 0.0), (2, 1): (0, 0.0)},
    edge_util_history={},
    congestion_predictor=NS(window=4),
)
for dpid, tx_bytes in ((1, 22_500_000), (2, 0)):
    handler(state, NS(msg=NS(datapath=NS(id=dpid), body=[NS(port_no=1, tx_bytes=tx_bytes)])))
assert state.edge_util_history[frozenset({1, 2})] == [60.0, 0.0]
assert current_util(state, 1, 2) == 0.0
print("CONFIRMED telemetry: 60% forward traffic plus 0% reverse traffic produces current utilization 0%")

for filename in ("test_static_run.py", "test_adaptive_run.py"):
    tree = ast.parse((ROOT / "mininet_sdn" / filename).read_text())
    statement = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "ok" for t in n.targets))
    condition = ast.Expression(body=statement.value)
    result = eval(compile(condition, filename, "eval"), {"out": "2 packets transmitted, 0 received, 100% packet loss"})
    assert result is True
    print(f"CONFIRMED {filename}: 100% packet loss is classified as OK")

print("All focused finding reproductions completed.")
