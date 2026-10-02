#!/bin/sh
# gera ./build pro terraform zipar (deps pra linux x86_64 / py3.12)
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BUILD="$ROOT/build"

rm -rf "$BUILD"
mkdir -p "$BUILD"

pip install \
  --requirement "$ROOT/requirements.txt" \
  --target "$BUILD" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  --upgrade --quiet

cp -r "$ROOT/src/." "$BUILD/"
find "$BUILD" -type d -name "__pycache__" -prune -exec rm -rf {} +

# ca do rds pra conexão com ssl
curl -sSfL https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -o "$BUILD/rds-ca-bundle.pem"

echo "Build gerado em $BUILD"
