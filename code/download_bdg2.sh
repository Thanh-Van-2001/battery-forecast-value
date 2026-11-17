#!/bin/bash
# Download the three BDG2 files from GitHub LFS and verify them against the LFS pointer hashes.
# Atomic: each file is written to .part and renamed only after its sha256 matches.
set -u
D=${1:-data}
mkdir -p "$D"
BASE=https://media.githubusercontent.com/media/buds-lab/building-data-genome-project-2/master
fetch() {  # path sha256 name
  local out="$D/$3"
  if [ -f "$out" ] && echo "$2  $out" | sha256sum -c --status; then echo "$3 already OK"; return 0; fi
  for k in 1 2 3; do
    curl -sSL --retry 3 -m 1800 -o "$out.part" "$BASE/$1" && echo "$2  $out.part" | sha256sum -c --status && mv "$out.part" "$out" && echo "$3 OK" && return 0
    echo "$3 attempt $k failed"; sleep 10
  done
  echo "$3 FAILED"; return 1
}
fetch data/meters/cleaned/electricity_cleaned.csv b6ffc9b4dfcefe5c753594730a08ae822b0d50fec6815abb8f185591e6c630a3 electricity_cleaned.csv
fetch data/metadata/metadata.csv 992d0b29f24f96ad4332bc4dbb534b7bdd7dd2689aad093f94e93068ecddca02 metadata.csv
fetch data/weather/weather.csv a8189f1c6acdf3b9933a9e6354b8e7c1278cd56a7075929623a17565d44f04bd weather.csv
