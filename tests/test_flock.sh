#!/usr/bin/env sh

#
# Ensure umu-launcher does not download its fetched resources more than once
# when multiple processes of itself are created
#

tmp1=$(mktemp)
tmp2=$(mktemp)

UMU_LOG=debug GAMEID=umu-0 "$HOME/.local/bin/umu-run" wineboot -u 2> "$tmp1" &
sleep 1
UMU_LOG=debug GAMEID=umu-0 "$HOME/.local/bin/umu-run" wineboot -u 2> "$tmp2" &
wait

grep "exited with wait status" "$tmp1" && grep -E "exited with wait status" "$tmp2"

# Ensure the 2nd proc didn't download the runtime
grep -E "\(latest\), please wait..." "$tmp2"
exit_code=$?
if "$exit_code" != 0; then
	exit 1
fi

# Ensure the 2nd proc didn't download Proton
grep "Downloading" "$tmp2"
exit_code=$?
if "$exit_code" != 0; then
	exit 1
fi

