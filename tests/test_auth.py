import os
import unittest
from base64 import urlsafe_b64encode
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from kerislab.auth import OAuthConfigurationError, OAuthService


def id_token_for(claims: dict[str, object]) -> str:
    encoded_claims = urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"header.{encoded_claims}.signature"


class OAuthTests(unittest.TestCase):
    def test_google_authorization_url_uses_oidc_parameters(self) -> None:
        env = {
            "KERISLAB_GOOGLE_CLIENT_ID": "client-id",
            "KERISLAB_GOOGLE_CLIENT_SECRET": "client-secret",
            "KERISLAB_GOOGLE_REDIRECT_URI": "https://kerislab.example.com/api/auth/google/callback",
        }
        with patch.dict(os.environ, env, clear=False):
            service = OAuthService()
            url = service.authorization_url(service.google_config(), state="state", nonce="nonce")

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "accounts.google.com")
        self.assertEqual(query["client_id"], ["client-id"])
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["state"], ["state"])
        self.assertEqual(query["nonce"], ["nonce"])
        self.assertIn("openid", query["scope"][0])

    def test_sso_authorization_url_uses_enterprise_provider_config(self) -> None:
        env = {
            "KERISLAB_SSO_CLIENT_ID": "sso-client",
            "KERISLAB_SSO_CLIENT_SECRET": "sso-secret",
            "KERISLAB_SSO_AUTHORIZE_URL": "https://idp.example.com/oauth2/authorize",
            "KERISLAB_SSO_TOKEN_URL": "https://idp.example.com/oauth2/token",
            "KERISLAB_SSO_REDIRECT_URI": "https://kerislab.example.com/api/auth/sso/callback",
            "KERISLAB_SSO_SCOPES": "openid email groups",
        }
        with patch.dict(os.environ, env, clear=False):
            service = OAuthService()
            url = service.authorization_url(service.sso_config(), state="state", nonce="nonce")

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "idp.example.com")
        self.assertEqual(query["client_id"], ["sso-client"])
        self.assertIn("groups", query["scope"][0])

    def test_resolve_profile_fetches_userinfo_when_access_token_is_returned(self) -> None:
        env = {
            "KERISLAB_GOOGLE_CLIENT_ID": "client-id",
            "KERISLAB_GOOGLE_CLIENT_SECRET": "client-secret",
            "KERISLAB_GOOGLE_REDIRECT_URI": "https://kerislab.example.com/api/auth/google/callback",
        }
        with patch.dict(os.environ, env, clear=False):
            service = OAuthService()
            config = service.google_config()
            with patch.object(
                service,
                "fetch_userinfo",
                return_value={"email": "user@example.com", "name": "User", "picture": "https://avatar.example.com/u.png"},
            ) as fetch:
                profile = service.resolve_profile(config, {"access_token": "access-token"})

        fetch.assert_called_once_with(config, access_token="access-token")
        self.assertEqual(profile["email"], "user@example.com")
        self.assertEqual(profile["display_name"], "User")
        self.assertEqual(profile["avatar_url"], "https://avatar.example.com/u.png")

    def test_resolve_profile_extracts_id_token_claims(self) -> None:
        env = {
            "KERISLAB_GOOGLE_CLIENT_ID": "client-id",
            "KERISLAB_GOOGLE_CLIENT_SECRET": "client-secret",
            "KERISLAB_GOOGLE_REDIRECT_URI": "https://kerislab.example.com/api/auth/google/callback",
        }
        claims = {
            "email": "idtoken@example.com",
            "preferred_username": "idtoken-user",
            "aud": "client-id",
            "iss": "https://accounts.google.com",
            "nonce": "nonce",
        }
        id_token = id_token_for(claims)
        with patch.dict(os.environ, env, clear=False):
            service = OAuthService()
            config = service.google_config()
            profile = service.resolve_profile(config, {"id_token": id_token}, expected_nonce="nonce")
        self.assertEqual(profile["email"], "idtoken@example.com")
        self.assertEqual(profile["display_name"], "idtoken-user")

    def test_resolve_profile_rejects_id_token_nonce_mismatch(self) -> None:
        env = {
            "KERISLAB_GOOGLE_CLIENT_ID": "client-id",
            "KERISLAB_GOOGLE_CLIENT_SECRET": "client-secret",
            "KERISLAB_GOOGLE_REDIRECT_URI": "https://kerislab.example.com/api/auth/google/callback",
        }
        id_token = id_token_for(
            {
                "email": "idtoken@example.com",
                "aud": "client-id",
                "iss": "https://accounts.google.com",
                "nonce": "wrong",
            }
        )
        with patch.dict(os.environ, env, clear=False):
            service = OAuthService()
            config = service.google_config()
            with self.assertRaises(OAuthConfigurationError):
                service.resolve_profile(config, {"id_token": id_token}, expected_nonce="expected")

    def test_resolve_profile_rejects_id_token_audience_mismatch(self) -> None:
        env = {
            "KERISLAB_GOOGLE_CLIENT_ID": "client-id",
            "KERISLAB_GOOGLE_CLIENT_SECRET": "client-secret",
            "KERISLAB_GOOGLE_REDIRECT_URI": "https://kerislab.example.com/api/auth/google/callback",
        }
        id_token = id_token_for(
            {
                "email": "idtoken@example.com",
                "aud": "other-client",
                "iss": "https://accounts.google.com",
                "nonce": "nonce",
            }
        )
        with patch.dict(os.environ, env, clear=False):
            service = OAuthService()
            config = service.google_config()
            with self.assertRaises(OAuthConfigurationError):
                service.resolve_profile(config, {"id_token": id_token}, expected_nonce="nonce")


if __name__ == "__main__":
    unittest.main()
