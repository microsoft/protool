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
from typing import Any, cast
from OpenSSL import crypto


def _extract_certificate_properties(cert: crypto.X509) -> dict[str, Any]:
    """Extract key properties from an X509 certificate."""
    subject = cert.get_subject()
    issuer = cert.get_issuer()

    # Helper to safely get X509Name components
    def get_component(name_obj, component: str) -> str | None:
        try:
            return getattr(name_obj, component, None)
        except AttributeError:
            return None

    # Parse ASN.1 TIME to ISO 8601 format
    def parse_asn1_time(time_bytes: bytes | None) -> str | None:
        if time_bytes is None:
            return None
        time_str = time_bytes.decode("utf-8")
        # ASN.1 format: YYYYMMDDhhmmssZ
        # Convert to ISO 8601: YYYY-MM-DDThh:mm:ssZ
        try:
            return f"{time_str[0:4]}-{time_str[4:6]}-{time_str[6:8]}T{time_str[8:10]}:{time_str[10:12]}:{time_str[12:14]}Z"
        except (IndexError, ValueError):
            return time_str  # Return as-is if parsing fails

    return {
        "CommonName": get_component(subject, "CN"),
        "Organization": get_component(subject, "O"),
        "OrganizationalUnit": get_component(subject, "OU"),
        "Country": get_component(subject, "C"),
        "IssuerCommonName": get_component(issuer, "CN"),
        "IssuerOrganization": get_component(issuer, "O"),
        "SerialNumber": str(
            cert.get_serial_number()  # Other libs struggle with large integers
        ),
        "NotBefore": parse_asn1_time(cert.get_notBefore()),
        "NotAfter": parse_asn1_time(cert.get_notAfter()),
        "SignatureAlgorithm": (
            cert.get_signature_algorithm().decode("utf-8")
            if cert.get_signature_algorithm()
            else None
        ),
        "Fingerprint": (
            cert.digest("sha256").decode("utf-8") if hasattr(cert, "digest") else None
        ),
    }


class ProvisioningType(Enum):
    """Enum representing the type of provisioning profile."""

    IOS_DEVELOPMENT = 1
    APP_STORE_DISTRIBUTION = 3
    AD_HOC_DISTRIBUTION = 5
    ENTERPRISE_DISTRIBUTION = 7


# pylint: disable=too-many-instance-attributes
class ProvisioningProfile:
    """Represents a provisioning profile."""

    file_path: str
    file_name: str
    xml: str
    _contents: dict[str, Any]
    _decode_certificates: bool

    app_id_name: str | None
    application_identifier_prefix: str | None
    creation_date: datetime.datetime | None
    platform: list[str] | None
    entitlements: dict[str, Any]
    expiration_date: datetime.datetime | None
    name: str | None
    team_identifier: list[str] | None
    team_name: str | None
    time_to_live: int | None
    uuid: str | None
    version: int | None
    provisioned_devices: list[str] | None
    provisions_all_devices: bool | None

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

    def developer_certificates(self) -> list[crypto.X509]:
        """Returns developer certificates as a list of PyOpenSSL X509."""
        dev_certs: list[crypto.X509] = []
        raw_cert_items: list[bytes] = cast(
            list[bytes], self._contents.get("DeveloperCertificates", [])
        )

        for cert_item in raw_cert_items:
            loaded_cert: crypto.X509 = crypto.load_certificate(
                crypto.FILETYPE_ASN1, cert_item
            )
            dev_certs.append(loaded_cert)

        return dev_certs

    def __init__(
        self,
        file_path: str,
        *,
        sort_keys: bool = True,
        decode_certificates: bool = False,
    ) -> None:
        self.file_path = os.path.abspath(file_path)
        self.file_name = os.path.basename(self.file_path)
        self._decode_certificates = decode_certificates
        self.load_from_disk(sort_keys=sort_keys)

    def load_from_disk(self, *, sort_keys: bool = True) -> None:
        """Load the provisioning profile details from disk and parse them."""
        self.xml = self._get_xml()
        self._contents = plistlib.loads(self.xml.encode())

        if sort_keys:
            self.xml = plistlib.dumps(self._contents, sort_keys=True).decode("utf-8")

        self._parse_contents()

        # If we decoded certificates, we need to regenerate the XML to include them
        if self._decode_certificates:
            contents_copy = copy.deepcopy(self._contents)
            del contents_copy["DeveloperCertificates"]
            del contents_copy["DER-Encoded-Profile"]
            self.xml = plistlib.dumps(contents_copy, sort_keys=sort_keys).decode(
                "utf-8"
            )

    def contents(self) -> dict[str, Any]:
        """Return a copy of the content dict."""
        return copy.deepcopy(self._contents)

    def _parse_contents(self) -> None:
        """Parse the contents of the profile."""
        self.app_id_name = self._contents.get("AppIDName")
        self.application_identifier_prefix = self._contents.get(
            "ApplicationIdentifierPrefix"
        )
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

        # Decode certificates if requested
        if self._decode_certificates:
            decoded_certs: list[dict[str, Any]] = []
            for cert in self.developer_certificates():
                try:
                    decoded_certs.append(_extract_certificate_properties(cert))
                except Exception as ex:
                    # Log error but continue with other certificates
                    print(
                        f"Warning: Failed to decode certificate: {ex}", file=sys.stderr
                    )
            self._contents["DecodedDeveloperCertificates"] = decoded_certs

    def _get_xml(self) -> str:
        """Load the XML contents of a provisioning profile."""
        if not os.path.exists(self.file_path):
            raise Exception(f"File does not exist: {self.file_path}")

        security_cmd = f'security cms -D -i "{self.file_path}" 2> /dev/null'
        return subprocess.check_output(
            security_cmd, universal_newlines=True, shell=True
        ).strip()


# pylint: enable=too-many-instance-attributes


def profiles(profiles_dir: str | None = None) -> list[ProvisioningProfile]:
    """Returns a list of all currently installed provisioning profiles."""
    if profiles_dir:
        dir_path = os.path.expanduser(profiles_dir)
    else:
        user_path = os.path.expanduser("~")
        dir_path = os.path.join(
            user_path, "Library", "MobileDevice", "Provisioning Profiles"
        )

    all_profiles: list[ProvisioningProfile] = []
    for profile in os.listdir(dir_path):
        full_path = os.path.join(dir_path, profile)
        _, ext = os.path.splitext(full_path)
        if ext == ".mobileprovision":
            provisioning_profile = ProvisioningProfile(full_path)
            all_profiles.append(provisioning_profile)

    return all_profiles


def diff(
    a_path: str,
    b_path: str,
    *,
    sort_keys: bool = True,
    ignore_keys: list[str] | None = None,
    tool_override: str | None = None,
) -> str:
    """Diff two provisioning profiles."""

    # pylint: disable=too-many-locals

    if tool_override is None:
        diff_tool = "opendiff"
    else:
        diff_tool = tool_override

    profile_a = ProvisioningProfile(a_path, sort_keys=sort_keys)
    profile_b = ProvisioningProfile(b_path, sort_keys=sort_keys)

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

    with open(a_temp_path, "w", encoding="utf-8") as temp_profile:
        temp_profile.write(a_xml)

    with open(b_temp_path, "w", encoding="utf-8") as temp_profile:
        temp_profile.write(b_xml)

    # We deliberately don't wrap the tool so that arguments work as well
    diff_command = f'{diff_tool} "{a_temp_path}" "{b_temp_path}"'

    try:
        diff_contents = subprocess.check_output(
            diff_command, universal_newlines=True, shell=True
        ).strip()
    except subprocess.CalledProcessError as ex:
        # Diff tools usually return a non-0 exit code if there are differences,
        # so we just swallow this error
        diff_contents = ex.output

    # Cleanup
    shutil.rmtree(temp_dir)

    return diff_contents


def value_for_key(profile_path: str, key: str) -> Any | None:
    """Return the value for a given key"""

    profile = ProvisioningProfile(profile_path)

    try:
        value = profile.contents()[key]
        return value
    except KeyError:
        return None


def decode(profile_path: str, xml: bool = True, *, decode_certificates: bool = False):
    """Decode a profile, returning as a dictionary if xml is set to False."""

    profile = ProvisioningProfile(profile_path, decode_certificates=decode_certificates)

    if xml:
        return profile.xml

    return profile.contents()


if __name__ == "__main__":
    print("This should only be used as a module.")
    sys.exit(1)
