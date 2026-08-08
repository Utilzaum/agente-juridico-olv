#!/bin/bash
cd "$(dirname "$0")/leis_html" || exit 1
for f in *.html *.htm; do
  [ -f "$f" ] || continue
  if iconv -f UTF-8 -t UTF-8 "$f" >/dev/null 2>&1; then
    echo "⏭️  $f já é UTF-8"
  else
    iconv -f ISO-8859-1 -t UTF-8 "$f" -o /tmp/conv.tmp && mv /tmp/conv.tmp "$f"
    echo "✅ $f convertido (acentos restaurados)"
  fi
done
