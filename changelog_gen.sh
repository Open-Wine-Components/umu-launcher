#!/bin/bash
export VERSION=$(git tag --sort=-v:refname | head -1)
export PREVIOUS_VERSION=$(git tag --sort=-v:refname | head -2 | awk '{split($0, tags, "\n")} END {print tags[1]}')
export CHANGES=$(git log --pretty="- %s" $VERSION...$PREVIOUS_VERSION)
printf "# 🎁 Release notes (\`$VERSION\`)\n\n## Changes\n$CHANGES\n\n## Metadata\n\`\`\`\nThis version -------- $VERSION\nPrevious version ---- $PREVIOUS_VERSION\nTotal commits ------- $(echo "$CHANGES" | wc -l)\n\`\`\`\n" > release_notes.md
