#!/usr/bin/env bash
#
# murmuration/ui/replay/ is a committed build artifact of nictopia/.
# Rerun this script after any nictopia/src change to regenerate it.
# Requires Node 22.12+ (see nictopia/README.md).
#
set -euo pipefail

cd "$(dirname "$0")/.."

(cd nictopia && npm install && npm run build -- --base=/replay/)

rm -rf murmuration/ui/replay
cp -R nictopia/dist murmuration/ui/replay

echo "Done. Regenerated murmuration/ui/replay/ from nictopia/dist — remember to commit murmuration/ui/replay."
