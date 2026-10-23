#!/usr/bin/env bash
#
# Report on an Antora build log in Markdown.
#
# Counts the FATAL, ERROR, and WARN entries of the log, lists the missing
# attributes, and shows each problem with its file and source lines. The
# log uses --log-format=pretty: "[time] LEVEL (logger): message", followed
# by indented lines.
#
# Exits 0 when the build is clean: make succeeded, the log exists, and it
# has no FATAL, ERROR, or missing attribute entries. Other warnings are
# reported but do not fail the check. Exits 1 otherwise.
#
# With an attention file, it also writes one Markdown bullet for each problem
# that fails the check, for the top of the sync pull request.
#
# Usage: scripts/build-report.sh <build log> <make exit status> [make output] [attention file]

set -euo pipefail

log="${1:?build log required}"
status="${2:?make exit status required}"
make_out="${3:-}"
attention="${4:-}"
max_lines=60
max_items=20
root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/"

# Print the entries whose first line contains the pattern, with their
# indented continuation lines, and paths relative to the repository.
entries() {
  awk -v pat="$1" '
    /^\[/ { show = index($0, pat) > 0 }
    show
  ' "$log" | relative | head -n "$max_lines"
}

relative() {
  awk -v root="$root" '{ while ((i = index($0, root)) > 0) $0 = substr($0, 1, i - 1) substr($0, i + length(root)); print }'
}

count() {
  grep -cF "$1" "$log" || true
}

block() {
  local title="$1" text="$2"
  [ -n "$text" ] || return 0
  echo
  echo "<details><summary>$title</summary>"
  echo
  echo '```'
  echo "$text"
  echo '```'
  echo
  echo "</details>"
}

# Write the attention bullets: one for each FATAL and ERROR entry, with its
# file, and one for each missing attribute name.
write_attention() {
  [ -n "$attention" ] || return 0
  {
    if [ ! -s "$log" ]; then
      echo "- **Build:** the build log is missing or empty, so the build cannot be checked. See **Build**."
      return
    fi
    if [ "$status" -ne 0 ]; then
      echo "- **Build:** \`make product-local\` exited with status $status. See **Build**."
    fi
    {
      awk '
        function flush() { if (msg != "") { print "- **Build:** " msg (file != "" ? " (`" file "`)" : ""); msg = ""; file = "" } }
        /^\[/ {
          flush()
          if (match($0, /\] (FATAL|ERROR) \([^)]*\): /)) {
            level = substr($0, RSTART + 2, RLENGTH - 2); sub(/ \(.*/, "", level)
            msg = level " " substr($0, RSTART + RLENGTH)
          }
          next
        }
        msg != "" && /^ +file: / { file = $0; sub(/^ +file: /, "", file) }
        END { flush() }
      ' "$log" | relative
      grep -F '] WARN (' "$log" | grep -oE 'missing attribute: [A-Za-z0-9_-]+' |
        sed 's/missing attribute: //' | sort | uniq -c | sort -rn |
        awk '{ printf "- **Build:** missing attribute `%s` (%d %s)\n", $2, $1, ($1 == 1 ? "entry" : "entries") }' || true
    } > "$attention.all"
    head -n "$max_items" "$attention.all"
    total=$(wc -l < "$attention.all")
    if [ "$total" -gt "$max_items" ]; then
      echo "- **Build:** ... and $((total - max_items)) more. See **Build**."
    fi
    rm -f "$attention.all"
  } > "$attention"
}

write_attention

echo "## Build"
echo

if [ ! -s "$log" ]; then
  echo "\`make product-local\` exit status: $status. The build log \`$log\` is missing or empty, so the build cannot be checked."
  if [ -n "$make_out" ] && [ -s "$make_out" ]; then
    block "Last lines of the make output" "$(tail -n 30 "$make_out")"
  fi
  exit 1
fi

fatal=$(count '] FATAL (')
errors=$(count '] ERROR (')
warns=$(count '] WARN (')
missing=$(grep -F '] WARN (' "$log" | grep -cF 'missing attribute' || true)
other=$((warns - missing))

echo "\`make product-local\` exit status: $status."
echo
echo "| Level | Entries |"
echo "|---|---|"
echo "| FATAL | $fatal |"
echo "| ERROR | $errors |"
echo "| WARN: missing attribute | $missing |"
echo "| WARN: other | $other |"

if [ "$missing" -gt 0 ]; then
  echo
  echo "Missing attributes:"
  echo
  grep -F '] WARN (' "$log" | grep -oE 'missing attribute: [A-Za-z0-9_-]+' |
    sed 's/missing attribute: //' | sort | uniq -c | sort -rn |
    awk '{ printf "- `%s` (%d)\n", $2, $1 }'
fi

block "FATAL entries" "$(entries '] FATAL (')"
block "ERROR entries" "$(entries '] ERROR (')"
block "Missing attribute entries" "$(entries 'missing attribute')"
if [ "$other" -gt 0 ]; then
  block "Other warnings" "$(awk '
    /^\[/ { show = index($0, "] WARN (") > 0 && index($0, "missing attribute") == 0 }
    show
  ' "$log" | relative | head -n "$max_lines")"
fi

if [ "$status" -ne 0 ] && [ -n "$make_out" ] && [ -s "$make_out" ]; then
  block "Last lines of the make output" "$(tail -n 30 "$make_out")"
fi

[ "$status" -eq 0 ] && [ "$fatal" -eq 0 ] && [ "$errors" -eq 0 ] && [ "$missing" -eq 0 ]
