"""Test direct subprocess execution and literal argument handling."""

from pathlib import Path
import plistlib
import subprocess
from unittest.mock import patch

import pytest

import protool


@pytest.fixture(name="profile_paths")
def fixture_profile_paths(tmp_path: Path) -> tuple[str, str]:
    """Create profile paths containing spaces and shell metacharacters."""
    paths = (
        tmp_path / 'first "$(echo expanded)" `echo expanded`; $HOME.mobileprovision',
        tmp_path / "second 'profile' & file.mobileprovision",
    )
    for path in paths:
        path.touch()
    return str(paths[0]), str(paths[1])


def test_decode_uses_literal_path(profile_paths: tuple[str, str]) -> None:
    """Pass the entire profile path as one argument without shell execution."""
    xml = plistlib.dumps({"Name": "Test"}).decode()
    with patch("protool.subprocess.check_output", return_value=f" \n{xml}\n ") as run:
        profile = protool.ProvisioningProfile(profile_paths[0], sort_keys=False)

    run.assert_called_once_with(
        ["security", "cms", "-D", "-i", profile_paths[0]],
        universal_newlines=True,
        stderr=subprocess.DEVNULL,
    )
    assert profile.xml == xml.strip()
    assert profile.name == "Test"


def test_decode_propagates_failure(profile_paths: tuple[str, str]) -> None:
    """Keep reporting a decoding command's failure to the caller."""
    error = subprocess.CalledProcessError(1, ["security"])
    with patch("protool.subprocess.check_output", side_effect=error):
        with pytest.raises(subprocess.CalledProcessError) as caught:
            protool.ProvisioningProfile(profile_paths[0])
    assert caught.value is error


@pytest.mark.parametrize(
    ("tool_override", "expected"),
    [
        (None, ["opendiff"]),
        ("diff -u", ["diff", "-u"]),
        (
            '"/path with spaces/diff" --label "a b" "$HOME" "$(echo literal)" ";"',
            [
                "/path with spaces/diff",
                "--label",
                "a b",
                "$HOME",
                "$(echo literal)",
                ";",
            ],
        ),
    ],
)
def test_diff_uses_argument_list(
    profile_paths: tuple[str, str],
    tool_override: str | None,
    expected: list[str],
) -> None:
    """Preserve quoted tool arguments and literal profile filenames."""
    xml = plistlib.dumps({"Name": "Test"}).decode()
    with (
        patch.object(protool.ProvisioningProfile, "_get_xml", return_value=xml),
        patch("protool.subprocess.check_output", return_value=" output \n") as run,
    ):
        result = protool.diff(*profile_paths, tool_override=tool_override)

    run.assert_called_once()
    command = run.call_args.args[0]
    assert command[:-2] == expected
    assert [Path(path).name for path in command[-2:]] == [
        Path(path).name for path in profile_paths
    ]
    assert run.call_args.kwargs == {"universal_newlines": True}
    assert result == "output"
    assert not Path(command[-1]).parent.exists()


@pytest.mark.parametrize("tool_override", ["", "   ", '""', '"unterminated'])
def test_diff_rejects_invalid_command(tool_override: str) -> None:
    """Reject empty or malformed tool commands before decoding profiles."""
    with patch.object(protool.ProvisioningProfile, "_get_xml") as decode:
        with pytest.raises(ValueError):
            protool.diff("first", "second", tool_override=tool_override)
    decode.assert_not_called()


def test_diff_cleans_up_after_launch_failure(profile_paths: tuple[str, str]) -> None:
    """Remove temporary profiles when an executable cannot be launched."""
    xml = plistlib.dumps({"Name": "Test"}).decode()
    with (
        patch.object(protool.ProvisioningProfile, "_get_xml", return_value=xml),
        patch("protool.subprocess.check_output", side_effect=FileNotFoundError) as run,
    ):
        with pytest.raises(FileNotFoundError):
            protool.diff(*profile_paths)
    assert not Path(run.call_args.args[0][-1]).parent.exists()


@pytest.mark.parametrize("different", [False, True])
def test_real_diff(profile_paths: tuple[str, str], different: bool) -> None:
    """Capture real diff output, including exit status one for differences."""
    contents = [{"Name": "First"}, {"Name": "Second" if different else "First"}]
    with patch.object(
        protool.ProvisioningProfile,
        "_get_xml",
        side_effect=[plistlib.dumps(value).decode() for value in contents],
    ):
        output = protool.diff(*profile_paths, tool_override="diff -u")

    if different:
        assert "-\t<string>First</string>" in output
        assert "+\t<string>Second</string>" in output
    else:
        assert output == ""
