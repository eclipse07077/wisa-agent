#!/usr/bin/env bash
set -euo pipefail

output=${1:?}
gdown=${2:-gdown}
mkdir -p "$output"

"$gdown" --continue 1cEdDdmDACkeTmC04vUwW8WXqn36t4DE4 \
  -O "$output/ta1-clearscope-e3-official-1.json.tar.gz"
"$gdown" --continue 11bVukedxRn8lVPmbBD2S6juUlqL4cI6b \
  -O "$output/ta1-clearscope-e3-official-2.json.tar.gz"
"$gdown" --continue 1z1KtBvS-XBwCt3DlkI6yS1UO7_1sVvB6 \
  -O "$output/ta1-clearscope-e3-official.json.tar.gz"
