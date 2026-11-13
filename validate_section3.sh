#!/usr/bin/env bash
set -o pipefail
cd -- "$(dirname -- "$0")"

FAIL=0

check() {
  local label="$1"; shift
  if "$@"; then
    printf 'OK   | %s\n' "$label"
  else
    printf 'FAIL | %s\n' "$label"
    FAIL=$((FAIL + 1))
  fi
}

present() {
  local file="$1" pattern="$2"
  python3 - "$file" "$pattern" <<'PY'
import io, re, sys
path, pat = sys.argv[1], sys.argv[2]
text = io.open(path, encoding='utf-8').read()
print('FOUND' if re.search(pat, text) else 'ABSENT')
PY
}

absent() {
  local file="$1" pattern="$2"
  python3 - "$file" "$pattern" <<'PY'
import io, re, sys
path, pat = sys.argv[1], sys.argv[2]
text = io.open(path, encoding='utf-8').read()
print('ABSENT' if not re.search(pat, text) else 'FOUND')
PY
}

printf '=== deliverable existence and size ===\n'
for f in Section_3_Updated.md Section_3_Change_Report.md; do
  if [ -s "$f" ]; then
    printf 'OK   | %s present (%s bytes, %s lines)\n' \
      "$f" "$(wc -c < "$f")" "$(wc -l < "$f")"
  else
    printf 'FAIL | %s missing or empty\n' "$f"
    FAIL=$((FAIL + 1))
  fi
done

printf '\n=== readback Section_3_Updated.md opening lines ===\n'
sed -n '1,12p' Section_3_Updated.md

printf '\n=== malformed label-map notation must be absent from updated file ===\n'
result=$(absent Section_3_Updated.md 'a\$\s*\\mathrm\{label\}\\\_{map}')
if [ "$result" = "ABSENT" ]; then printf 'OK   | malformed notation absent from updated file\n'; else printf 'FAIL | malformed notation still present in updated file\n'; FAIL=$((FAIL + 1)); fi

printf '\n=== f_map notation present and used for label map ===\n'
result=$(present Section_3_Updated.md 'f_\{\\mathrm\{map\}\}')
if [ "$result" = "FOUND" ]; then printf 'OK   | f_{\\mathrm{map}} found in updated file\n'; else printf 'FAIL | f_{\\mathrm{map}} not found in updated file\n'; FAIL=$((FAIL + 1)); fi

printf '\n=== lower-bit preservation constraint explicitly present ===\n'
result=$(present Section_3_Updated.md '\\\\hat\{v\} \\\\bmod 2\^\{8-b\} = \\\\tilde\{v\} \\\\bmod 2\^\{8-b\}')
if [ "$result" = "FOUND" ]; then printf 'OK   | lower-bit preservation equation present\n'; else printf 'FAIL | lower-bit preservation equation missing\n'; FAIL=$((FAIL + 1)); fi

printf '\n=== BPP algebraic identity wording present ===\n'
result=$(present Section_3_Updated.md 'algebraically identical')
if [ "$result" = "FOUND" ]; then printf 'OK   | BPP identity wording present\n'; else printf 'FAIL | BPP identity wording missing\n'; FAIL=$((FAIL + 1)); fi

printf '\n=== full-image recovery claim qualified with verification scope ===\n'
result=$(present Section_3_Updated.md 'repro_receiver_payload_len\.py')
if [ "$result" = "FOUND" ]; then printf 'OK   | verification script reference present\n'; else printf 'FAIL | verification script reference missing\n'; FAIL=$((FAIL + 1)); fi

printf '\n=== LaTeX equation delimiters balanced ===\n'
b=$(grep -c '\\begin{equation}' Section_3_Updated.md || true)
e=$(grep -c '\\end{equation}' Section_3_Updated.md || true)
if [ "$b" = "$e" ] && [ "$b" -gt 0 ]; then printf 'OK   | begin=%s end=%s\n' "$b" "$e"; else printf 'FAIL | begin=%s end=%s\n' "$b" "$e"; FAIL=$((FAIL + 1)); fi

printf '\n=== subsection heading count unchanged ===\n'
og=$(grep -cE '^## [0-9]+\.[0-9]+\.' sec3_deliverable_b_section3_manuscript.md || true)
ng=$(grep -cE '^## [0-9]+\.[0-9]+\.' Section_3_Updated.md || true)
if [ "$og" = "$ng" ]; then printf 'OK   | subsection headings original=%s updated=%s\n' "$og" "$ng"; else printf 'FAIL | subsection headings original=%s updated=%s\n' "$og" "$ng"; FAIL=$((FAIL + 1)); fi

printf '\n=== change report references updated file ===\n'
result=$(present Section_3_Change_Report.md 'Section_3_Updated\.md')
if [ "$result" = "FOUND" ]; then printf 'OK   | change report mentions updated file\n'; else printf 'WARN | change report does not mention updated file\n'; fi

printf '\nDONE\n'
exit "$FAIL"
