#!/bin/sh
# Build one test file with the sources, run it, and (with a second argument) write LCOV coverage there.
set -e
out=$(mktemp -d)
g++ --coverage -O0 -Isrc -o "$out/t" src/*.cpp "$1"
cd "$out" && ./t
[ -z "$2" ] || gcovr --root "$OLDPWD" --object-directory "$out" --lcov "$2/lcov.info" "$out" >/dev/null
