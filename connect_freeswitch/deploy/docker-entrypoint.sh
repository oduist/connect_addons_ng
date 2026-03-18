#!/bin/sh
set -e

BASEURL=http://files.freeswitch.org
SOUNDS_DIR=/usr/share/freeswitch/sounds

download_sounds() {
    local SOUND_RATES=$(echo "$SOUND_RATES" | sed -e 's/:/\n/g')
    local SOUND_TYPES=$(echo "$SOUND_TYPES" | sed -e 's/:/\n/g')

    if [ -z "$SOUND_RATES" ] || [ -z "$SOUND_TYPES" ]; then
        echo "SOUND_RATES or SOUND_TYPES not set, skipping sound download."
        return
    fi

    cd /tmp
    for stype in $SOUND_TYPES; do
        for srate in $SOUND_RATES; do
            local fname="freeswitch-sounds-${stype}-${srate}-1.0.52.tar.gz"
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

trap 'freeswitch -stop' SIGTERM

/usr/bin/freeswitch -nc -nf -nonat &
pid="$!"

wait $pid
exit 0
