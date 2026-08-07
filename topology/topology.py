from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel


class CustomTopology(Topo):
    """
    Custom topology for AI-Driven Adaptive Network Traffic Management
    """

    def __init__(self):
        super().__init__()

        # Add hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')

        # Add OpenFlow switches
        s1 = self.addSwitch('s1', protocols='OpenFlow13')
        s2 = self.addSwitch('s2', protocols='OpenFlow13')
        s3 = self.addSwitch('s3', protocols='OpenFlow13')
        s4 = self.addSwitch('s4', protocols='OpenFlow13')

        # Connect hosts to switches
        self.addLink(h1, s1, cls=TCLink, bw=100, delay='2ms')
        self.addLink(h2, s4, cls=TCLink, bw=100, delay='2ms')

        # Connect switches
        self.addLink(s1, s2, cls=TCLink, bw=100, delay='5ms')
        self.addLink(s1, s3, cls=TCLink, bw=100, delay='5ms')
        self.addLink(s2, s4, cls=TCLink, bw=100, delay='5ms')
        self.addLink(s3, s4, cls=TCLink, bw=100, delay='5ms')


def run():
    """
    Create and start the Mininet network.
    """

    topo = CustomTopology()

    controller = RemoteController(
        'c0',
        ip='127.0.0.1',
        port=6653
    )

    net = Mininet(
        topo=topo,
        controller=controller,
        link=TCLink
    )

    print("*** Starting network")
    net.start()

    print("*** Running CLI")
    CLI(net)

    print("*** Stopping network")
    net.stop()


if __name__ == "__main__":
    setLogLevel('info')
    run()