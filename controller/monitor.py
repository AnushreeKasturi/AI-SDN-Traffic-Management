from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER
from os_ken.controller.handler import MAIN_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.lib import hub


class TrafficMonitor(app_manager.OSKenApp):

    OFP_VERSIONS = [0x04]

    def __init__(self, *args, **kwargs):
        super(TrafficMonitor, self).__init__(*args, **kwargs)

        self.logger.info("=" * 50)
        self.logger.info("AI-SDN Traffic Monitor Started")
        self.logger.info("=" * 50)

        self.datapaths = {}

        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(
        ofp_event.EventOFPStateChange,
        [CONFIG_DISPATCHER, MAIN_DISPATCHER]
    )
    def state_change_handler(self, ev):

        datapath = ev.datapath

        if ev.state == MAIN_DISPATCHER:

            if datapath.id not in self.datapaths:

                self.datapaths[datapath.id] = datapath

                self.logger.info(
                    f"Monitoring switch {datapath.id}"
                )

        elif ev.state == CONFIG_DISPATCHER:

            if datapath.id in self.datapaths:

                del self.datapaths[datapath.id]

                self.logger.info(
                    f"Stopped monitoring switch {datapath.id}"
                )

    def _monitor(self):

        while True:

            for datapath in self.datapaths.values():

                self._request_port_stats(datapath)

            hub.sleep(5)

    def _request_port_stats(self, datapath):

        parser = datapath.ofproto_parser

        if datapath.id in [1, 4]:
            ports = [1, 2, 3]
        else:
            ports = [1, 2]

        for port_no in ports:

            request = parser.OFPPortStatsRequest(
                datapath,
                0,
                port_no
            )

            datapath.send_msg(request)

        self.logger.info(
            f"Requested port statistics from switch "
            f"{datapath.id}"
        )

    @set_ev_cls(
        ofp_event.EventOFPPortStatsReply,
        MAIN_DISPATCHER
    )
    def port_stats_reply_handler(self, ev):

        datapath = ev.msg.datapath
        dpid = datapath.id

        self.logger.info(
            f"Traffic statistics received from switch {dpid}"
        )

        for stat in ev.msg.body:

            self.logger.info(
                f"Switch {dpid} | "
                f"Port {stat.port_no} | "
                f"RX Packets: {stat.rx_packets} | "
                f"RX Bytes: {stat.rx_bytes} | "
                f"TX Packets: {stat.tx_packets} | "
                f"TX Bytes: {stat.tx_bytes}"
            )
