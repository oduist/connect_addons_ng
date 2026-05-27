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
        # Extract the freshest non-expired cert+key bundle for FS_DOMAIN
        # from Traefik's acme.json. acme.json may contain entries from
        # multiple resolvers (e.g. an old "le" alongside a new "letsencrypt"),
        # so we collect all matches, drop expired ones, and pick the one
        # with the latest notAfter — that is the renewed certificate.
        BUNDLE=$(FS_DOMAIN="$FS_DOMAIN" ACME_FILE="$ACME_FILE" python3 <<'PY'
import base64, datetime, json, os, subprocess, sys

target = os.environ["FS_DOMAIN"]
parts = target.split(".", 1)
wildcard = "*." + parts[1] if len(parts) == 2 else None

try:
    with open(os.environ["ACME_FILE"]) as f:
        data = json.load(f)
except Exception as exc:
    print(f"acme.json read error: {exc}", file=sys.stderr)
    sys.exit(1)

candidates = []
for resolver_name, resolver in data.items():
    for cert in (resolver.get("Certificates") or []):
        dom = cert.get("domain", {})
        names = {dom.get("main", "")} | set(dom.get("sans") or [])
        if not (target in names or (wildcard and wildcard in names)):
            continue
        try:
            cert_pem = base64.b64decode(cert["certificate"]).decode()
            key_pem = base64.b64decode(cert["key"]).decode()
        except Exception as exc:
            print(f"skip {resolver_name}: decode error: {exc}", file=sys.stderr)
            continue
        r = subprocess.run(
            ["openssl", "x509", "-noout", "-enddate"],
            input=cert_pem, capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(f"skip {resolver_name}: openssl error: {r.stderr.strip()}", file=sys.stderr)
            continue
        end = r.stdout.strip().split("=", 1)[1]
        not_after = datetime.datetime.strptime(end, "%b %d %H:%M:%S %Y %Z")
        candidates.append((not_after, resolver_name, cert_pem, key_pem))

now = datetime.datetime.utcnow()
fresh = [c for c in candidates if c[0] > now]
if not fresh:
    if candidates:
        latest = max(candidates, key=lambda c: c[0])
        print(
            f"all matching certificates expired (latest: {latest[1]} notAfter={latest[0]})",
            file=sys.stderr,
        )
    sys.exit(1)

fresh.sort(key=lambda c: c[0], reverse=True)
not_after, resolver_name, cert_pem, key_pem = fresh[0]
print(
    f"picked cert from resolver {resolver_name!r} notAfter={not_after.isoformat()}Z",
    file=sys.stderr,
)
# FS expects key first, then cert
sys.stdout.write(key_pem)
if not key_pem.endswith("\n"):
    sys.stdout.write("\n")
sys.stdout.write(cert_pem)
PY
)

        if [ -n "$BUNDLE" ]; then
            printf '%s' "$BUNDLE" > "$TLS_DIR/wss.pem"
            cp "$TLS_DIR/wss.pem" "$TLS_DIR/dtls-srtp.pem"
            echo "TLS certificate installed from Traefik ACME for $FS_DOMAIN"
            return
        fi
        echo "Warning: no valid (non-expired) certificate for $FS_DOMAIN in ACME store"
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
    # Substitute the placeholder in event_socket.conf.xml with the
    # per-installation password from FS_ESL_PASSWORD. The variable is
    # mandatory — we refuse to start with the placeholder still in
    # place so a misconfigured deployment fails loudly instead of
    # silently exposing a known password on the ESL socket.
    CONF=/usr/local/freeswitch/etc/freeswitch/autoload_configs/event_socket.conf.xml
    if [ -z "$FS_ESL_PASSWORD" ]; then
        echo "FS_ESL_PASSWORD is not set. Generate a per-installation secret (e.g. 'openssl rand -hex 32') and pass it in the container environment. Refusing to start." >&2
        exit 1
    fi
    case "$FS_ESL_PASSWORD" in
        *\<*|*\>*|*\"*|*\&*)
            echo "FS_ESL_PASSWORD contains an XML metacharacter (<>\"&). Refusing to start." >&2
            exit 1
            ;;
    esac
    if [ ! -f "$CONF" ]; then
        echo "Cannot find $CONF. Refusing to start." >&2
        exit 1
    fi
    if ! grep -q 'name="password"' "$CONF"; then
        echo "No password param in $CONF. Refusing to start." >&2
        exit 1
    fi
    sed -i 's|<param name="password" value="[^"]*"/>|<param name="password" value="'"$FS_ESL_PASSWORD"'"/>|' "$CONF"
    if grep -q '__SET_FS_ESL_PASSWORD__' "$CONF"; then
        echo "sed substitution failed: placeholder still present in $CONF. Refusing to start." >&2
        exit 1
    fi
    echo "Applied FS_ESL_PASSWORD to event_socket.conf.xml"
}

download_sounds
setup_tls
apply_esl_password

trap 'freeswitch -stop' TERM

exec /usr/bin/freeswitch -nf -nonat
