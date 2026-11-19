#!/bin/sh
# Today Board - start (macOS / Linux). Works from any folder: sh start.sh
cd "$(dirname "$0")" || exit 1
PY=""
for c in python3 python; do
  if "$c" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3.8+ was not found. Install it from https://www.python.org/downloads/ and run this again."
  echo "You can still LOOK at the board without Python: open board.html."
  exit 1
fi
[ -f board-data.json ] || "$PY" tools/board.py init
exec "$PY" tools/board.py serve --open
