#!/usr/bin/env sh

#
# Ensure umu-launcher does not download its fetched resources more than once
# when multiple processes of itself are created
#

tmp1=$(mktemp)
tmp2=$(mktemp)
downloads=$(mktemp)
trap 'rm -f "$tmp1" "$tmp2" "$downloads"' EXIT

UMU_LOG=debug GAMEID=umu-0 "$HOME/.local/bin/umu-run" wineboot -u 2> "$tmp1" &
sleep 1
UMU_LOG=debug GAMEID=umu-0 "$HOME/.local/bin/umu-run" wineboot -u 2> "$tmp2" &
wait

grep "exited with wait status" "$tmp1" && grep -E "exited with wait status" "$tmp2"

# Either process can win the install lock. Ensure no fetched resource was
# downloaded more than once across both processes.
grep "Downloading" "$tmp1" "$tmp2" | sed 's/^[^:]*://' > "$downloads"
if sort "$downloads" | uniq -d | grep .; then
	exit 1
fi
