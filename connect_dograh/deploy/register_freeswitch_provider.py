#!/usr/bin/env python3
"""Register the freeswitch provider package in a Dograh API source tree.

Applies the two documented one-line integration points of Dograh's
provider registry (api/services/telephony/providers/AGENTS.md):

1. api/services/telephony/providers/__init__.py — import the package
   for side effects (ProviderSpec registration).
2. api/schemas/telephony_config.py — add the config request/response
   classes to the discriminated union and the response model.

Anchored insertions fail loudly (non-zero exit) when the upstream file
shape has drifted, so an incompatible base image breaks at build time
rather than at runtime. Idempotent: re-running on a patched tree is a
no-op.
"""

import py_compile
import sys
from pathlib import Path

SCHEMA_IMPORT = """from api.services.telephony.providers.freeswitch.config import (
    FreeswitchConfigurationRequest,
    FreeswitchConfigurationResponse,
)
"""


def insert_after(content: str, anchor: str, insertion: str, label: str) -> str:
    if insertion in content:
        print(f"[skip] {label}: already applied")
        return content
    index = content.find(anchor)
    if index == -1:
        sys.exit(f"[fail] {label}: anchor not found: {anchor!r}")
    end = index + len(anchor)
    print(f"[ok] {label}")
    return content[:end] + insertion + content[end:]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: register_freeswitch_provider.py <dograh-app-root>")
    root = Path(sys.argv[1])

    providers_init = root / "api/services/telephony/providers/__init__.py"
    schema = root / "api/schemas/telephony_config.py"
    package = root / "api/services/telephony/providers/freeswitch"

    for path in (providers_init, schema, package / "__init__.py"):
        if not path.exists():
            sys.exit(f"[fail] missing: {path}")

    content = providers_init.read_text()
    content = insert_after(
        content,
        "    cloudonix,\n",
        "    freeswitch,\n",
        "providers/__init__.py import",
    )
    providers_init.write_text(content)

    content = schema.read_text()
    content = insert_after(
        content,
        "from api.services.telephony.providers.cloudonix.config import (\n"
        "    CloudonixConfigurationRequest,\n"
        "    CloudonixConfigurationResponse,\n"
        ")\n",
        SCHEMA_IMPORT,
        "telephony_config.py import",
    )
    content = insert_after(
        content,
        "        CloudonixConfigurationRequest,\n",
        "        FreeswitchConfigurationRequest,\n",
        "telephony_config.py request union",
    )
    content = insert_after(
        content,
        "    ari: Optional[ARIConfigurationResponse] = None\n",
        "    freeswitch: Optional[FreeswitchConfigurationResponse] = None\n",
        "telephony_config.py response field",
    )
    schema.write_text(content)

    for path in [providers_init, schema, *sorted(package.glob("*.py"))]:
        py_compile.compile(str(path), doraise=True)
    print("[ok] python syntax check passed")


if __name__ == "__main__":
    main()
