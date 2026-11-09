#!/bin/sh
# Truth pin: fail CI when tracked text says something known to be wrong.
# POSIX sh, needs only git and grep.
set -u
cd "$(dirname "$0")/.." || exit 1

fail=0
FILES=$(git ls-files '*.py' '*.md' '*.toml' '*.yml' '*.yaml' '*.sh' | grep -v '^scripts/truthcheck\.sh$' | grep -v '^tests/spec/')
[ -n "$FILES" ] || exit 0

check() {
    if echo "$FILES" | xargs grep -inE -- "$1" 2>/dev/null; then
        echo "truthcheck: FAIL, $2" >&2
        fail=1
    fi
}

check 'livetennisapi\.com/docs' 'the docs live at https://docs.livetennisapi.com'
check 'bensynapse' 'a personal handle in an org repo'
check 'sub-?second|guaranteed|99\.9 ?%' 'a claim this package cannot back'

[ "$fail" -eq 0 ] && echo "truthcheck: OK"
exit "$fail"
