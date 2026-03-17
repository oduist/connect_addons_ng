FROM --platform=linux/amd64 safarov/freeswitch:latest

# Copy FreeSWITCH configuration files
COPY freeswitch/conf /etc/freeswitch

# Set default environment variables
ENV SOUND_RATES=8000:16000 \
    SOUND_TYPES=music:en-us-callie \
    EPMD=false \
    DUMPCAP=false \
    ODOO_URL=http://localhost:8069 \
    FS_LOG_LEVEL=info \
    FS_SOFIA_LOG_LEVEL=0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD fs_cli -x "status" > /dev/null 2>&1 || exit 1

# Run FreeSWITCH
CMD ["freeswitch", "-c"]
