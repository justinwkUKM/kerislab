import unittest

from kerislab.models import Target
from kerislab.scope import ScopeError, validate_target_scope


class ScopeTests(unittest.TestCase):
    def target(self, url: str, allow_private: bool = False) -> Target:
        return Target(
            workspace_id="wks_test",
            project_id="prj_test",
            name="target",
            url=url,
            allow_private_networks=allow_private,
        )

    def test_allows_public_https_target(self) -> None:
        validate_target_scope(self.target("https://example.com"))

    def test_blocks_localhost_by_default(self) -> None:
        with self.assertRaises(ScopeError):
            validate_target_scope(self.target("http://localhost:8000"))

    def test_blocks_private_ip_by_default(self) -> None:
        with self.assertRaises(ScopeError):
            validate_target_scope(self.target("http://192.168.1.10"))

    def test_allows_private_ip_when_explicitly_enabled(self) -> None:
        validate_target_scope(self.target("http://192.168.1.10", allow_private=True))

    def test_rejects_non_http_scheme(self) -> None:
        with self.assertRaises(ScopeError):
            validate_target_scope(self.target("file:///etc/passwd"))


if __name__ == "__main__":
    unittest.main()

