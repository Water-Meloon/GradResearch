I refer to Rusheel's Github page and Jerrel's Github page for the basic installation and configuration of DNS servers.


Rusheel Github Link: https://github.com/Rusheelraj/FIT-DNS-Research/blob/main/Implementing%20Traditional%20DNSSEC.md#implementing-dnssec-using-bind9


Jerrel's Github Link: https://github.com/jerrelgordon/fit-dns-research-cheatsheet/blob/main/README.md

# Implementing DNS using Bind9

## Bind9 Installation:
```
$ sudo apt update 
$ sudo apt install bind9 bind9utils bind9-doc dnsutils
```

## Configure DNS resolver
### Configure named.conf.local file
```
//
// Do any local configuration here
//
zone "adam" {
    type master;
    file "/etc/bind/zones/db.adam";  # zone file path
    allow-transfer { none; };  # disable zone transfers
};
// Consider adding the 1918 zones here, if they are not used in your
// organization
//include "/etc/bind/zones.rfc1918";

```
### Configure named.conf.options file
```
options {
	directory "/var/cache/bind";
	recursion yes;
	allow-query {163.118.76.0/24;};
	allow-recursion {163.118.76.0/24;};
	#allow-new-zones yes;
	// If there is a firewall between you and nameservers you want
	// to talk to, you may need to fix the firewall to allow multiple
	// ports to talk.  See http://www.kb.cert.org/vuls/id/800113

	// If your ISP provided one or more IP addresses for stable 
	// nameservers, you probably want to use them as forwarders.  
	// Uncomment the following block, and insert the addresses replacing 
	// the all-0's placeholder.

	//forwarders {
	 //163.118.76.81;
	 //8.8.8.8;
	 //8.8.4.4;
	//};

	//========================================================================
	// If BIND logs error messages about the root key being expired,
	// you will need to update your keys.  See https://www.isc.org/bind-keys
	//========================================================================
	dnssec-validation auto;

	listen-on-v6 { any; };
};
```
We need to set ```recursion yes;``` to make the DNS server as an recursive resolver.
You can set who is allowed to perform recursion using this DNS server by setting the ```allow-recursion``` with the IP addresses or a network range in CIDR.

## Configure DNS Zone File:
```
$TTL 604800
@ IN SOA ns.adam. admin.adam. (
  2023100501 ; serial number
  604800     ; refresh
  86400      ; retry
  2419200    ; expire
  604800 )   ; negative cache TTL

; name servers
adam.	IN	NS	ns.adam.

; A records for name servers
ns	IN	A	163.118.76.10
ns	IN	A	163.118.76.81  

; additional records
host3	IN	A	163.118.76.9
host4	IN	A	163.118.76.82
host5	IN	A	163.118.76.77
www	IN	A	163.118.76.10  
www	IN	A	163.118.76.81
 
; Custom records
testing	IN	A	10.3.3.21
```
