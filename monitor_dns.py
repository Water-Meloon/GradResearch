from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types, ipv4, udp
from ryu.lib import hub
import time
import random
import subprocess
import re


DNS_PORT = 53
THRESHOLD = 1

DNS_SERVERS_IP = ['163.118.76.10', '163.118.76.81']
DNS_SERVERS_MAC = {'163.118.76.10': '08:00:27:b4:56:e9', '163.118.76.81': '08:00:27:c7:dc:6f'}
DNS_SERVERS_VPORT = {'163.118.76.10': 2, '163.118.76.81': 3}
BACKUP_DNS_IP = "163.118.76.82"
BACKUP_DNS_MAC = "08:00:27:4b:36:79"
BACKUP_DNS_VPORT = 5
HOST_PORT=4
VM_INDEX={0:"dns1",1:"dns2"}


class DNSRotation(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(DNSRotation, self).__init__(*args, **kwargs)
        self.active_dns_index = 0
        self.datapaths = {}
        self.packet_counts = {}
        self.monitor_thread = hub.spawn(self._monitor)
        self.logger.info("DNSRotation App Initialized")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        # Extract packet details
        pkt = packet.Packet(msg.data)
        eth_pkt = pkt.get_protocol(ethernet.ethernet)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        udp_pkt = pkt.get_protocol(udp.udp)

        if ip_pkt and udp_pkt and udp_pkt.dst_port == DNS_PORT and in_port == HOST_PORT:
            print(ip_pkt.src, ip_pkt.dst)
            self.install_dns_flow_rules(datapath)

    def install_dns_flow_rules(self, datapath):

        # Forward DNS requests
        self.add_dns_response_flow(datapath)
        self.add_dns_request_flow(datapath)

        # Handle DNS responses

        self._request_flow_stats(datapath)


#request handling
    def add_dns_request_flow(self, datapath):
        parser = datapath.ofproto_parser

        match = parser.OFPMatch(in_port=HOST_PORT, eth_type=ether_types.ETH_TYPE_IP,ip_proto=17, udp_dst=DNS_PORT)
        actions = [
            parser.OFPActionSetField(eth_dst=DNS_SERVERS_MAC[DNS_SERVERS_IP[self.active_dns_index]]),
            parser.OFPActionSetField(ipv4_dst=DNS_SERVERS_IP[self.active_dns_index]),
            parser.OFPActionOutput(DNS_SERVERS_VPORT[DNS_SERVERS_IP[self.active_dns_index]])
        ]
        self.add_flow(datapath, 10, match, actions)


#response handling
    def add_dns_response_flow(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        
        match = parser.OFPMatch(in_port=DNS_SERVERS_VPORT[DNS_SERVERS_IP[self.active_dns_index]], eth_type=ether_types.ETH_TYPE_IP, ip_proto=17, eth_src=DNS_SERVERS_MAC[DNS_SERVERS_IP[self.active_dns_index]],udp_src=DNS_PORT,ipv4_src=DNS_SERVERS_IP[self.active_dns_index])
        if self.active_dns_index==0:
            actions = [
                parser.OFPActionOutput(ofproto.OFPP_NORMAL) 
            ]
        else:
            actions = [
                parser.OFPActionSetField(eth_src="08:00:27:c7:dc:6f"),
                parser.OFPActionSetField(ipv4_src="163.118.76.10"),
                parser.OFPActionOutput(HOST_PORT)
            ] 
        self.add_flow(datapath, 11, match, actions)

#assign flow rules
    def add_flow(self, datapath, priority, match, actions):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)
        
        
    def redirect_to_backup_dns(self, datapath):
        parser = datapath.ofproto_parser
    
    # Redirect DNS requests to backup DNS
        match = parser.OFPMatch(in_port=HOST_PORT, eth_type=ether_types.ETH_TYPE_IP, ip_proto=17, udp_dst=DNS_PORT)
        actions = [
            parser.OFPActionSetField(eth_dst=BACKUP_DNS_MAC),
            parser.OFPActionSetField(ipv4_dst=BACKUP_DNS_IP),
            parser.OFPActionOutput(BACKUP_DNS_VPORT)
        ]
        self.add_flow(datapath, 10, match, actions)
        
        # Redirect DNS responses from backup DNS
        match = parser.OFPMatch(in_port=BACKUP_DNS_VPORT, eth_src="08:00:27:4b:36:79",eth_type=ether_types.ETH_TYPE_IP, ip_proto=17, udp_src=DNS_PORT,ipv4_src="163.118.76.82")
        actions = [parser.OFPActionSetField(eth_src="08:00:27:c7:dc:6f"),
                parser.OFPActionSetField(ipv4_src="163.118.76.10"),
                parser.OFPActionOutput(HOST_PORT)
                ] 
        self.add_flow(datapath, 13, match, actions)
        self._request_flow_stats(datapath)
        

#fetching statistics
    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_flow_stats(dp)
            hub.sleep(2)

    def _request_flow_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        datapath_id = ev.msg.datapath.id
        for stat in ev.msg.body:
            if stat.priority == 11 and stat.match.get('ipv4_src') == DNS_SERVERS_IP[self.active_dns_index]:
                new_packet_count = stat.packet_count
                print(new_packet_count)
                old_packet_count = self.packet_counts.get(datapath_id, {}).get(DNS_SERVERS_IP[self.active_dns_index], 0)
                print(self.packet_counts.get(datapath_id, {}).get(DNS_SERVERS_IP[self.active_dns_index], 0))
                self.packet_counts.setdefault(datapath_id, {})[DNS_SERVERS_IP[self.active_dns_index]] = new_packet_count

                packet_difference = abs(new_packet_count - old_packet_count)
                rate = packet_difference / 2  # Checking every 2 seconds
                print("Rate: ", rate)

                if rate > THRESHOLD:
                    print("Threshold exceeded. Rotating DNS server.")
                    self.redirect_to_backup_dns(self.datapaths[datapath_id])
                    self.stop_vm(self.active_dns_index)
                    last_dns_index=self.active_dns_index
                    next_dns_index = (self.active_dns_index + 1) % len(DNS_SERVERS_IP)
                    # Rotate the DNS server
                    start_time = time.time()
                    self.start_vm(next_dns_index)
                    self.delete_dns_response_flow(self.datapaths[datapath_id])
                    self.active_dns_index = next_dns_index
                    self.remove_backup_dns_flows(self.datapaths[datapath_id])
        # Update DNS rules for the next DNS server
                    self.install_dns_flow_rules(self.datapaths[datapath_id])

                    end_time = time.time()
                    rotation_time = end_time - start_time
                    new_packet_count = 0
                    old_packet_count=0

                    self.logger.info(f"Server rotation time: {rotation_time:.2f} seconds")

                    
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER])
    def state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
            self.add_default_flow(datapath)


#default rules installation
    def add_default_flow(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_NORMAL)]
        self.add_flow(datapath, 0, match, actions)

        match_default = parser.OFPMatch(in_port=HOST_PORT, eth_type=ether_types.ETH_TYPE_IP, ip_proto=17, udp_dst=DNS_PORT)
        actions_default = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 1, match_default, actions_default)  # Lower priority catch-all rule
        self.logger.info("Default flow rule added.")
        
        
    def start_vm(self,vm_name):
        vm = VM_INDEX[vm_name]
        command = ["VBoxManage", "startvm", vm,"--type", "headless"]
        subprocess.run(command, check=True)
        
        
       
    def stop_vm(self,vm_name):
        vm = VM_INDEX[vm_name]
        command = ["VBoxManage", "controlvm", vm,"savestate"]
        subprocess.run(command, check=True)



    def remove_backup_dns_flows(self, datapath):
        parser = datapath.ofproto_parser

    # Match criteria for the DNS response from backup
        match_response = parser.OFPMatch(in_port=BACKUP_DNS_VPORT, eth_src="08:00:27:4b:36:79",eth_type=ether_types.ETH_TYPE_IP, ip_proto=17, udp_src=DNS_PORT,ipv4_src="163.118.76.82")
        self.delete_flow(datapath, match_response)
        
        
    def delete_dns_response_flow(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

    # Match fields based on the flow you want to delete
        match = parser.OFPMatch(
            in_port=DNS_SERVERS_VPORT[DNS_SERVERS_IP[self.active_dns_index]],
            eth_src=DNS_SERVERS_MAC[DNS_SERVERS_IP[self.active_dns_index]],
            eth_type=ether_types.ETH_TYPE_IP,
            ip_proto=17,  # UDP protocol
            ipv4_src=DNS_SERVERS_IP[self.active_dns_index],
            udp_src=DNS_PORT
        )

        self.delete_flow(datapath, match)
        
      
    def delete_flow(self, datapath, match):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        mod = parser.OFPFlowMod(datapath=datapath, command=ofproto.OFPFC_DELETE, out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY, priority=11,match=match)
        datapath.send_msg(mod)
