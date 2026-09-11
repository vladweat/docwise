#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v npm &>/dev/null; then
  echo "ERROR: npm not found. Install Node.js 20+."
  exit 1
fi

# optionalDependencies (Next SWC, Tailwind lightningcss/oxide, Rollup, esbuild) пропускаются.
# Нативные gnu+musl бинарники — прямые deps: хост glibc, образ node:20-alpine (musl).
# Версии SWC = next; lightningcss/oxide = tailwindcss; rollup/esbuild = vitest/vite.
echo "Installing frontend dependencies..."
npm install --omit=optional --no-audit --no-fund

mkdir -p public
if [[ -f node_modules/pdfjs-dist/build/pdf.worker.min.mjs ]]; then
  cp node_modules/pdfjs-dist/build/pdf.worker.min.mjs public/pdf.worker.min.mjs
elif [[ -f node_modules/pdfjs-dist/build/pdf.worker.min.js ]]; then
  cp node_modules/pdfjs-dist/build/pdf.worker.min.js public/pdf.worker.min.js
fi

echo ""
echo "OK: frontend/node_modules ready"
echo "Next (offline): make up"
