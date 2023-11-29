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
THRESHOLD = 80000 #60000
VM_STARTUP_THRESHOLD=15000
DEFAULT_DNS_SERVER_IP = '163.118.76.10'  # IP of the default DNS server
DEFAULT_DNS_SERVER_MAC = '08:00:27:b4:56:e9'  # MAC of the default DNS server
LOAD_BALANCE_GROUP_ID = 100
DNS_SERVERS_IP = ['163.118.76.10', '163.118.76.81']
DNS_SERVERS_MAC = {'163.118.76.10': '08:00:27:b4:56:e9', '163.118.76.81': '08:00:27:c7:dc:6f'}
DNS_SERVERS_VPORT = {'163.118.76.10': 2, '163.118.76.81': 3}
BACKUP_DNS_IP = "163.118.76.82"
BACKUP_DNS_MAC = "08:00:27:4b:36:79"
BACKUP_DNS_VPORT = 5
HOST_PORT=4
VM_INDEX={0:"dns1",1:"dns2"}
VM_STARTUP_time=[]
DEFAULT_PACKET_LIST=[]
TIME=[]
GROUP_PACKET_LIST=[]
GROUP_TIME=[]




class DNSRotation(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(DNSRotation, self).__init__(*args, **kwargs)
        self.active_dns_index = 0
        self.datapaths = {}
        self.packet_counts = {}
        self.previous_packet_counts = {}
        self.total_counts=0
        self.last_index=0
        self.vm_startup_initiated = False
        self.is_load_balancing_active = False
        self.monitor_thread = hub.spawn(self._monitor)
        self.logger.info("DNSRotation App Initialized")

    #@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    #def packet_in_handler(self, ev):
        #msg = ev.msg
        #datapath = msg.datapath
        #parser = datapath.ofproto_parser
        #in_port = msg.match['in_port']

        # Extract packet details
        #pkt = packet.Packet(msg.data)
        #eth_pkt = pkt.get_protocol(ethernet.ethernet)
        #ip_pkt = pkt.get_protocol(ipv4.ipv4)
        #udp_pkt = pkt.get_protocol(udp.udp)

        #if ip_pkt and udp_pkt and udp_pkt.dst_port == DNS_PORT and in_port == HOST_PORT:
            #print(ip_pkt.src, ip_pkt.dst)
            #self.install_dns_flow_rules(datapath)
            

    def install_dns_flow_rules(self, datapath):
        self.add_dns_request_flow(datapath)


#request handling
    def add_dns_request_flow(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,eth_dst=DEFAULT_DNS_SERVER_MAC,ip_proto=17, ipv4_dst=DEFAULT_DNS_SERVER_IP,udp_dst=DNS_PORT)
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_NORMAL)
        ]
        self.add_flow(datapath, 10, match, actions)

#eth_dst=DNS_SERVERS_MAC[DNS_SERVERS_IP[self.active_dns_index]]),
            #parser.OFPActionSetField(ipv4_dst=DNS_SERVERS_IP[self.active_dns_index]),
            #parser.OFPActionOutput(DNS_SERVERS_VPORT[DNS_SERVERS_IP[self.active_dns_index]]
#response handling


#assign flow rules
    def add_flow(self, datapath, priority, match, actions):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)
              

#fetching statistics
    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                if self.is_load_balancing_active:
                    self._request_group_stats(dp)
                else:
                    self._request_flow_stats(dp)
            hub.sleep(2)

    # New method to request group stats
    def _request_group_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPGroupStatsRequest(datapath)
        datapath.send_msg(req)

    # Existing method to request flow stats
    def _request_flow_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)
        
        
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        datapath_id = ev.msg.datapath.id
        for stat in body:
            if stat.priority ==10:
                new_packet_count=stat.packet_count
                self.total_counts=new_packet_count
                seconds=time.time()
                TIME.append(seconds)
                GROUP_TIME.append(seconds)
                old_packet_count = self.packet_counts.get(datapath_id, {}).get(DNS_SERVERS_IP[self.active_dns_index], 0)
                print(self.packet_counts.get(datapath_id, {}).get(DNS_SERVERS_IP[self.active_dns_index], 0))
                self.packet_counts.setdefault(datapath_id, {})[DNS_SERVERS_IP[self.active_dns_index]] = new_packet_count

                packet_difference = new_packet_count - old_packet_count
                rate = packet_difference / 2  # Checking every 2 seconds
                print("Rate: ", rate)
                DEFAULT_PACKET_LIST.append(rate)
                GROUP_PACKET_LIST.append(0)
                print(DEFAULT_PACKET_LIST)
                self.write_list_to_file(DEFAULT_PACKET_LIST, 'default_packet_list.txt')
                self.write_list_to_file(TIME, 'time.txt')
                #if rate > VM_STARTUP_THRESHOLD and not self.vm_startup_initiated :
                    #print("VM is starting up....")
                    #self.start_vm(1)
                    #if self.detecting_state(1) ==0:
                        #self.setup_load_balance_group(self.datapaths[datapath_id])
                        #self.vm_startup_initiated = True

                if rate > THRESHOLD:
                    print("Threshold exceeded. Load-Balancing between DNS servers.")
                    self.setup_load_balance_group(self.datapaths[datapath_id])
                    self.add_group_response_flow(self.datapaths[datapath_id])
                    self.forward_to_group(self.datapaths[datapath_id])
                    self.logger.info(f"Load_balacing....")
                    self.trigger_load_balancing()
                    self.initialize_counters(datapath_id)
                    new_packet_count=0
                    old_packet_count=0
                    
                    
    @set_ev_cls(ofp_event.EventOFPGroupStatsReply, MAIN_DISPATCHER)
    def group_stats_reply_handler(self, ev):
        body = ev.msg.body
        datapath = ev.msg.datapath
        bucket1=0
        bucket2=1
        for group_stat in body:
            if group_stat.group_id == 100:  # Specific group ID
                bucket0_stats = group_stat.bucket_stats[0]
                bucket1_stats=group_stat.bucket_stats[1]
                packet_count_bucket0 = bucket0_stats.packet_count
                packet_count_bucket1 = bucket1_stats.packet_count
                print(packet_count_bucket1)
                seconds=time.time()
                TIME.append(seconds)
                GROUP_TIME.append(seconds)
                #self.logger.info(f"Group ID: {group_stat.group_id}, Bucket0 Packet Count: {packet_count_bucket0}")
                previous_packet_count1 = self.get_previous_packet_count(bucket1)
                rate1 = (packet_count_bucket0 - previous_packet_count1)/2
                print("Rate:",rate1)
                DEFAULT_PACKET_LIST.append(rate1)
                print(DEFAULT_PACKET_LIST)
                self.previous_packet_counts[bucket1] = packet_count_bucket0
                previous_packet_count2 = self.get_previous_packet_count(bucket2)
                print(previous_packet_count2)
                rate2 = (packet_count_bucket1 - previous_packet_count2)/2
                GROUP_PACKET_LIST.append(rate2)
                self.previous_packet_counts[bucket2] = packet_count_bucket1
                print(GROUP_PACKET_LIST)
                self.write_list_to_file(GROUP_PACKET_LIST, 'group_packet_list.txt')
                self.write_list_to_file(GROUP_TIME, 'group_time.txt')
                if rate1<15000:  # Check for 10% drop
                    self.logger.info("Packet count dropped. Switching to default DNS.")
                    self.delete_group_response_rule(datapath)
                    self.delete_group(datapath,100)
                    self.stop_load_balancing()
                    self.install_dns_flow_rules(datapath)
                    self.reset_packet_count(bucket1)
                    self.reset_packet_count(bucket2)
                    packet_count_bucket0=0
                    packet_count_bucket1=0
                    #self.stop_vm(1)
                    #self.vm_startup_initiated=False
                    
        

    # Modified method that triggers load balancing
    def trigger_load_balancing(self):
        # Logic to trigger load balancing
        self.is_load_balancing_active = True  # Update state
        self.logger.info("Load balancing activated.")

    # Modified method that stops load balancing
    def stop_load_balancing(self):
        # Logic to stop load balancing
        self.is_load_balancing_active = False
        self.logger.info("Load balancing deactivated.")

                    
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
        self.add_dns_request_flow(datapath)
        self._request_flow_stats(datapath)
       
        self.logger.info("Default flow rule added.")
        
        
    def start_vm(self,vm_name):
        vm = VM_INDEX[vm_name]
        command = ["VBoxManage", "startvm", vm,"--type", "headless"]
        subprocess.run(command, check=True)
        
        
    def stop_vm(self,vm_name):
        vm = VM_INDEX[vm_name]
        command = ["VBoxManage", "controlvm", vm,"savestate"]
        subprocess.run(command, check=True)
        

    def detecting_state(self,dns_ip):
        while True:
            command = ["nslookup","google.com",DNS_SERVERS_IP[dns_ip]]
            rs=subprocess.run(command,stdout=subprocess.DEVNULL)
            if rs.returncode==0:
                break
        return rs.returncode
       

        mod = parser.OFPFlowMod(datapath=datapath, command=ofproto.OFPFC_DELETE, out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY, priority=11,match=match)
        datapath.send_msg(mod)
        
        
    def initialize_counters(self, datapath_id):
    # Reset all packet counters for this datapath to zero
        for dns_ip in DNS_SERVERS_IP:
            self.packet_counts.setdefault(datapath_id, {})[dns_ip] = 0
            
            
    def get_previous_packet_count(self, bucket_stats):
    # Key is a tuple of group ID and bucket index
        return self.previous_packet_counts.get(bucket_stats, 0)
        
       
    def reset_packet_count(self, group_id):
        self.previous_packet_counts[group_id] = 0
            
            
    def setup_load_balance_group(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        weight_1=50
        weight_2=50
        # Setup group for DNS load balancing
        actions_default = [parser.OFPActionOutput(ofproto.OFPP_NORMAL)]
        bucket_default = parser.OFPBucket(weight=weight_1,actions=actions_default)
        
        actions_second = [
            parser.OFPActionSetField(eth_dst=DNS_SERVERS_MAC[DNS_SERVERS_IP[1]]),
            parser.OFPActionSetField(ipv4_dst=DNS_SERVERS_IP[1]),
            parser.OFPActionOutput(DNS_SERVERS_VPORT[DNS_SERVERS_IP[1]])
        ]
        bucket_second = parser.OFPBucket(weight=weight_2,actions=actions_second)

        buckets = [bucket_default, bucket_second]
        group_mod = parser.OFPGroupMod(datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_SELECT,
                                       LOAD_BALANCE_GROUP_ID, buckets)
        datapath.send_msg(group_mod)
        
        
    def forward_to_group(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,eth_dst=DEFAULT_DNS_SERVER_MAC,ip_proto=17, ipv4_dst=DEFAULT_DNS_SERVER_IP,udp_dst=DNS_PORT)
        actions = [parser.OFPActionGroup(LOAD_BALANCE_GROUP_ID)]
        self.add_flow(datapath, 10, match, actions)
        
        
    def add_group_response_flow(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match = parser.OFPMatch(
            in_port=DNS_SERVERS_VPORT[DNS_SERVERS_IP[1]],
            eth_type=ether_types.ETH_TYPE_IP,
            ip_proto=17,  
            eth_src=DNS_SERVERS_MAC[DNS_SERVERS_IP[1]],
            udp_src=DNS_PORT,
            ipv4_src=DNS_SERVERS_IP[1]
        )
        actions = [
            parser.OFPActionSetField(eth_src=DEFAULT_DNS_SERVER_MAC),
            parser.OFPActionSetField(ipv4_src=DEFAULT_DNS_SERVER_IP),
            parser.OFPActionOutput(HOST_PORT)
        ]
        self.add_flow(datapath, 12, match, actions)
        
    
    def delete_group_response_rule(self,datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        match = parser.OFPMatch(
            in_port=DNS_SERVERS_VPORT[DNS_SERVERS_IP[1]],
            eth_type=ether_types.ETH_TYPE_IP,
            ip_proto=17,  # UDP
            eth_src=DNS_SERVERS_MAC[DNS_SERVERS_IP[1]],
            udp_src=DNS_PORT,
            ipv4_src=DNS_SERVERS_IP[1]
        )

        self.delete_flow(datapath, 12, match)
    
    
    def delete_group_flow_rule(self, datapath, group_id):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match=parser.OFPMatch(in_port=HOST_PORT, eth_type=ether_types.ETH_TYPE_IP,ip_proto=17)
    # Create a flow mod message to delete the flow rule
        flow_mod = parser.OFPFlowMod(datapath=datapath, command=ofproto.OFPFC_DELETE,
                                 out_group=group_id, match=match)

    # Send the flow mod message to the switch
        datapath.send_msg(flow_mod)
        self.logger.info("Flow rule directing to group {} deletion command sent.".format(group_id))
        
    
    def delete_group(self, datapath, group_id):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

    # Create a group mod message to delete the group
        group_mod = parser.OFPGroupMod(datapath=datapath,
                                   command=ofproto.OFPGC_DELETE,
                                   group_id=group_id)

    # Send the group mod message to the switch
        datapath.send_msg(group_mod)
        self.logger.info(f"Group {group_id} deletion command sent.")
        
        
    def switch_to_default_dns(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

    # Match criteria for DNS traffic (e.g., UDP traffic on port 53)
        match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, 
                            ip_proto=17,  # 17 is the protocol number for UDP
                            udp_dst=DNS_PORT)  # DNS_PORT is typically 53

    # Define action to forward DNS requests to the default DNS server
        actions = [
            parser.OFPActionSetField(eth_dst=DEFAULT_DNS_SERVER_MAC),
            parser.OFPActionSetField(ipv4_dst=DEFAULT_DNS_SERVER_IP),
            parser.OFPActionOutput(DNS_SERVERS_VPORT[DEFAULT_DNS_SERVER_IP])
        ]

    # Add a flow to implement the above action
        self.add_flow(datapath, 10, match, actions)
        
        
    def delete_flow(self, datapath, priority, match):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

    # Construct a flow_mod message with command DELETE
        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            priority=priority,
            match=match
        )  

    # Send the flow mod message to the switch
        datapath.send_msg(flow_mod)

  
  
    def write_list_to_file(self, list_data, file_name):
        with open(file_name, 'w') as file:
            for item in list_data:
                file.write(f"{item}\n")
        self.logger.info(f"Data written to {file_name}")      
    

            
