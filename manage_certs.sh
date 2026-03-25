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
# Requires: easy-rsa installed by openvpn-install.sh at /etc/openvpn/easy-rsa/

set -euo pipefail

EASYRSA_DIR="/etc/openvpn/easy-rsa"
PKI_DIR="$EASYRSA_DIR/pki"
CLIENT_TEMPLATE="/etc/openvpn/client-template.txt"
OVPN_OUTPUT_DIR="${OPENVPN_CERT_DIR:-/etc/openvpn/easy-rsa/pki}"  # where .ovpn files are saved (from .env)

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

check_client_template() {
    [[ -f "$CLIENT_TEMPLATE" ]] || die "Client template not found at $CLIENT_TEMPLATE"
}

# ---------- operations ----------

do_list() {
    check_easyrsa
    local index="$PKI_DIR/index.txt"
    [[ -f "$index" ]] || die "PKI index not found at $index"

    # Valid certs start with 'V'; extract CN (field after '/')
    local certs
    certs=$(tail -n +2 "$index" | grep '^V' | cut -d '=' -f 2)

    if [[ -z "$certs" ]]; then
        echo "No valid certificates found."
    else
        echo "$certs"
    fi
}

do_generate() {
    local name="$1"
    validate_name "$name"
    check_easyrsa
    check_client_template

    cd "$EASYRSA_DIR" || die "Cannot cd to $EASYRSA_DIR"

    # Check if certificate already exists
    if tail -n +2 "$PKI_DIR/index.txt" 2>/dev/null | grep -qE "^V.*/CN=$name\$"; then
        die "Certificate for '$name' already exists."
    fi

    # Generate certificate (nopass = no password on private key)
    EASYRSA_CERT_EXPIRE=3650 ./easyrsa --batch build-client-full "$name" nopass || die "Failed to generate certificate for '$name'"

    # Build .ovpn file
    local ovpn_file="$OVPN_OUTPUT_DIR/$name.ovpn"
    cp "$CLIENT_TEMPLATE" "$ovpn_file"

    {
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
        if grep -qs '^tls-crypt' /etc/openvpn/server.conf; then
            echo "<tls-crypt>"
            cat /etc/openvpn/tls-crypt.key
            echo "</tls-crypt>"
        elif grep -qs '^tls-auth' /etc/openvpn/server.conf; then
            echo "key-direction 1"
            echo "<tls-auth>"
            cat /etc/openvpn/tls-auth.key
            echo "</tls-auth>"
        fi
    } >> "$ovpn_file"

    echo "Certificate for '$name' generated. Config saved to $ovpn_file"
}

do_revoke() {
    local name="$1"
    validate_name "$name"
    check_easyrsa

    cd "$EASYRSA_DIR" || die "Cannot cd to $EASYRSA_DIR"

    # Check that the certificate exists and is valid
    if ! tail -n +2 "$PKI_DIR/index.txt" 2>/dev/null | grep -qE "^V.*/CN=$name\$"; then
        die "No valid certificate found for '$name'."
    fi

    # Revoke
    ./easyrsa --batch revoke "$name" || die "Failed to revoke certificate for '$name'"

    # Regenerate CRL
    EASYRSA_CRL_DAYS=3650 ./easyrsa gen-crl || die "Failed to generate CRL"

    # Update crl.pem used by OpenVPN
    cp "$PKI_DIR/crl.pem" /etc/openvpn/crl.pem
    chmod 644 /etc/openvpn/crl.pem

    # Remove .ovpn file
    rm -f "$OVPN_OUTPUT_DIR/$name.ovpn"
    find /home/ -maxdepth 2 -name "$name.ovpn" -delete 2>/dev/null || true

    # Remove from ipp.txt (IP persistence)
    sed -i "/^$name,.*/d" /etc/openvpn/ipp.txt 2>/dev/null || true

    echo "Certificate for '$name' revoked."
}

do_renew() {
    local name="$1"

    # Renew = revoke old + generate new
    do_revoke "$name"
    do_generate "$name"

    echo "Certificate for '$name' renewed."
}

# ---------- main ----------

[[ $# -ge 1 ]] || die "Usage: $0 <list|generate|revoke|renew> [common_name]"

ACTION="$1"
shift

case "$ACTION" in
    list)
        do_list
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
    *)
        die "Unknown operation: '$ACTION'. Use: list, generate, revoke, renew"
        ;;
esac
