#!/bin/sh
set -eu
target_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$target_dir/build/imx519-demo" "$@"
