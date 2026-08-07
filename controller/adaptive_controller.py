from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER
from os_ken.controller.handler import set_ev_cls


class AdaptiveController(app_manager.OSKenApp):

    OFP_VERSIONS = [0x04]  # OpenFlow 1.3

    def __init__(self, *args, **kwargs):
        super(AdaptiveController, self).__init__(*args, **kwargs)

        self.logger.info("=" * 50)
        self.logger.info("AI-SDN Adaptive Controller Started")
        self.logger.info("=" * 50)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath

        self.logger.info("--------------------------------")
        self.logger.info("Switch Connected!")
        self.logger.info(f"Datapath ID : {datapath.id}")
        self.logger.info("--------------------------------")