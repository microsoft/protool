#!/usr/bin/env python3

"""Command line handler for protool."""

import argparse
import json
import sys
import re

import protool

PROV_TYPE_MAPPINGS = \
{"ios-dev": protool.ProvisioningType.IOS_DEVELOPMENT, \
  "appstore": protool.ProvisioningType.APP_STORE_DISTRIBUTION, \
  "enterprise": protool.ProvisioningType.ENTERPRISE_DISTRIBUTION, \
  "adhoc": protool.ProvisioningType.AD_HOC_DISTRIBUTION}

def _handle_diff(args: argparse.Namespace) -> int:
    """Handle the diff sub command."""

    if len(args.profiles) != 2:
        print("Expected 2 profiles for diff command")
        return 1

    try:
        print(protool.diff(args.profiles[0], args.profiles[1], ignore_keys=args.ignore, tool_override=args.tool))
    except Exception as ex:
        print(f"Could not diff: {ex}", file=sys.stderr)
        return 1

    return 0


def _handle_git_diff(args: argparse.Namespace) -> int:
    """Handle the gitdiff sub command."""

    try:
        print(protool.diff(args.git_args[1], args.git_args[4], ignore_keys=args.ignore, tool_override=args.tool))
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

    regular_types = [str, int, float]
    found_supported_type = False

    for regular_type in regular_types:
        if isinstance(value, regular_type):
            found_supported_type = True
            print(value)
            break

    if not found_supported_type:
        try:
            result = json.dumps(value)
        except Exception:
            print("Unable to serialize values. Please use the XML format instead.", file=sys.stderr)
            return 1

        print(result)

    return 0


def _handle_decode(args: argparse.Namespace) -> int:
    """Handle the decode sub command."""
    try:
        print(protool.decode(args.profile))
    except Exception as ex:
        print(f"Could not decode: {ex}", file=sys.stderr)
        return 1

    return 0

def _handle_search(args: argparse.Namespace) -> int:
    """Handle the search sub command."""
    try:
        prov_types_set = set()
        if "all" in args.profile_types:
            prov_types_set.update(PROV_TYPE_MAPPINGS.values())
        else:
            selected_prov_types = {PROV_TYPE_MAPPINGS[key] for key in PROV_TYPE_MAPPINGS if key in args.profile_types}
            prov_types_set.update(selected_prov_types)

        for profile in protool.profiles():
            app_prefix = profile.application_identifier_prefix[0]
            prefixed_app_id = profile.entitlements["application-identifier"]
            app_id_noprefix = re.sub(app_prefix + r"\.(.*)", r"\1", prefixed_app_id, count=1)

            if re.search(args.app_id, app_id_noprefix):
                if profile.profile_type in prov_types_set:
                    print(profile.file_path)
    except Exception as ex:
        print(f"Could not perform search: {ex}", file=sys.stderr)
        return 1

    return 0


def _handle_arguments() -> int:
    """Handle command line arguments and call the correct method."""

    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers()

    diff_parser = subparsers.add_parser('diff', help="Perform a diff between two profiles")

    diff_parser.add_argument(
        "-i",
        "--ignore",
        dest="ignore",
        action="store",
        nargs='+',
        default=None,
        help='A list of keys to ignore. e.g. --ignore TimeToLive UUID'
    )

    diff_parser.add_argument(
        "-t",
        "--tool",
        dest="tool",
        action="store",
        default=None,
        help='Specify a diff command to use. It should take two file paths as the final two arguments. Defaults to opendiff'  #pylint: disable=line-too-long
    )

    diff_parser.add_argument(
        "-p",
        "--profiles",
        dest="profiles",
        action="store",
        nargs=2,
        required=True,
        help='The two profiles to diff'
    )

    diff_parser.set_defaults(subcommand="diff")

    gitdiff_parser = subparsers.add_parser(
        'gitdiff',
        help="Perform a diff between two profiles with the git diff parameters"
    )

    gitdiff_parser.add_argument(
        "-i",
        "--ignore",
        dest="ignore",
        action="store",
        nargs='+',
        default=None,
        help='A list of keys to ignore. e.g. --ignore TimeToLive UUID'
    )

    gitdiff_parser.add_argument(
        "-t",
        "--tool",
        dest="tool",
        action="store",
        default=None,
        help='Specify a diff command to use. It should take two file paths as the final two arguments. Defaults to opendiff'  #pylint: disable=line-too-long
    )

    gitdiff_parser.add_argument(
        "-g",
        "--git-args",
        dest="git_args",
        action="store",
        nargs=7,
        required=True,
        help='The arguments from git'
    )

    gitdiff_parser.set_defaults(subcommand="gitdiff")

    read_parser = subparsers.add_parser('read', help="Read the value from a profile using the key specified command")

    read_parser.add_argument(
        "-p",
        "--profile",
        dest="profile",
        action="store",
        required=True,
        help='The profile to read the value from'
    )

    read_parser.add_argument(
        "-k",
        "--key",
        dest="key",
        action="store",
        required=True,
        help='The key to read the value for'
    )

    read_parser.set_defaults(subcommand="read")

    decode_parser = subparsers.add_parser(
        'decode',
        help="Decode a provisioning profile and display in a readable format"
    )

    decode_parser.add_argument(
        "-p",
        "--profile",
        dest="profile",
        action="store",
        required=True,
        help='The profile to read the value from'
    )

    decode_parser.set_defaults(subcommand="decode")

    search_parser = subparsers.add_parser('search', \
        help="Search for a .mobileprovision file matching a given description")

    search_parser.add_argument(
        "-i",
        "--appid",
        dest="app_id",
        action="store",
        help="The exact app bundle ID to search for"
    )

    prov_types = list(PROV_TYPE_MAPPINGS.keys()) + ["all"]

    search_parser.add_argument(
        "-t",
        "--type",
        dest="profile_types",
        action="store",
        required=False,
        help='Limits search to a provisioning profile type(s)',
        default="all",
        nargs="*",
        choices=prov_types
    )

    search_parser.set_defaults(subcommand="search")

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

    if args.subcommand == "search":
        return _handle_search(args)

    print("Unrecognized command")
    return 1

def run() -> int:
    """Entry point for poetry generated command line tool."""
    return _handle_arguments()

if __name__ == "__main__":
    sys.exit(_handle_arguments())
