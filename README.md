# protool 

[![PyPi Version](https://img.shields.io/pypi/v/protool.svg)](https://pypi.org/project/protool/)
[![License](https://img.shields.io/pypi/l/protool.svg)](https://github.com/Microsoft/protool/blob/master/LICENSE)

A tool for dealing with provisioning profiles.

What can it do? 

* Read profiles as XML or as a dictionary
* Read the values from the profile
* Diff two profiles to see what has changed

### Installation

    pip install protool

### Examples:

    import protool
    profile = protool.ProvisioningProfile("/path/to/profile")

    # Get the diff of two profiles
    diff = protool.diff("/path/to/first", "/path/to/second", tool_override="diff")

    # Get the UUID of a profile
    print profile.uuid

    # Get the full XML of the profile
    print profile.xml

    # Get the parsed contents of the profile as a dictionary
    print profile.contents()


Alternatively, from the command line:

    # Get the diff
    protool diff --profiles /path/to/profile1 /path/to/profile2 --tool diff

    # Get the UUID of a profile
    protool read --profile /path/to/profile --key UUID

    # Get the raw XML (identical to using `security cms -D -i /path/to/profile`)
    protool decode --profile /path/to/profile


# Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.microsoft.com.

When you submit a pull request, a CLA-bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
