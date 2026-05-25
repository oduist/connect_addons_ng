#!/bin/sh

BASEURL=http://files.freeswitch.org
SOUNDS_DIR=/usr/share/freeswitch/sounds
TLS_DIR=/usr/local/freeswitch/etc/freeswitch/tls
ACME_FILE=/etc/traefik/acme.json

download_sounds() {
    SRATES=$(echo "$SOUND_RATES" | sed -e 's/:/ /g')
    STYPES=$(echo "$SOUND_TYPES" | sed -e 's/:/ /g')

    if [ -z "$SRATES" ] || [ -z "$STYPES" ]; then
        echo "SOUND_RATES or SOUND_TYPES not set, skipping sound download."
        return
    fi

    cd /tmp
    for stype in $STYPES; do
        for srate in $SRATES; do
            fname="freeswitch-sounds-${stype}-${srate}-1.0.52.tar.gz"
            if [ -f "${SOUNDS_DIR}/.${fname}.done" ]; then
                echo "Skipping $fname (already extracted)"
                continue
            fi
            echo "Downloading $fname..."
            if wget -q "${BASEURL}/${fname}"; then
                tar xzf "$fname" -C "$SOUNDS_DIR"/
                touch "${SOUNDS_DIR}/.${fname}.done"
                rm -f "$fname"
            else
                echo "Warning: failed to download $fname"
            fi
        done
    done
}

setup_tls() {
    mkdir -p "$TLS_DIR"

    if [ -f "$ACME_FILE" ] && [ -n "$FS_DOMAIN" ]; then
        echo "Extracting TLS certificate for $FS_DOMAIN from Traefik ACME..."
        # Extract cert and key for FS_DOMAIN from Traefik acme.json
        # acme.json stores certs as base64-encoded PEM
        CERT=$(python3 -c "
import json, base64, sys
try:
    with open('$ACME_FILE') as f:
        data = json.load(f)
    for resolver in data.values():
        for cert in (resolver.get('Certificates') or []):
            main = cert.get('domain', {}).get('main', '')
            sans = cert.get('domain', {}).get('sans') or []
            if main == '$FS_DOMAIN' or '$FS_DOMAIN' in sans:
                print(base64.b64decode(cert['certificate']).decode(), end='')
                sys.exit(0)
    # Try wildcard match
    parts = '$FS_DOMAIN'.split('.', 1)
    if len(parts) == 2:
        wildcard = '*.' + parts[1]
        for resolver in data.values():
            for cert in (resolver.get('Certificates') or []):
                main = cert.get('domain', {}).get('main', '')
                sans = cert.get('domain', {}).get('sans') or []
                if main == wildcard or wildcard in sans:
                    print(base64.b64decode(cert['certificate']).decode(), end='')
                    sys.exit(0)
    sys.exit(1)
except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
")

        KEY=$(python3 -c "
import json, base64, sys
try:
    with open('$ACME_FILE') as f:
        data = json.load(f)
    for resolver in data.values():
        for cert in (resolver.get('Certificates') or []):
            main = cert.get('domain', {}).get('main', '')
            sans = cert.get('domain', {}).get('sans') or []
            if main == '$FS_DOMAIN' or '$FS_DOMAIN' in sans:
                print(base64.b64decode(cert['key']).decode(), end='')
                sys.exit(0)
    parts = '$FS_DOMAIN'.split('.', 1)
    if len(parts) == 2:
        wildcard = '*.' + parts[1]
        for resolver in data.values():
            for cert in (resolver.get('Certificates') or []):
                main = cert.get('domain', {}).get('main', '')
                sans = cert.get('domain', {}).get('sans') or []
                if main == wildcard or wildcard in sans:
                    print(base64.b64decode(cert['key']).decode(), end='')
                    sys.exit(0)
    sys.exit(1)
except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
")

        if [ -n "$CERT" ] && [ -n "$KEY" ]; then
            # Combine key + cert into PEM files (FS expects key first)
            printf '%s\n%s' "$KEY" "$CERT" > "$TLS_DIR/wss.pem"
            cp "$TLS_DIR/wss.pem" "$TLS_DIR/dtls-srtp.pem"
            echo "TLS certificate installed from Traefik ACME for $FS_DOMAIN"
            return
        fi
        echo "Warning: certificate for $FS_DOMAIN not found in ACME store"
    fi

    # Fallback: generate self-signed certificate if none exists
    if [ ! -f "$TLS_DIR/wss.pem" ]; then
        echo "Generating self-signed TLS certificate..."
        openssl req -x509 -nodes -days 3650 \
            -newkey rsa:4096 \
            -keyout "$TLS_DIR/key.pem" \
            -out "$TLS_DIR/cert.pem" \
            -subj "/C=US/CN=${FS_DOMAIN:-FreeSWITCH}" 2>/dev/null
        cat "$TLS_DIR/key.pem" "$TLS_DIR/cert.pem" > "$TLS_DIR/wss.pem"
        cp "$TLS_DIR/wss.pem" "$TLS_DIR/dtls-srtp.pem"
        rm -f "$TLS_DIR/key.pem" "$TLS_DIR/cert.pem"
        echo "Self-signed TLS certificate generated"
    fi
}

apply_esl_password() {
    # Replace the ClueCon default in event_socket.conf.xml with whatever
    # the operator put in FS_ESL_PASSWORD. Leave the file alone if the
    # var is not set so behaviour stays backwards-compatible.
    if [ -z "$FS_ESL_PASSWORD" ]; then
        return
    fi
    case "$FS_ESL_PASSWORD" in
        *\<*|*\>*|*\"*|*\&*)
            echo "Refusing to apply FS_ESL_PASSWORD: contains XML metacharacter." >&2
            return
            ;;
    esac
    CONF=/usr/local/freeswitch/etc/freeswitch/autoload_configs/event_socket.conf.xml
    if [ ! -f "$CONF" ]; then
        echo "Cannot find $CONF; skipping ESL password substitution." >&2
        return
    fi
    if ! grep -q 'name="password"' "$CONF"; then
        echo "No password param in $CONF; skipping ESL password substitution." >&2
        return
    fi
    sed -i 's|<param name="password" value="[^"]*"/>|<param name="password" value="'"$FS_ESL_PASSWORD"'"/>|' "$CONF"
    echo "Applied FS_ESL_PASSWORD to event_socket.conf.xml"
}

download_sounds
setup_tls
apply_esl_password

trap 'freeswitch -stop' TERM

exec /usr/bin/freeswitch -nf -nonat
