#!/usr/bin/env bash
# Setup symlinks from module tests/ dirs to tests_suite submodule.
# Usage: ./scripts/setup_test_symlinks.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODULES=("connect" "connect_twilio" "connect_freeswitch")
SUBMODULE_DIR="$REPO_ROOT/tests_suite"

# Check if submodule is initialized
if [ ! -f "$SUBMODULE_DIR/.git" ] && [ ! -d "$SUBMODULE_DIR/.git" ]; then
    echo "⚠  tests_suite submodule not initialized."
    echo "   Run: git submodule update --init"
    echo ""
    echo "   Without the test suite, modules operate in Unprotected Mode."
    echo "   Purchase access at https://github.com/oduist/connect_addons_tests"
    exit 1
fi

echo "Setting up test symlinks..."
echo ""

for module in "${MODULES[@]}"; do
    link="$REPO_ROOT/$module/tests"
    target="../tests_suite/$module/tests"

    # Remove existing (broken symlink, directory, or file)
    if [ -L "$link" ] || [ -e "$link" ]; then
        rm -rf "$link"
    fi

    ln -sf "$target" "$link"
    echo "  ✓ $module/tests → $target"
done

echo ""
echo "✅ Safe Mode activated. Test suite is linked."
echo "   Run tests with: oduflow run_odoo_tests <module>"
