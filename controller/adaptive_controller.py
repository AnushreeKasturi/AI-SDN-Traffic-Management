from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER
from os_ken.controller.handler import MAIN_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.lib.packet import packet
from os_ken.lib.packet import ethernet
from os_ken.lib.packet import ether_types


class AdaptiveController(app_manager.OSKenApp):

    OFP_VERSIONS = [0x04]  # OpenFlow 1.3

    def __init__(self, *args, **kwargs):
        super(AdaptiveController, self).__init__(*args, **kwargs)

        self.logger.info("=" * 50)
        self.logger.info("AI-SDN Adaptive Controller Started")
        self.logger.info("=" * 50)

        # MAC address table
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.logger.info("--------------------------------")
        self.logger.info("Switch Connected!")
        self.logger.info(f"Datapath ID : {datapath.id}")
        self.logger.info("--------------------------------")

        # Table-miss flow:
        # Send unknown packets to the controller.
        match = parser.OFPMatch()

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        self.add_flow(
            datapath,
            0,
            match,
            actions
        )

        self.logger.info(
            f"Table-miss flow installed on switch {datapath.id}"
        )

    def add_flow(self, datapath, priority, match, actions):

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions
        )

        datapath.send_msg(flow_mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None:
            return

        dst = eth.dst
        src = eth.src

        # Ignore LLDP packets
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        # Create MAC table for this switch
        self.mac_to_port.setdefault(dpid, {})

        # Learn source MAC
        self.mac_to_port[dpid][src] = in_port

        self.logger.info(
            f"Packet received at switch {dpid}: "
            f"{src} -> {dst} on port {in_port}"
        )

        # -------------------------------------------------
        # LOOP-SAFE FLOODING
        # -------------------------------------------------
        #
        # The topology has two paths between s1 and s4.
        # During initial learning, broadcast packets such
        # as ARP must not be flooded through both paths.
        #
        # We temporarily use:
        #
        # h1 -> s1 -> s2 -> s4 -> h2
        #
        # as the loop-free learning path.
        #

        if (
            dst == "ff:ff:ff:ff:ff:ff"
            or dst.startswith("33:33:")
        ):

            if dpid == 1:

                # s1:
                # h1 = port 1
                # s2 = port 2
                # s3 = port 3

                if in_port == 1:
                    out_ports = [2]

                elif in_port == 2:
                    out_ports = [1]

                else:
                    out_ports = [1]

            elif dpid == 2:

                # s2:
                # s1 = port 1
                # s4 = port 2

                if in_port == 1:
                    out_ports = [2]

                elif in_port == 2:
                    out_ports = [1]

                else:
                    out_ports = [1]

            elif dpid == 3:

                # s3 is reserved for the alternate path.
                # It is not used during baseline flooding.
                return

            elif dpid == 4:

                # s4:
                # h2 = port 1
                # s2 = port 2
                # s3 = port 3

                if in_port == 2:
                    out_ports = [1]

                elif in_port == 1:
                    out_ports = [2]

                else:
                    out_ports = [1]

            else:
                return

            for out_port in out_ports:

                actions = [
                    parser.OFPActionOutput(out_port)
                ]

                out = parser.OFPPacketOut(
                    datapath=datapath,
                    buffer_id=msg.buffer_id,
                    in_port=in_port,
                    actions=actions,
                    data=msg.data
                )

                datapath.send_msg(out)

            return

        # -------------------------------------------------
        # NORMAL MAC LEARNING
        # -------------------------------------------------

        if dst in self.mac_to_port[dpid]:

            out_port = self.mac_to_port[dpid][dst]

        else:

            # Destination unknown.
            # Avoid flooding through the loop.
            if dpid == 1:
                out_port = 2

            elif dpid == 2:
                out_port = 2

            elif dpid == 4:
                out_port = 1

            else:
                return

        actions = [
            parser.OFPActionOutput(out_port)
        ]

        # Install flow when destination is known
        if dst in self.mac_to_port[dpid]:

            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst
            )

            self.add_flow(
                datapath,
                10,
                match,
                actions
            )

        # Send packet out
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )

        datapath.send_msg(out)