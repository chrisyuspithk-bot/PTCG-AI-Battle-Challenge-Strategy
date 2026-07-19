#!/bin/bash
# Build submission.tar.gz for Kaggle Simulation Category
#
# PREREQUISITE: Download cg/ engine bindings from Kaggle
#   1. Go to https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/data
#   2. Download the sample submission / SDK
#   3. Place the cg/ directory inside this submission/ folder
#
# Then run: bash build_submission.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
OUTPUT="$SCRIPT_DIR/submission.tar.gz"

echo "=== Building Kaggle Submission ==="

rm -rf "$BUILD_DIR" "$OUTPUT"
mkdir -p "$BUILD_DIR"

# Required files
for f in main.py deck.csv; do
    if [ ! -f "$SCRIPT_DIR/$f" ]; then
        echo "ERROR: $f not found in $SCRIPT_DIR"
        exit 1
    fi
    cp "$SCRIPT_DIR/$f" "$BUILD_DIR/"
    echo "  ✓ $f"
done

# cg engine bindings (required)
if [ -d "$SCRIPT_DIR/cg" ]; then
    cp -r "$SCRIPT_DIR/cg" "$BUILD_DIR/"
    echo "  ✓ cg/ engine bindings"
else
    echo ""
    echo "  ✗ ERROR: cg/ directory not found!"
    echo "    Download it from Kaggle:"
    echo "    https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/data"
    echo "    Then place cg/ in: $SCRIPT_DIR/"
    exit 1
fi

# Create tarball
cd "$BUILD_DIR"
tar czf "$OUTPUT" --owner=0 --group=0 .

echo ""
echo "=== Done ==="
echo "File: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
echo ""
echo "Submit at: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/submit"
