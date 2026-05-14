#!/usr/bin/env bash
set -euo pipefail

#=== sanity / defaults ===#
if [[ $EUID -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

CLIENT_NAME="${CLIENT_NAME:-client}"
VPN_NET="${VPN_NET:-10.8.0.0/24}"
VPN_SUBNET="${VPN_NET%/*}"
VPN_PORT="${VPN_PORT:-1194}"
VPN_PROTO="${VPN_PROTO:-udp}"
EASYRSA_DIR="/etc/openvpn/easy-rsa"
OVPN_DIR="/etc/openvpn/server"
SERVER_NAME="server"
PROFILE_OUT="/root/${CLIENT_NAME}.ovpn"

# Detect default egress interface
EGRESS_IFACE="$(ip route get 1.1.1.1 | awk '{for(i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}')"
if [[ -z "${EGRESS_IFACE}" ]]; then
  echo "Failed to detect egress interface." >&2
  exit 1
fi

#=== determine public address ===#
detect_public_addr() {
  # 1) AWS IMDSv2
  if TOKEN=$(curl -s --max-time 2 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60"); then
    if PUB=$(curl -s --max-time 2 -H "X-aws-ec2-metadata-token: ${TOKEN}" http://169.254.169.254/latest/meta-data/public-ipv4); then
      [[ -n "$PUB" ]] && echo "$PUB" && return
    fi
  fi
  # 2) AWS IMDSv1
  if PUB=$(curl -s --max-time 2 http://169.254.169.254/latest/meta-data/public-ipv4); then
    [[ -n "$PUB" ]] && echo "$PUB" && return
  fi
  # 3) OpenDNS whoami (works through most egress)
  if PUB=$(dig +short TXT o-o.myaddr.l.google.com @ns1.google.com 2>/dev/null | tr -d '"'); then
    [[ -n "$PUB" ]] && echo "$PUB" && return
  fi
}

PUBLIC_ADDR="${OVPN_PUBLIC_ADDR:-$(detect_public_addr || true)}"
if [[ -z "${PUBLIC_ADDR:-}" ]]; then
  echo "WARNING: Could not auto-detect public address. Set OVPN_PUBLIC_ADDR to hostname/IP before running." >&2
  exit 1
fi

#=== apt sources / packages ===#
apt-get update -y
apt-get install -y --no-install-recommends openvpn easy-rsa ufw ca-certificates curl iproute2 iptables nano

#=== easy-rsa PKI ===#
install -d -m 700 "${EASYRSA_DIR}"
# Copy Easy-RSA 3 template if not already initialized
if [[ ! -d "${EASYRSA_DIR}/pki" ]]; then
  make-cadir "${EASYRSA_DIR}" >/dev/null 2>&1 || true
  # Some distros don't ship make-cadir; fallback to copying skeleton if present
  if [[ ! -d "${EASYRSA_DIR}/pki" ]]; then
    cp -r /usr/share/easy-rsa/* "${EASYRSA_DIR}/" || true
  fi
fi

pushd "${EASYRSA_DIR}" >/dev/null

# Easy-RSA vars (non-interactive)
cat > "${EASYRSA_DIR}/vars" <<EOF
set_var EASYRSA_BATCH "1"
set_var EASYRSA_REQ_CN "OpenVPN-CA"
set_var EASYRSA_ALGO "ec"
set_var EASYRSA_CURVE "prime256v1"
EOF

./easyrsa init-pki
./easyrsa build-ca nopass
./easyrsa gen-req "${SERVER_NAME}" nopass
./easyrsa sign-req server "${SERVER_NAME}"

./easyrsa gen-dh
./easyrsa gen-req "${CLIENT_NAME}" nopass
./easyrsa sign-req client "${CLIENT_NAME}"

# tls-crypt key
install -d -m 700 "${OVPN_DIR}"
openvpn --genkey secret "${OVPN_DIR}/tc.key"

# Copy server files
install -m 600 "pki/private/${SERVER_NAME}.key"   "${OVPN_DIR}/"
install -m 644 "pki/issued/${SERVER_NAME}.crt"    "${OVPN_DIR}/"
install -m 644 "pki/ca.crt"                       "${OVPN_DIR}/"
install -m 644 "pki/dh.pem"                       "${OVPN_DIR}/"

# Prepare client material (we'll embed later)
install -d -m 700 "/root/ovpn-clients/${CLIENT_NAME}"
install -m 600 "pki/private/${CLIENT_NAME}.key"   "/root/ovpn-clients/${CLIENT_NAME}/"
install -m 644 "pki/issued/${CLIENT_NAME}.crt"    "/root/ovpn-clients/${CLIENT_NAME}/"
install -m 644 "pki/ca.crt"                       "/root/ovpn-clients/${CLIENT_NAME}/"
install -m 600 "${OVPN_DIR}/tc.key"               "/root/ovpn-clients/${CLIENT_NAME}/"
popd >/dev/null

#=== OpenVPN server config ===#
install -d -m 755 "${OVPN_DIR}"
cat > "${OVPN_DIR}/server.conf" <<EOF
port ${VPN_PORT}
proto ${VPN_PROTO}
dev tun

user nobody
group nogroup
persist-key
persist-tun

topology subnet
server ${VPN_SUBNET} 255.255.255.0
ifconfig-pool-persist /var/log/openvpn/ipp.txt

push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 1.1.1.1"
push "dhcp-option DNS 9.9.9.9"

cipher AES-256-GCM
data-ciphers AES-256-GCM:AES-256-CBC
data-ciphers-fallback AES-256-CBC
auth SHA256
tls-version-min 1.2
tls-crypt ${OVPN_DIR}/tc.key

ca ${OVPN_DIR}/ca.crt
cert ${OVPN_DIR}/${SERVER_NAME}.crt
key ${OVPN_DIR}/${SERVER_NAME}.key
dh ${OVPN_DIR}/dh.pem

keepalive 10 120
explicit-exit-notify 1
status /var/log/openvpn/status.log
log-append /var/log/openvpn/openvpn.log
verb 3

# Allow multiple clients with same cert? No; better hygiene.
duplicate-cn
EOF

# Systemd expects /etc/openvpn/server/server.conf; we already used that path.
systemctl daemon-reload

#=== IP forwarding ===#
SYSCTL_FILE="/etc/sysctl.d/99-openvpn-forward.conf"
echo "net.ipv4.ip_forward=1" > "${SYSCTL_FILE}"
sysctl --system >/dev/null

#=== UFW (allow SSH + VPN, enable forwarding + NAT) ===#
ufw --force reset

# Allow SSH (22/tcp) and OpenVPN
ufw allow 22/tcp
ufw allow "${VPN_PORT}/${VPN_PROTO}"

# Default forward policy to ACCEPT
sed -i 's/^DEFAULT_FORWARD_POLICY=.*/DEFAULT_FORWARD_POLICY="ACCEPT"/' /etc/default/ufw

# NAT rules
UFW_BEFORE="/etc/ufw/before.rules"
if ! grep -q "OPENVPN NAT RULES" "${UFW_BEFORE}" 2>/dev/null; then
  cp "${UFW_BEFORE}" "${UFW_BEFORE}.bak.$(date +%s)" || true
  cat > "${UFW_BEFORE}" <<EOF
# rules.before
# (rest of file managed; includes NAT for OpenVPN)

*nat
:POSTROUTING ACCEPT [0:0]
# OPENVPN NAT RULES
-A POSTROUTING -s ${VPN_NET} -o ${EGRESS_IFACE} -j MASQUERADE
COMMIT

*filter
:ufw-before-input - [0:0]
:ufw-before-output - [0:0]
:ufw-before-forward - [0:0]
:ufw-not-local - [0:0]
# allow all on loopback
-A ufw-before-input -i lo -j ACCEPT
-A ufw-before-output -o lo -j ACCEPT
# drop RFC1918 packets not coming from LAN
-A ufw-not-local -m addrtype --dst-type LOCAL -j RETURN
-A ufw-not-local -m addrtype --dst-type MULTICAST -j RETURN
-A ufw-not-local -m addrtype --dst-type BROADCAST -j RETURN
-A ufw-before-input -j ufw-not-local
# allow established/related
-A ufw-before-input -m state --state RELATED,ESTABLISHED -j ACCEPT
-A ufw-before-forward -m state --state RELATED,ESTABLISHED -j ACCEPT
# allow ping
-A ufw-before-input -p icmp --icmp-type echo-request -j ACCEPT
# allow DHCP client
-A ufw-before-input -p udp --sport 67 --dport 68 -j ACCEPT
# allow OpenVPN traffic in the before chain so policy applies after
-A ufw-before-input -p ${VPN_PROTO} --dport ${VPN_PORT} -j ACCEPT
# allow forwarding for VPN subnet
-A ufw-before-forward -s ${VPN_NET} -j ACCEPT
-A ufw-before-forward -d ${VPN_NET} -j ACCEPT
# end of before rules
COMMIT
EOF
fi

# Enable UFW non-interactively
ufw --force enable
ufw status verbose || true

#=== enable & start OpenVPN ===#
systemctl enable --now "openvpn-server@server.service"
sleep 2
systemctl --no-pager --full status "openvpn-server@server.service" || true

#=== build client profile ===#
CA_FILE="/root/ovpn-clients/${CLIENT_NAME}/ca.crt"
CRT_FILE="/root/ovpn-clients/${CLIENT_NAME}/${CLIENT_NAME}.crt"
KEY_FILE="/root/ovpn-clients/${CLIENT_NAME}/${CLIENT_NAME}.key"
TC_FILE="/root/ovpn-clients/${CLIENT_NAME}/tc.key"

cat > "${PROFILE_OUT}" <<EOF
client
dev tun
proto ${VPN_PROTO}
remote ${PUBLIC_ADDR} ${VPN_PORT}
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
cipher AES-256-GCM
auth SHA256
verb 3
key-direction 1
explicit-exit-notify 1
auth-nocache
sndbuf 0
rcvbuf 0

<ca>
$(cat "${CA_FILE}")
</ca>
<cert>
$(awk '/BEGIN CERTIFICATE/{flag=1} flag{print} /END CERTIFICATE/{flag=0}' "${CRT_FILE}")
</cert>
<key>
$(cat "${KEY_FILE}")
</key>
<tls-crypt>
$(cat "${TC_FILE}")
</tls-crypt>
EOF

chmod 600 "${PROFILE_OUT}"

echo
echo "OpenVPN server is configured."
echo "Default network: ${VPN_NET} via ${EGRESS_IFACE}"
echo "Public address used in profile: ${PUBLIC_ADDR}"
echo "Client profile written to: ${PROFILE_OUT}"
echo
echo "Tip: download it securely and import into your OpenVPN client."
echo "If this instance should route other subnets, ensure AWS 'Source/Dest Check' is disabled and relevant routes are in the VPC."
