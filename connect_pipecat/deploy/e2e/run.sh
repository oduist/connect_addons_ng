#!/bin/sh
set -eu

: "${SIPP_REMOTE_IP:?set SIPP_REMOTE_IP}"
: "${SIPP_DESTINATION:?set SIPP_DESTINATION}"
: "${SIPP_AUTH_USER:?set SIPP_AUTH_USER}"
: "${SIPP_AUTH_PASSWORD:?set SIPP_AUTH_PASSWORD}"

if [ "${SIPP_DISABLED:-0}" = "1" ]; then
  exec sleep infinity
fi

remote_port="${SIPP_REMOTE_PORT:-5080}"
local_port="${SIPP_LOCAL_PORT:-5062}"
media_port="${SIPP_MEDIA_PORT:-6000}"
local_ip="${SIPP_LOCAL_IP:-$SIPP_REMOTE_IP}"
run_id="${SIPP_RUN_ID:-$(date +%s)}"

printf 'SEQUENTIAL\n%s;%s\n' "$SIPP_AUTH_USER" "$SIPP_AUTH_PASSWORD" > users.csv
espeak-ng -v en-us -s 135 -w caller-interrupt.wav \
  'interrupt now. Say the verification word orange.'
ffmpeg -hide_banner -loglevel error -y -i caller-interrupt.wav \
  -ar 8000 -ac 1 -f mulaw caller-interrupt.pcmu
python3 make_pcap.py caller-interrupt.pcmu caller-interrupt.pcap

sipp "$SIPP_REMOTE_IP:$remote_port" \
  -sf scenario.xml -inf users.csv -s "$SIPP_DESTINATION" \
  -i "$local_ip" -p "$local_port" -mi "$local_ip" -mp "$media_port" \
  -cid_str "pipecat-e2e-${run_id}-%u@%s" \
  -m 1 -timeout 30000 -trace_err -trace_msg
