"""CLI entrypoint: `connect-livekit-agent run|upload-recordings`."""
import sys

import click

from .config import AgentSettings


@click.group()
def main():
    """LiveKit sidecar for Oduist Connect."""


@main.command()
def run():
    """Run the voice-AI agent worker (LiveKit Agents)."""
    from . import agent
    # livekit-agents' own CLI consumes argv; hand it just the subcommand
    # it expects to start a worker.
    sys.argv = [sys.argv[0], "start"]
    agent.run(AgentSettings())


@main.command("upload-recordings")
def upload_recordings():
    """Watch the egress volume and deliver finished files to Odoo."""
    from . import uploader
    uploader.run(AgentSettings())


if __name__ == "__main__":
    main()
