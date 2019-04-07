#!/usr/bin/env python3

"""A utility for dealing with provisioning profiles"""

from enum import Enum

import copy
import datetime
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional
from OpenSSL.crypto import FILETYPE_ASN1, load_certificate, x509


class ProvisioningType(Enum):
    """Enum representing the type of provisioning profile."""
    IOS_DEVELOPMENT = 1
    APP_STORE_DISTRIBUTION = 3
    AD_HOC_DISTRIBUTION = 5
    ENTERPRISE_DISTRIBUTION = 7


class Certificate:
    """Represents a certificate attached to a provisioning profile. Currently wraps PyOpenSSL x509 objects.
    Review https://pyopenssl.org/en/stable/api/crypto.html#x509-objects to make use of additional functionality.
    """
    x509: x509

    def __init__ (self, cert_body_string: str):
        self.x509 = load_certificate(FILETYPE_ASN1, cert_body_string)

    @property 
    def sha1(self) -> str:
        """The certificates sha1 hash."""
        return self.x509.digest('sha1').decode().replace(":", "")

    @property
    def is_expired(self) -> bool:
        """Returns True if the certificate has expired, False if not expired."""
        return self.x509.has_expired()


#pylint: disable=too-many-instance-attributes
class ProvisioningProfile:
    """Represents a provisioning profile."""

    file_path: str
    file_name: str
    xml: str
    _contents: Dict[str, Any]

    app_id_name: Optional[str]
    application_identifier_prefix: Optional[str]
    creation_date: Optional[datetime.datetime]
    platform: Optional[List[str]]
    entitlements: Dict[str, Any]
    expiration_date: Optional[datetime.datetime]
    name: Optional[str]
    team_identifier: Optional[List[str]]
    team_name: Optional[str]
    time_to_live: Optional[int]
    uuid: Optional[str]
    version: Optional[int]
    provisioned_devices: Optional[List[str]]
    provisions_all_devices: Optional[bool]

    @property
    def profile_type(self) -> ProvisioningType:
        """Determine the profile type from the various values in the profile."""
        if self.provisions_all_devices:
            return ProvisioningType.ENTERPRISE_DISTRIBUTION

        if not self.entitlements.get("get-task-allow") and self.provisioned_devices:
            return ProvisioningType.AD_HOC_DISTRIBUTION

        if not self.entitlements.get("get-task-allow") and not self.provisioned_devices:
            return ProvisioningType.APP_STORE_DISTRIBUTION

        if self.entitlements.get("get-task-allow") and self.provisioned_devices:
            return ProvisioningType.IOS_DEVELOPMENT

        raise Exception("Unable to determine provisioning profile type")

    @property
    def developer_certificates(self) -> [Certificate]:
        """Returns developer certificates as a list of PyOpenSSL X509""" 
        dev_certs = []
        for item in self._contents.get("DeveloperCertificates"):
            try:
                certificate = Certificate(item)
                dev_certs.append(certificate)
            except Exception as cert_exception:
                print(f"Could not load certificate due to an error: {cert_exception}")

        return dev_certs

    def __init__(self, file_path: str) -> None:
        self.file_path = os.path.abspath(file_path)
        self.file_name = os.path.basename(self.file_path)
        self.load_from_disk()

    def load_from_disk(self) -> None:
        """Load the provisioning profile details from disk and parse them."""
        self.xml = self._get_xml()
        self._contents = plistlib.loads(self.xml.encode())
        self._parse_contents()

    def contents(self) -> Dict[str, Any]:
        """Return a copy of the content dict."""
        return copy.deepcopy(self._contents)

    def _parse_contents(self) -> None:
        """Parse the contents of the profile."""
        self.app_id_name = self._contents.get("AppIDName")
        self.application_identifier_prefix = self._contents.get("ApplicationIdentifierPrefix")
        self.creation_date = self._contents.get("CreationDate")
        self.platform = self._contents.get("Platform")
        self.entitlements = self._contents.get("Entitlements", {})
        self.expiration_date = self._contents.get("ExpirationDate")
        self.name = self._contents.get("Name")
        self.team_identifier = self._contents.get("TeamIdentifier")
        self.team_name = self._contents.get("TeamName")
        self.time_to_live = self._contents.get("TimeToLive")
        self.uuid = self._contents.get("UUID")
        self.version = self._contents.get("Version")
        self.provisioned_devices = self._contents.get("ProvisionedDevices")
        self.provisions_all_devices = self._contents.get("ProvisionsAllDevices", False)

    def _get_xml(self) -> str:
        """Load the XML contents of a provisioning profile."""
        if not os.path.exists(self.file_path):
            raise Exception(f"File does not exist: {self.file_path}")

        security_cmd = f'security cms -D -i "{self.file_path}" 2> /dev/null'
        return subprocess.check_output(
            security_cmd,
            universal_newlines=True,
            shell=True
        ).strip()
#pylint: enable=too-many-instance-attributes


def profiles(profiles_dir: Optional[str] = None) -> List[ProvisioningProfile]:
    """Returns a list of all currently installed provisioning profiles."""
    if profiles_dir:
        dir_path = os.path.expanduser(profiles_dir)
    else:
        user_path = os.path.expanduser('~')
        dir_path = os.path.join(user_path,
                                "Library",
                                "MobileDevice",
                                "Provisioning Profiles")

    all_profiles = []
    for profile in os.listdir(dir_path):
        full_path = os.path.join(dir_path, profile)
        _, ext = os.path.splitext(full_path)
        if ext == ".mobileprovision":
            provisioning_profile = ProvisioningProfile(full_path)
            all_profiles.append(provisioning_profile)

    return all_profiles


def diff(a_path: str, b_path: str, ignore_keys: Optional[List[str]] = None, tool_override: Optional[str] = None) -> str:
    """Diff two provisioning profiles."""

    #pylint: disable=too-many-locals

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
            except KeyError:
                pass
            try:
                del b_dict[key]
            except KeyError:
                pass

        a_xml = plistlib.dumps(a_dict).decode("utf-8")
        b_xml = plistlib.dumps(b_dict).decode("utf-8")

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


def value_for_key(profile_path: str, key: str) -> Optional[Any]:
    """Return the value for a given key"""

    profile = ProvisioningProfile(profile_path)

    try:
        value = profile.contents()[key]
        return value
    except KeyError:
        return None


def decode(profile_path: str, xml: bool = True):
    """Decode a profile, returning as a dictionary if xml is set to False."""

    profile = ProvisioningProfile(profile_path)

    if xml:
        return profile.xml

    return profile.contents()


if __name__ == "__main__":
    print("This should only be used as a module.")
    sys.exit(1)
