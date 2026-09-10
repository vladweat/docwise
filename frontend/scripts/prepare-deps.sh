#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v npm &>/dev/null; then
  echo "ERROR: npm not found. Install Node.js 20+."
  exit 1
fi

# optionalDependencies Next (SWC) пропускаются; бинарники SWC стоят прямыми deps
# в package.json и должны совпадать с версией next (иначе disablePageConfig / mismatch).
echo "Installing frontend dependencies..."
npm install --omit=optional --no-audit --no-fund

mkdir -p public
if [[ -f node_modules/pdfjs-dist/build/pdf.worker.min.js ]]; then
  cp node_modules/pdfjs-dist/build/pdf.worker.min.js public/pdf.worker.min.js
fi

echo ""
echo "OK: frontend/node_modules ready"
echo "Next (offline): make up"
