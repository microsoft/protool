"""Test deserializing."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
#pylint: disable=wrong-import-position
import protool
#pylint: enable=wrong-import-position


class ParsingTestSuite(unittest.TestCase):
    """Protool parsing test cases."""

    def test_parsing(self):
        """Test that parsers are applied correctly."""
        self.assertIsNotNone(protool.ProvisioningType.AD_HOC_DISTRIBUTION)
