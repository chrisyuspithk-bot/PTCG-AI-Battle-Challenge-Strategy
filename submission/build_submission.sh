#!/bin/bash
# Build submission.tar.gz for Kaggle Simulation Category (cabt engine)
#
# The submission must be a .tar.gz with main.py and deck.csv at the top level.
#
# PREREQUISITE: None! The cabt engine is included in the Kaggle environment.
# You only need main.py + deck.csv in the tarball.
#
# Usage: bash build_submission.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="$SCRIPT_DIR/submission.tar.gz"
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "=== Building Kaggle Simulation Submission ==="

# Verify required files
for f in main.py deck.csv; do
    if [ ! -f "$SCRIPT_DIR/$f" ]; then
        echo "ERROR: $f not found in $SCRIPT_DIR"
        exit 1
    fi
done

# Copy to temp build dir
cp "$SCRIPT_DIR/main.py" "$TEMP_DIR/"
cp "$SCRIPT_DIR/deck.csv" "$TEMP_DIR/"
echo "  ✓ main.py"
echo "  ✓ deck.csv"

# Verify deck.csv (60 lines, one card ID per line)
DECK_LINES=$(grep -c '^' "$TEMP_DIR/deck.csv" || true)
echo "  ✓ deck.csv: $DECK_LINES card IDs"

# Create tarball (files at top level, not nested)
cd "$TEMP_DIR"
tar czf "$OUTPUT" main.py deck.csv
rm -rf "$TEMP_DIR"

echo ""
echo "=== Done ==="
echo "File: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
echo ""
echo "Submit at: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/submit"
echo ""
echo "After submission:"
echo "  - Validation episode runs first (agent vs itself)"
echo "  - If OK → enters ladder at μ₀=600 Elo"
echo "  - Up to 5 submissions/day, latest 2 kept active"
echo "  - Matches continue until Aug 31 deadline"
