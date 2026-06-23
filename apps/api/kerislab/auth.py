from __future__ import annotations

import json
import os
from base64 import urlsafe_b64decode
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import AuthProvider


@dataclass(frozen=True)
class OIDCProviderConfig:
    provider: AuthProvider
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str | None
    issuer_urls: tuple[str, ...]
    redirect_uri: str
    scopes: tuple[str, ...]


class OAuthConfigurationError(ValueError):
    pass


class OAuthService:
    GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
    GOOGLE_ISSUER_URLS = ("https://accounts.google.com", "accounts.google.com")

    def google_config(self) -> OIDCProviderConfig:
        return OIDCProviderConfig(
            provider=AuthProvider.GOOGLE,
            client_id=self._required("KERISLAB_GOOGLE_CLIENT_ID"),
            client_secret=self._required("KERISLAB_GOOGLE_CLIENT_SECRET"),
            authorize_url=os.getenv("KERISLAB_GOOGLE_AUTHORIZE_URL", self.GOOGLE_AUTHORIZE_URL),
            token_url=os.getenv("KERISLAB_GOOGLE_TOKEN_URL", self.GOOGLE_TOKEN_URL),
            userinfo_url=os.getenv("KERISLAB_GOOGLE_USERINFO_URL", self.GOOGLE_USERINFO_URL),
            issuer_urls=tuple(os.getenv("KERISLAB_GOOGLE_ISSUER_URLS", ",".join(self.GOOGLE_ISSUER_URLS)).split(",")),
            redirect_uri=self._required("KERISLAB_GOOGLE_REDIRECT_URI"),
            scopes=("openid", "email", "profile"),
        )

    def sso_config(self) -> OIDCProviderConfig:
        return OIDCProviderConfig(
            provider=AuthProvider.SSO,
            client_id=self._required("KERISLAB_SSO_CLIENT_ID"),
            client_secret=self._required("KERISLAB_SSO_CLIENT_SECRET"),
            authorize_url=self._required("KERISLAB_SSO_AUTHORIZE_URL"),
            token_url=self._required("KERISLAB_SSO_TOKEN_URL"),
            userinfo_url=os.getenv("KERISLAB_SSO_USERINFO_URL"),
            issuer_urls=tuple(filter(None, os.getenv("KERISLAB_SSO_ISSUER_URLS", "").split(","))),
            redirect_uri=self._required("KERISLAB_SSO_REDIRECT_URI"),
            scopes=tuple(os.getenv("KERISLAB_SSO_SCOPES", "openid email profile").split()),
        )

    def authorization_url(self, config: OIDCProviderConfig, *, state: str, nonce: str) -> str:
        query = urlencode(
            {
                "client_id": config.client_id,
                "redirect_uri": config.redirect_uri,
                "response_type": "code",
                "scope": " ".join(config.scopes),
                "state": state,
                "nonce": nonce,
                "access_type": "offline",
                "prompt": "consent",
            }
        )
        return f"{config.authorize_url}?{query}"

    def exchange_code(self, config: OIDCProviderConfig, *, code: str) -> dict[str, Any]:
        body = urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config.redirect_uri,
                "client_id": config.client_id,
                "client_secret": config.client_secret,
            }
        ).encode()
        request = Request(
            config.token_url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode())

    def fetch_userinfo(self, config: OIDCProviderConfig, *, access_token: str) -> dict[str, Any]:
        if not config.userinfo_url:
            raise OAuthConfigurationError("OIDC userinfo endpoint is not configured")
        request = Request(
            config.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode())

    def resolve_profile(
        self,
        config: OIDCProviderConfig,
        token_response: dict[str, Any],
        *,
        expected_nonce: str | None = None,
    ) -> dict[str, str | None]:
        if isinstance(token_response.get("userinfo"), dict) or token_response.get("email"):
            return self.profile_from_claims(token_response)
        if token_response.get("id_token"):
            claims = self.claims_from_id_token(str(token_response["id_token"]))
            self.validate_id_token_claims(config, claims, expected_nonce=expected_nonce)
            return self.profile_from_claims(claims)
        if token_response.get("access_token") and config.userinfo_url:
            return self.profile_from_claims(
                self.fetch_userinfo(config, access_token=str(token_response["access_token"]))
            )
        raise OAuthConfigurationError("OIDC token response does not include resolvable user profile claims")

    def validate_id_token_claims(
        self,
        config: OIDCProviderConfig,
        claims: dict[str, Any],
        *,
        expected_nonce: str | None = None,
    ) -> None:
        audience = claims.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if config.client_id not in audiences:
            raise OAuthConfigurationError("OIDC id_token audience does not match client_id")
        if config.issuer_urls and claims.get("iss") not in config.issuer_urls:
            raise OAuthConfigurationError("OIDC id_token issuer is not trusted")
        if expected_nonce is not None and claims.get("nonce") != expected_nonce:
            raise OAuthConfigurationError("OIDC id_token nonce does not match OAuth state")

    def claims_from_id_token(self, id_token: str) -> dict[str, Any]:
        parts = id_token.split(".")
        if len(parts) < 2:
            raise OAuthConfigurationError("OIDC id_token is malformed")
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        try:
            return json.loads(urlsafe_b64decode(payload.encode()).decode())
        except Exception as exc:
            raise OAuthConfigurationError("OIDC id_token payload is invalid") from exc

    def profile_from_token_response(self, token_response: dict[str, Any]) -> dict[str, str | None]:
        return self.profile_from_claims(token_response)

    def profile_from_claims(self, claims: dict[str, Any]) -> dict[str, str | None]:
        userinfo = claims.get("userinfo")
        if isinstance(userinfo, dict):
            claims = userinfo
        if claims.get("email"):
            return {
                "email": str(claims["email"]),
                "display_name": str(claims.get("name") or claims.get("preferred_username") or claims["email"]),
                "avatar_url": str(claims["picture"]) if claims.get("picture") else None,
            }
        raise OAuthConfigurationError("OIDC claims do not include an email address")

    def _required(self, name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise OAuthConfigurationError(f"{name} is required")
        return value
