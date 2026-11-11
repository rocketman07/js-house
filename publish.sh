#!/bin/zsh
# Publish the J+S House web viewer: commit the current js-house.glb / index.html and push to GitHub.
# GitHub Pages republishes the site about a minute later.
# Run export_glb.py in Rhino first (it writes js-house.glb into this folder), then:  ./publish.sh "message"
set -e
cd "$(dirname "$0")"
MSG=${1:-"Update model export $(date '+%Y-%m-%d %H:%M')"}
# cache-bust: browsers keep js-house.glb for a while, so every publish points the page at a new ?v= stamp
STAMP=$(date '+%Y%m%d%H%M%S')
sed -i '' -E 's|const MODEL_URL = "js-house\.glb[^"]*";|const MODEL_URL = "js-house.glb?v='"$STAMP"'";|' index.html
git add js-house.glb index.html README.md export_glb.py publish.sh apps-script
if git diff --cached --quiet; then
  echo "Nothing changed since the last publish."
  exit 0
fi
git commit -q -m "$MSG"
git push -q origin main
echo "Published. The live site updates in about a minute."
