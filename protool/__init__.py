#!/usr/bin/env python3

"""A utility for dealing with provisioning profiles"""

import copy
import os
import shutil
import subprocess
import sys
import tempfile

import biplist

__version__ = '0.2'


class ProvisioningProfile(object):
    """Represents a provisioning profile."""

    def __init__(self, file_path):
        self.file_path = os.path.abspath(file_path)
        self.file_name = os.path.basename(self.file_path)
        self.xml = None
        self._contents = None
        self._load_xml()
        self._load_contents_dict()
        self._parse_contents()

    def contents(self):
        """Return a copy of the content dict."""
        return copy.deepcopy(self._contents)

    def _parse_contents(self):
        """Parse the contents of the profile."""
        self.app_id_name = self._contents.get("AppIDName")
        self.application_identifier_prefix = self._contents.get("ApplicationIdentifierPrefix")
        self.creation_date = self._contents.get("CreationDate")
        self.platform = self._contents.get("Platform")
        self.developer_certificates = self._contents.get("DeveloperCertificates")
        self.entitlements = self._contents.get("Entitlements")
        self.expiration_date = self._contents.get("ExpirationDate")
        self.name = self._contents.get("Name")
        self.team_identifier = self._contents.get("TeamIdentifier")
        self.team_name = self._contents.get("TeamName")
        self.time_to_live = self._contents.get("TimeToLive")
        self.uuid = self._contents.get("UUID")
        self.version = self._contents.get("Version")

    def _load_xml(self):
        """Load the XML contents of a provisioning profile."""
        security_cmd = 'security cms -D -i "%s" 2> /dev/null' % self.file_path
        self.xml = subprocess.check_output(
            security_cmd,
            universal_newlines=True,
            shell=True
        ).strip()

    def _load_contents_dict(self):
        """Return the contents of a provisioning profile."""
        self._contents = biplist.readPlistFromString(self.xml)


def diff(a_path, b_path, ignore_keys=None, tool_override=None):
    """Diff two provisioning profiles."""

    if tool_override is None:
        diff_tool = "opendiff"
    else:
        diff_tool = tool_override

    profile_a = ProvisioningProfile(a_path)
    profile_b = ProvisioningProfile(b_path)

    if ignore_keys is None:
        a_xml = profile_a.xml
        b_xml = profile_b.xml
    else:
        a_dict = profile_a.contents()
        b_dict = profile_b.contents()

        for key in ignore_keys:
            try:
                del a_dict[key]
            except:
                pass
            try:
                del b_dict[key]
            except:
                pass

        a_xml = biplist.writePlistToString(a_dict, binary=False)
        b_xml = biplist.writePlistToString(b_dict, binary=False)

    temp_dir = tempfile.mkdtemp()

    a_temp_path = os.path.join(temp_dir, profile_a.file_name)
    b_temp_path = os.path.join(temp_dir, profile_b.file_name)

    with open(a_temp_path, 'w') as temp_profile:
        temp_profile.write(a_xml)

    with open(b_temp_path, 'w') as temp_profile:
        temp_profile.write(b_xml)

    # We deliberately don't wrap the tool so that arguments work as well
    diff_command = '%s "%s" "%s"' % (diff_tool, a_temp_path, b_temp_path)

    try:
        diff_contents = subprocess.check_output(
            diff_command,
            universal_newlines=True,
            shell=True
        ).strip()
    except subprocess.CalledProcessError as ex:
        # Diff tools usually return a non-0 exit code if there are differences,
        # so we just swallow this error
        diff_contents = ex.output

    # Cleanup
    shutil.rmtree(temp_dir)

    return diff_contents


def value_for_key(profile_path, key):
    """Return the value for a given key"""

    profile = ProvisioningProfile(profile_path)

    try:
        value = profile.contents()[key]
        return value
    except KeyError:
        return None


def decode(profile_path, xml=True):
    """Decode a profile, returning as a dictionary if xml is set to False."""

    profile = ProvisioningProfile(profile_path)

    if xml:
        return profile.xml
    else:
        return profile.contents()


if __name__ == "__main__":
    print("This should only be used as a module.")
    sys.exit(1)
