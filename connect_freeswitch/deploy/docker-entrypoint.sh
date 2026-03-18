#!/bin/sh
set -e

BASEURL=http://files.freeswitch.org
SOUNDS_DIR=/usr/share/freeswitch/sounds

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

download_sounds

trap 'freeswitch -stop' TERM

exec /usr/bin/freeswitch -nf -nonat
