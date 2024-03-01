#!/usr/bin/env bash

set -eu

# Output helpers
COLOR_ERR=""
COLOR_STAT=""
COLOR_INFO=""
COLOR_CMD=""
COLOR_CLEAR=""
if [[ $(tput colors 2>/dev/null || echo 0) -gt 0 ]]; then
  COLOR_ERR=$'\e[31;1m'
  COLOR_STAT=$'\e[32;1m'
  COLOR_INFO=$'\e[30;1m'
  COLOR_CMD=$'\e[93;1m'
  COLOR_CLEAR=$'\e[0m'
fi

sh_quote() {
        local quoted
        quoted="$(printf '%q ' "$@")"; [[ $# -eq 0 ]] || echo "${quoted:0:-1}";
}
err()      { echo >&2 "${COLOR_ERR}!!${COLOR_CLEAR} $*"; }
stat()     { echo >&2 "${COLOR_STAT}::${COLOR_CLEAR} $*"; }
info()     { echo >&2 "${COLOR_INFO}::${COLOR_CLEAR} $*"; }
showcmd()  { echo >&2 "+ ${COLOR_CMD}$(sh_quote "$@")${COLOR_CLEAR}"; }
die()      { err "$@"; exit 1; }
finish()   { stat "$@"; exit 0; }
cmd()      { showcmd "$@"; "$@"; }


#
# Configure
#

THIS_COMMAND="$0 $*" # For printing, not evaling
MAKEFILE="./Makefile"

# This is not rigorous.  Do not use this for untrusted input.  Do not.  If you need a version of
# this for untrusted input, rethink the path that got you here.
function escape_for_make() {
  local escape="$1"
  escape="${escape//\\/\\\\}" #  '\' -> '\\'
  escape="${escape//#/\\#}"   #  '#' -> '\#'
  escape="${escape//\$/\$\$}" #  '$' -> '$$'
  escape="${escape// /\\ }"   #  ' ' -> '\ '
  echo "$escape"
}

function configure() {
  ## Checks before writing config
  if [[ -n "$arg_user_install" ]]; then
      arg_prefix="$HOME/.local"
  fi

  if [[ $arg_prefix != $(realpath "$arg_prefix") ]]; then
    die "PREFIX needs to be an absolute path"
  fi

  ## Write out config
  [[ ! -e "$MAKEFILE" ]] || rm "$MAKEFILE"

  {
    # Config
    echo "# Generated by: $THIS_COMMAND"
    echo ""
    if [[ -n "$arg_user_install" ]]; then
      echo "USERINSTALL     := xtrue"
    fi

    # Prefix was specified, baking it into the Makefile
    if [[ -n $arg_prefix ]]; then
      echo "PREFIX          := $(escape_for_make "$arg_prefix")"
    fi

    # Include base
    echo ""
    echo "include Makefile.in"
  } >> "$MAKEFILE"

  stat "Created $MAKEFILE, now run \"make\" to build."
}

#
# Parse arguments
#

arg_prefix=""
arg_user_install=""
arg_help=""
invalid_args=""
function parse_args() {
  local arg;
  local val;
  local val_used;
  local val_passed;
  if [[ $# -eq 0 ]]; then
    return 1
  fi
  while [[ $# -gt 0 ]]; do
    arg="$1"
    val=''
    val_used=''
    val_passed=''
    if [[ -z $arg ]]; then # Sanity
      err "Unexpected empty argument"
      return 1
    elif [[ ${arg:0:2} != '--' ]]; then
      err "Unexpected positional argument ($1)"
      return 1
    fi

    # Looks like an argument does it have a --foo=bar value?
    if [[ ${arg%=*} != "$arg" ]]; then
      val="${arg#*=}"
      arg="${arg%=*}"
      val_passed=1
    else
      # Otherwise for args that want a value, assume "--arg val" form
      val="${2:-}"
    fi

    # The args
    if [[ $arg = --help || $arg = --usage ]]; then
      arg_help=1
    elif [[ $arg = --prefix ]]; then
      if [[ -n $arg_user_install ]]; then
        die "--prefix cannot be used with --user-install"
      fi
      arg_prefix="$val"
      val_used=1
    elif [[ $arg = --user-install ]]; then
      if [[ -n $arg_prefix ]]; then
        die "--user-install cannot be used with --prefix"
      fi
      arg_user_install="1"
    else
      err "Unrecognized option $arg"
      return 1
    fi

    # Check if this arg used the value and shouldn't have or vice-versa
    if [[ -n $val_used && -z $val_passed ]]; then
      # "--arg val" form, used $2 as the value.

      # Don't allow this if it looked like "--arg --val"
      if [[ ${val#--} != "$val" ]]; then
        err "Ambiguous format for argument with value \"$arg $val\""
        err "  (use $arg=$val or $arg='' $val)"
        return 1
      fi

      # Error if this was the last positional argument but expected $val
      if [[ $# -le 1 ]]; then
        err "$arg takes a parameter, but none given"
        return 1
      fi

      shift # consume val
    elif [[ -z $val_used && -n $val_passed ]]; then
      # Didn't use a value, but passed in --arg=val form
      err "$arg does not take a parameter"
      return 1
    fi

    shift # consume arg
  done
}

usage() {
  "$1" "Usage: $0 { --prefix=path }"
  "$1" "  Generate a Makefile for building ULWGL"
  "$1" ""
  "$1" "  Options"
  "$1" "    --help"
  "$1" "    --usage           Show this help text and exit"
  "$1" ""
  "$1" "    --prefix=PREFIX   Install architecture-independent files in PREFIX"
  "$1" "                      [/usr]"
  "$1" "    --user-install    Install under user-only location. Incompatible with --prefix"
  "$1" "                      [$HOME/.local]"
  "$1" ""
  exit 1;
}

parse_args "$@" || usage err
[[ -z $arg_help ]] || usage info

configure
