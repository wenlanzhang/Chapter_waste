#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p Figure/workflow
snakemake --snakefile "$ROOT/Snakefile" --configfile "$ROOT/workflow/config.yaml" \
  --cores 1 --rulegraph all \
  | dot -Tpdf > Figure/workflow/spatial_rulegraph.pdf
echo "Wrote Figure/workflow/spatial_rulegraph.pdf"
