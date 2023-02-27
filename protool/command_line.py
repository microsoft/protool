#!/usr/bin/env python3

"""Command line handler for protool."""

import argparse
from datetime import datetime
import json
import os
import sys

try:
    import protool
except ImportError:
    # Insert the package into the PATH
    sys.path.insert(
        0, os.path.abspath(os.path.join(os.path.abspath(__file__), "..", ".."))
    )
    import protool


def _handle_diff(args: argparse.Namespace) -> int:
    """Handle the diff sub command."""

    if len(args.profiles) != 2:
        print("Expected 2 profiles for diff command")
        return 1

    try:
        print(
            protool.diff(
                args.profiles[0],
                args.profiles[1],
                sort_keys=not args.keep_original_order,
                ignore_keys=args.ignore,
                tool_override=args.tool,
            )
        )
    except Exception as ex:
        print(f"Could not diff: {ex}", file=sys.stderr)
        return 1

    return 0


def _handle_git_diff(args: argparse.Namespace) -> int:
    """Handle the gitdiff sub command."""

    try:
        print(
            protool.diff(
                args.git_args[1],
                args.git_args[4],
                sort_keys=not args.keep_original_order,
                ignore_keys=args.ignore,
                tool_override=args.tool,
            )
        )
    except Exception as ex:
        print(f"Could not diff: {ex}", file=sys.stderr)
        return 1

    return 0


def _handle_read(args: argparse.Namespace) -> int:
    """Handle the read sub command."""

    try:
        value = protool.value_for_key(args.profile, args.key)
    except Exception as ex:
        print(f"Could not read file: {ex}", file=sys.stderr)
        return 1

    if type(value) in [str, int, float]:
        print(value)
        return 0

    if isinstance(value, datetime):
        print(value.isoformat())
        return 0

    try:
        result = json.dumps(value)
        print(result)
        return 0
    except Exception as ex:
        print(
            f"Unable to serialize values: {ex}",
            file=sys.stderr,
        )
        return 1


def _handle_decode(args: argparse.Namespace) -> int:
    """Handle the decode sub command."""
    try:
        print(protool.decode(args.profile))
    except Exception as ex:
        print(f"Could not decode: {ex}", file=sys.stderr)
        return 1

    return 0


def _handle_arguments() -> int:
    """Handle command line arguments and call the correct method."""

    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers()

    diff_parser = subparsers.add_parser(
        "diff", help="Perform a diff between two profiles"
    )

    diff_parser.add_argument(
        "-i",
        "--ignore",
        dest="ignore",
        action="store",
        nargs="+",
        default=None,
        help="A list of keys to ignore. e.g. --ignore TimeToLive UUID",
    )

    diff_parser.add_argument(
        "-t",
        "--tool",
        dest="tool",
        action="store",
        default=None,
        help="Specify a diff command to use. It should take two file paths as the final two arguments. Defaults to opendiff",  # pylint: disable=line-too-long
    )

    diff_parser.add_argument(
        "-p",
        "--profiles",
        dest="profiles",
        action="store",
        nargs=2,
        required=True,
        help="The two profiles to diff",
    )

    diff_parser.add_argument(
        "-k",
        "--keep-original-order",
        dest="keep_original_order",
        action="store_true",
        required=False,
        default=False,
        help="Set to avoid sorting keys for diff operations",
    )

    diff_parser.set_defaults(subcommand="diff")

    gitdiff_parser = subparsers.add_parser(
        "gitdiff",
        help="Perform a diff between two profiles with the git diff parameters",
    )

    gitdiff_parser.add_argument(
        "-i",
        "--ignore",
        dest="ignore",
        action="store",
        nargs="+",
        default=None,
        help="A list of keys to ignore. e.g. --ignore TimeToLive UUID",
    )

    gitdiff_parser.add_argument(
        "-t",
        "--tool",
        dest="tool",
        action="store",
        default=None,
        help="Specify a diff command to use. It should take two file paths as the final two arguments. Defaults to opendiff",  # pylint: disable=line-too-long
    )

    gitdiff_parser.add_argument(
        "-g",
        "--git-args",
        dest="git_args",
        action="store",
        nargs=7,
        required=True,
        help="The arguments from git",
    )

    gitdiff_parser.set_defaults(subcommand="gitdiff")

    read_parser = subparsers.add_parser(
        "read", help="Read the value from a profile using the key specified command"
    )

    read_parser.add_argument(
        "-p",
        "--profile",
        dest="profile",
        action="store",
        required=True,
        help="The profile to read the value from",
    )

    read_parser.add_argument(
        "-k",
        "--key",
        dest="key",
        action="store",
        required=True,
        help="The key to read the value for",
    )

    read_parser.set_defaults(subcommand="read")

    decode_parser = subparsers.add_parser(
        "decode", help="Decode a provisioning profile and display in a readable format"
    )

    decode_parser.add_argument(
        "-p",
        "--profile",
        dest="profile",
        action="store",
        required=True,
        help="The profile to read the value from",
    )

    decode_parser.set_defaults(subcommand="decode")

    args = parser.parse_args()

    try:
        _ = args.subcommand
    except Exception:
        parser.print_help()
        return 1

    if args.subcommand == "diff":
        return _handle_diff(args)

    if args.subcommand == "gitdiff":
        return _handle_git_diff(args)

    if args.subcommand == "read":
        return _handle_read(args)

    if args.subcommand == "decode":
        return _handle_decode(args)

    print("Unrecognized command")
    return 1


def run() -> int:
    """Entry point for poetry generated command line tool."""
    return _handle_arguments()


if __name__ == "__main__":
    sys.exit(_handle_arguments())
