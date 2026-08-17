import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    sys.modules["requests"] = SimpleNamespace(Response=object)

from licensing import (
    _clean_hwid_value,
    _extract_error,
    _extract_expiry,
    _is_success_response,
    check_license,
    normalize_license_key,
)


class LicensingTests(unittest.TestCase):
    def test_normalize_license_key(self):
        self.assertEqual(normalize_license_key(" zernix - ab12 / cd34 "), "ZERNIX-AB12CD34")

    def test_clean_hwid_rejects_firmware_placeholders(self):
        self.assertEqual(_clean_hwid_value("To be filled by O.E.M."), "")
        self.assertEqual(_clean_hwid_value("0000-0000-0000"), "")

    def test_clean_hwid_keeps_stable_identifier(self):
        self.assertEqual(_clean_hwid_value(" a1b2-c3d4-e5f6 "), "A1B2-C3D4-E5F6")

    def test_license_response_helpers_accept_supported_shapes(self):
        self.assertTrue(_is_success_response({"valid": True}))
        self.assertTrue(_is_success_response({"status": "success"}))
        self.assertEqual(_extract_expiry({"expires_at": "2027-01-01"}), "2027-01-01")
        self.assertEqual(_extract_error({"detail": "expired"}), "expired")

    def test_license_check_requires_configured_api_key(self):
        with patch("licensing.API_KEY", ""):
            self.assertEqual(
                check_license("ZERNIX-AB12-CD34"),
                (False, "License server API key is not configured."),
            )


if __name__ == "__main__":
    unittest.main()
