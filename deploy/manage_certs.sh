#!/bin/bash
#
# manage_certs.sh — wrapper around easy-rsa for the OpenVPN Telegram Bot
#
# Usage:
#   manage_certs.sh list                       — list valid client certificates
#   manage_certs.sh generate <common_name>     — generate a new client certificate + .ovpn
#   manage_certs.sh revoke <common_name>       — revoke a client certificate
#   manage_certs.sh renew <common_name>        — revoke and re-issue a client certificate
#
# Supports both:
#   - /etc/openvpn/server/ (newer installations)
#   - /etc/openvpn/ (older installations)

set -euo pipefail

# ---------- path detection ----------

# Detect OpenVPN configuration directory
detect_openvpn_dir() {
    # Priority 1: Explicit environment variable
    if [[ -n "${OPENVPN_SERVER_DIR:-}" && -d "$OPENVPN_SERVER_DIR" ]]; then
        echo "$OPENVPN_SERVER_DIR"
        return
    fi
    
    # Priority 2: New path (/etc/openvpn/server/)
    if [[ -f "/etc/openvpn/server/server.conf" ]]; then
        echo "/etc/openvpn/server"
        return
    fi
    
    # Priority 3: Old path (/etc/openvpn/)
    if [[ -f "/etc/openvpn/server.conf" ]]; then
        echo "/etc/openvpn"
        return
    fi
    
    die "Cannot locate OpenVPN configuration. Tried:
  - /etc/openvpn/server/server.conf
  - /etc/openvpn/server.conf
Set OPENVPN_SERVER_DIR environment variable for non-standard installations."
}

# Get value from server.conf
get_server_conf_value() {
    local key="$1"
    local server_conf="$2"
    grep -E "^$key\s+" "$server_conf" 2>/dev/null | awk '{print $2}' | head -1
}

# Get server IP for client configuration
get_server_ip() {
    # Priority 1: Explicit environment variable
    if [[ -n "${OPENVPN_SERVER_IP:-}" ]]; then
        echo "$OPENVPN_SERVER_IP"
        return
    fi
    
    # Priority 2: Try to get external IP
    local external_ip=""
    external_ip=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || true)
    if [[ -n "$external_ip" && "$external_ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "$external_ip"
        return
    fi
    
    external_ip=$(curl -s --max-time 5 icanhazip.com 2>/dev/null || true)
    if [[ -n "$external_ip" ]]; then
        echo "$external_ip"
        return
    fi
    
    # Priority 3: hostname -I (first IP)
    external_ip=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
    if [[ -n "$external_ip" ]]; then
        echo "$external_ip"
        return
    fi
    
    # Fallback: user must configure manually
    echo "YOUR_SERVER_IP"
}

# Find client template file
find_client_template() {
    local openvpn_dir="$1"
    
    # Priority 1: Explicit path from environment
    if [[ -n "${OPENVPN_CLIENT_TEMPLATE:-}" && -f "$OPENVPN_CLIENT_TEMPLATE" ]]; then
        echo "$OPENVPN_CLIENT_TEMPLATE"
        return
    fi
    
    # Priority 2: client-template.txt in OpenVPN dir
    if [[ -f "$openvpn_dir/client-template.txt" ]]; then
        echo "$openvpn_dir/client-template.txt"
        return
    fi
    
    # Priority 3: client-common.txt in OpenVPN dir
    if [[ -f "$openvpn_dir/client-common.txt" ]]; then
        echo "$openvpn_dir/client-common.txt"
        return
    fi
    
    # Priority 4: generate dynamically
    echo ""
}

# Find tls-crypt key file
find_tls_crypt_key() {
    local openvpn_dir="$1"
    local server_conf="$2"
    
    # Priority 1: Explicit environment variable
    if [[ -n "${OPENVPN_TLS_CRYPT_KEY:-}" && -f "$OPENVPN_TLS_CRYPT_KEY" ]]; then
        echo "$OPENVPN_TLS_CRYPT_KEY"
        return
    fi
    
    # Priority 2: Parse filename from server.conf (tls-crypt <filename>)
    local tls_crypt_file=$(grep -E '^tls-crypt\s+' "$server_conf" 2>/dev/null | awk '{print $2}')
    
    if [[ -n "$tls_crypt_file" ]]; then
        # Check if absolute path
        if [[ "$tls_crypt_file" == /* ]]; then
            if [[ -f "$tls_crypt_file" ]]; then
                echo "$tls_crypt_file"
                return
            fi
        else
            # Relative path - try relative to server.conf directory first
            local conf_dir=$(dirname "$server_conf")
            if [[ -f "$conf_dir/$tls_crypt_file" ]]; then
                echo "$conf_dir/$tls_crypt_file"
                return
            fi
            # Try relative to openvpn_dir
            if [[ -f "$openvpn_dir/$tls_crypt_file" ]]; then
                echo "$openvpn_dir/$tls_crypt_file"
                return
            fi
        fi
    fi
    
    # Priority 3: Standard filenames
    if [[ -f "$openvpn_dir/tls-crypt.key" ]]; then
        echo "$openvpn_dir/tls-crypt.key"
        return
    fi
    
    if [[ -f "$openvpn_dir/tc.key" ]]; then
        echo "$openvpn_dir/tc.key"
        return
    fi
    
    # Not found - return empty
    echo ""
}

# Find tls-auth key file
find_tls_auth_key() {
    local openvpn_dir="$1"
    local server_conf="$2"
    
    # Priority 1: Explicit environment variable
    if [[ -n "${OPENVPN_TLS_AUTH_KEY:-}" && -f "$OPENVPN_TLS_AUTH_KEY" ]]; then
        echo "$OPENVPN_TLS_AUTH_KEY"
        return
    fi
    
    # Priority 2: Parse filename from server.conf (tls-auth <filename>)
    local tls_auth_file=$(grep -E '^tls-auth\s+' "$server_conf" 2>/dev/null | awk '{print $2}')
    
    if [[ -n "$tls_auth_file" ]]; then
        # Check if absolute path
        if [[ "$tls_auth_file" == /* ]]; then
            if [[ -f "$tls_auth_file" ]]; then
                echo "$tls_auth_file"
                return
            fi
        else
            # Relative path - try relative to server.conf directory first
            local conf_dir=$(dirname "$server_conf")
            if [[ -f "$conf_dir/$tls_auth_file" ]]; then
                echo "$conf_dir/$tls_auth_file"
                return
            fi
            # Try relative to openvpn_dir
            if [[ -f "$openvpn_dir/$tls_auth_file" ]]; then
                echo "$openvpn_dir/$tls_auth_file"
                return
            fi
        fi
    fi
    
    # Priority 3: Standard filenames
    if [[ -f "$openvpn_dir/tls-auth.key" ]]; then
        echo "$openvpn_dir/tls-auth.key"
        return
    fi
    
    if [[ -f "$openvpn_dir/ta.key" ]]; then
        echo "$openvpn_dir/ta.key"
        return
    fi
    
    # Not found - return empty
    echo ""
}

# ---------- globals (set by init) ----------

init_paths() {
    OPENVPN_DIR=$(detect_openvpn_dir)
    
    # Server configuration file
    SERVER_CONF="${OPENVPN_SERVER_CONF:-$OPENVPN_DIR/server.conf}"
    [[ -f "$SERVER_CONF" ]] || die "server.conf not found at $SERVER_CONF"
    
    # Easy-RSA directory
    EASYRSA_DIR="${OPENVPN_EASYRSA_DIR:-$OPENVPN_DIR/easy-rsa}"
    PKI_DIR="$EASYRSA_DIR/pki"
    
    # Output directory for .ovpn files
    OVPN_OUTPUT_DIR="${OPENVPN_CERT_DIR:-$PKI_DIR}"
    
    # Client template
    CLIENT_TEMPLATE=$(find_client_template "$OPENVPN_DIR")
    
    # CRL and IPP files
    CRL_PEM="${OPENVPN_CRL_PEM:-$OPENVPN_DIR/crl.pem}"
    IPP_TXT="${OPENVPN_IPP_TXT:-$OPENVPN_DIR/ipp.txt}"
}

# ---------- helpers ----------

die() {
    echo "$1" >&2
    exit 1
}

validate_name() {
    # allow alphanumeric, underscore, dash — same regex as openvpn-install.sh
    if [[ ! "$1" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        die "Invalid client name: '$1'. Use only letters, digits, hyphens and underscores."
    fi
}

check_easyrsa() {
    [[ -d "$EASYRSA_DIR" ]] || die "easy-rsa not found at $EASYRSA_DIR"
    [[ -f "$EASYRSA_DIR/easyrsa" ]] || die "easyrsa binary not found in $EASYRSA_DIR"
}

# ---------- operations ----------

do_list() {
    init_paths
    check_easyrsa
    local index="$PKI_DIR/index.txt"
    [[ -f "$index" ]] || die "PKI index not found at $index"

    # Valid certs start with 'V'; extract CN, strip BANNED_ prefix
    while IFS= read -r line; do
        local cn
        cn=$(echo "$line" | sed 's/.*CN=\([^ ]*\).*/\1/')
        # Strip BANNED_ prefix for display
        cn="${cn#BANNED_}"
        echo "$cn"
    done < <(tail -n +2 "$index" | grep '^V')
}

do_generate() {
    local name="$1"
    
    # Strip BANNED_ prefix if present
    name="${name#BANNED_}"
    
    validate_name "$name"
    
    init_paths
    check_easyrsa

    cd "$EASYRSA_DIR" || die "Cannot cd to $EASYRSA_DIR"

    # Check if certificate already exists
    if tail -n +2 "$PKI_DIR/index.txt" 2>/dev/null | grep -qE "^V.*/CN=$name\$"; then
        die "Certificate for '$name' already exists."
    fi

    # Generate certificate (nopass = no password on private key)
    EASYRSA_CERT_EXPIRE=3650 ./easyrsa --batch build-client-full "$name" nopass \
        > /dev/null 2>&1 || die "Failed to generate certificate for '$name'"

    # Get server settings from server.conf
    local server_ip=$(get_server_ip)
    local port=$(get_server_conf_value "port" "$SERVER_CONF")
    local proto=$(get_server_conf_value "proto" "$SERVER_CONF")
    local auth=$(get_server_conf_value "auth" "$SERVER_CONF")
    local cipher=$(get_server_conf_value "cipher" "$SERVER_CONF")
    
    # Defaults if not found in server.conf
    port=${port:-1194}
    proto=${proto:-udp}
    auth=${auth:-SHA256}
    cipher=${cipher:-AES-256-CBC}

    # Build .ovpn file
    local ovpn_file="$OVPN_OUTPUT_DIR/$name.ovpn"
    
    if [[ -n "$CLIENT_TEMPLATE" ]]; then
        # Use existing template and update remote/proto
        cp "$CLIENT_TEMPLATE" "$ovpn_file"
        
        # Update remote line
        if grep -q "^remote " "$ovpn_file"; then
            sed -i "s/^remote .*/remote $server_ip $port/" "$ovpn_file"
        else
            sed -i "/^client/a remote $server_ip $port" "$ovpn_file"
        fi
        
        # Update proto if different
        if grep -q "^proto " "$ovpn_file"; then
            sed -i "s/^proto .*/proto $proto/" "$ovpn_file"
        fi
    else
        # Generate template dynamically
        cat > "$ovpn_file" <<EOF
client
dev tun
proto $proto
remote $server_ip $port
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
cipher $cipher
auth $auth
verb 3
EOF
    fi

    # Append certificates and keys
    {
        echo ""
        echo "<ca>"
        cat "$PKI_DIR/ca.crt"
        echo "</ca>"

        echo "<cert>"
        awk '/BEGIN/,/END CERTIFICATE/' "$PKI_DIR/issued/$name.crt"
        echo "</cert>"

        echo "<key>"
        cat "$PKI_DIR/private/$name.key"
        echo "</key>"

        # Determine tls-crypt or tls-auth
        if grep -qs '^tls-crypt' "$SERVER_CONF"; then
            local tls_crypt_key=$(find_tls_crypt_key "$OPENVPN_DIR" "$SERVER_CONF")
            if [[ -n "$tls_crypt_key" && -f "$tls_crypt_key" ]]; then
                echo "<tls-crypt>"
                cat "$tls_crypt_key"
                echo "</tls-crypt>"
            fi
        elif grep -qs '^tls-auth' "$SERVER_CONF"; then
            local tls_auth_key=$(find_tls_auth_key "$OPENVPN_DIR" "$SERVER_CONF")
            if [[ -n "$tls_auth_key" && -f "$tls_auth_key" ]]; then
                echo "key-direction 1"
                echo "<tls-auth>"
                cat "$tls_auth_key"
                echo "</tls-auth>"
            fi
        fi
    } >> "$ovpn_file"

    echo "OK"
}

do_revoke() {
    local name="$1"
    
    # Strip BANNED_ prefix if present
    name="${name#BANNED_}"
    
    validate_name "$name"
    
    init_paths
    check_easyrsa

    cd "$EASYRSA_DIR" || die "Cannot cd to $EASYRSA_DIR"

    # Check that the certificate exists (normal or banned)
    if ! tail -n +2 "$PKI_DIR/index.txt" 2>/dev/null | grep -qE "^V.*/CN=(BANNED_)?${name}$"; then
        die "Certificate '$name' not found."
    fi
    
    # If certificate is banned, unban it first (easyrsa needs clean CN)
    if tail -n +2 "$PKI_DIR/index.txt" 2>/dev/null | grep -qE "^V.*/CN=BANNED_${name}$"; then
        sed -i "s|/CN=BANNED_${name}$|/CN=${name}|g" "$PKI_DIR/index.txt"
    fi

    # Revoke (suppress easyrsa output)
    ./easyrsa --batch revoke "$name" > /dev/null 2>&1 || die "Failed to revoke certificate for '$name'"

    # Regenerate CRL (suppress easyrsa output)
    EASYRSA_CRL_DAYS=3650 ./easyrsa gen-crl > /dev/null 2>&1 || die "Failed to generate CRL"

    # Update crl.pem used by OpenVPN
    cp "$PKI_DIR/crl.pem" "$CRL_PEM"
    chmod 644 "$CRL_PEM"

    # Remove .ovpn file
    rm -f "$OVPN_OUTPUT_DIR/$name.ovpn"
    find /home/ -maxdepth 2 -name "$name.ovpn" -delete 2>/dev/null || true
    
    # Remove old certificate files (for renew compatibility)
    rm -f "$PKI_DIR/issued/${name}.crt" 2>/dev/null || true
    rm -f "$PKI_DIR/private/${name}.key" 2>/dev/null || true
    rm -f "$PKI_DIR/reqs/${name}.req" 2>/dev/null || true

    # Remove from ipp.txt (IP persistence)
    if [[ -f "$IPP_TXT" ]]; then
        sed -i "/^$name,.*/d" "$IPP_TXT" 2>/dev/null || true
    fi

    echo "OK"
}

do_renew() {
    local name="$1"

    # Renew = revoke old + generate new
    do_revoke "$name" > /dev/null 2>&1
    do_generate "$name"

    echo "OK"
}

# Check if certificate exists (normal or banned)
is_cert_exists() {
    local name="$1"
    init_paths
    local index="$PKI_DIR/index.txt"
    
    if [[ ! -f "$index" ]]; then
        return 1
    fi
    
    # Check for normal or banned certificate
    if tail -n +2 "$index" 2>/dev/null | grep -qE "^V.*/CN=(BANNED_)?${name}$"; then
        return 0
    fi
    return 1
}

# Check if certificate is banned
is_cert_banned() {
    local name="$1"
    init_paths
    local index="$PKI_DIR/index.txt"
    
    if [[ ! -f "$index" ]]; then
        return 1
    fi
    
    # Check for BANNED_ prefix
    if tail -n +2 "$index" 2>/dev/null | grep -qE "^V.*/CN=BANNED_${name}$"; then
        return 0  # Is banned
    fi
    return 1  # Not banned
}

# Ban certificate by renaming CN in index.txt
do_ban() {
    local name="$1"
    
    # Strip BANNED_ prefix if present (in case user passed BANNED_name)
    name="${name#BANNED_}"
    
    validate_name "$name"
    
    init_paths
    check_easyrsa
    
    local index="$PKI_DIR/index.txt"
    [[ -f "$index" ]] || die "PKI index not found at $index"
    
    # Check if already banned
    if tail -n +2 "$index" 2>/dev/null | grep -qE "^V.*/CN=BANNED_${name}$"; then
        die "Certificate '$name' is already banned."
    fi
    
    # Check if certificate exists
    if ! tail -n +2 "$index" 2>/dev/null | grep -qE "^V.*/CN=${name}$"; then
        die "Certificate for '$name' not found."
    fi
    
    # Replace CN=name with CN=BANNED_name
    sed -i "s|/CN=${name}$|/CN=BANNED_${name}|g" "$index"
    
    # Regenerate CRL (empty - no real revocations)
    cd "$EASYRSA_DIR" || die "Cannot cd to $EASYRSA_DIR"
    ./easyrsa gen-crl > /dev/null 2>&1 || die "Failed to regenerate CRL"
    
    # Update crl.pem
    cp "$PKI_DIR/crl.pem" "$CRL_PEM"
    chmod 644 "$CRL_PEM"
    
    echo "OK"
}

# Unban certificate by restoring CN in index.txt
do_unban() {
    local name="$1"
    
    # Strip BANNED_ prefix if present (in case user passed BANNED_name)
    name="${name#BANNED_}"
    
    validate_name "$name"
    
    init_paths
    check_easyrsa
    
    local index="$PKI_DIR/index.txt"
    [[ -f "$index" ]] || die "PKI index not found at $index"
    
    # Check if banned certificate exists
    if ! tail -n +2 "$index" 2>/dev/null | grep -qE "^V.*/CN=BANNED_${name}$"; then
        die "Banned certificate for '$name' not found."
    fi
    
    # Replace CN=BANNED_name with CN=name
    sed -i "s|/CN=BANNED_${name}$|/CN=${name}|g" "$index"
    
    # Regenerate CRL
    cd "$EASYRSA_DIR" || die "Cannot cd to $EASYRSA_DIR"
    ./easyrsa gen-crl > /dev/null 2>&1 || die "Failed to regenerate CRL"
    
    # Update crl.pem
    cp "$PKI_DIR/crl.pem" "$CRL_PEM"
    chmod 644 "$CRL_PEM"
    
    echo "OK"
}

# List all certificates including banned ones (with status marker)
do_list_all() {
    init_paths
    check_easyrsa
    
    local index="$PKI_DIR/index.txt"
    [[ -f "$index" ]] || die "PKI index not found at $index"
    
    # Extract all CNs with status
    while IFS= read -r line; do
        local cn
        cn=$(echo "$line" | sed 's/.*CN=\([^ ]*\).*/\1/')
        if [[ "$cn" == BANNED_* ]]; then
            # Show as: [BANNED] Test (clean name)
            local clean_name="${cn#BANNED_}"
            echo "[BANNED] $clean_name"
        else
            echo "$cn"
        fi
    done < <(tail -n +2 "$index" | grep '^V')
}

# List only certificate names (for internal use, no status markers)
do_list_names() {
    init_paths
    check_easyrsa
    
    local index="$PKI_DIR/index.txt"
    [[ -f "$index" ]] || die "PKI index not found at $index"
    
    # Extract clean CNs (strip BANNED_ prefix)
    tail -n +2 "$index" | grep '^V' | sed -nT 's|.*CN=\(.*\)|\1|p' | sed 's/^BANNED_//'
}

# ---------- main ----------

[[ $# -ge 1 ]] || die "Usage: $0 <list|list-all|generate|revoke|renew|ban|unban|check-ban> [common_name]"

ACTION="$1"
shift

case "$ACTION" in
    list)
        do_list
        ;;
    list-all)
        do_list_all
        ;;
    generate)
        [[ $# -ge 1 ]] || die "Usage: $0 generate <common_name>"
        do_generate "$1"
        ;;
    revoke)
        [[ $# -ge 1 ]] || die "Usage: $0 revoke <common_name>"
        do_revoke "$1"
        ;;
    renew)
        [[ $# -ge 1 ]] || die "Usage: $0 renew <common_name>"
        do_renew "$1"
        ;;
    ban)
        [[ $# -ge 1 ]] || die "Usage: $0 ban <common_name>"
        do_ban "$1"
        ;;
    unban)
        [[ $# -ge 1 ]] || die "Usage: $0 unban <common_name>"
        do_unban "$1"
        ;;
    check-ban)
        [[ $# -ge 1 ]] || die "Usage: $0 check-ban <common_name>"
        if is_cert_banned "$1"; then
            echo "banned"
        else
            echo "not_banned"
        fi
        ;;
    check-exists)
        [[ $# -ge 1 ]] || die "Usage: $0 check-exists <common_name>"
        if is_cert_exists "$1"; then
            echo "exists"
        else
            echo "not_exists"
        fi
        ;;
    *)
        die "Unknown operation: '$ACTION'. Use: list, list-all, generate, revoke, renew, ban, unban, check-ban, check-exists"
        ;;
esac
