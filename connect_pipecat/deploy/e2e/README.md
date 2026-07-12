# Pipecat SIPp E2E harness

This image executes one authenticated SIP call and injects a spoken interrupt
into the agent's greeting. It is opt-in because it requires a real FreeSWITCH,
sidecar, provider credentials and a temporary SIP endpoint.

Required environment variables:

- `SIPP_REMOTE_IP` — FreeSWITCH SIP address reachable from the runner;
- `SIPP_DESTINATION` — temporary Pipecat extension;
- `SIPP_AUTH_USER` and `SIPP_AUTH_PASSWORD` — temporary endpoint credentials.

`SIPP_LOCAL_IP`, `SIPP_LOCAL_PORT`, `SIPP_MEDIA_PORT`, and `SIPP_RUN_ID` are
optional. Set `SIPP_DISABLED=1` to keep the container available for a manual,
isolated invocation using different local SIP/RTP ports.

The runner exits non-zero on SIP dialog failure and writes SIPp message, error,
and generated caller-audio PCAP artifacts to its working directory. Verify the
media outcome afterwards in the Pipecat sidecar logs (`Sending killAudio…`) and
in the Odoo call, recording, transcript and summary records.
