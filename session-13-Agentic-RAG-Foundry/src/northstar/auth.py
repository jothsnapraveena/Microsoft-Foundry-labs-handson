"""Caller identity. The customer is always derived here, never from IDs in the request body or chat."""
from dataclasses import dataclass
import logging

log = logging.getLogger("northstar.auth")
CUSTOMER_CHANNEL, AGENT_CHANNEL = "customer", "agent"


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class Identity:
    customer_id: str
    channel: str      # only the customer channel may confirm a proposal


class DemoAuthenticator:
    """LOCAL DEMO STUB. Trusts request headers, so anyone who can reach the service can be any customer.

    Selected only by NORTHSTAR_AUTH_MODE=demo. Never enable it in a deployed configuration.
    """
    def __init__(self, repository):
        self.repository = repository
        log.warning("DEMO IDENTITY STUB ENABLED: callers are trusted by header. Do not deploy this configuration.")

    def authenticate(self, headers):
        customer_id = headers.get("x-demo-customer-id")
        channel = headers.get("x-demo-channel", AGENT_CHANNEL)
        if not customer_id or channel not in (CUSTOMER_CHANNEL, AGENT_CHANNEL):
            raise AuthError("Missing demo identity")
        with self.repository.transaction() as uow:
            if not uow.customer_exists(customer_id):
                raise AuthError("Unknown identity")
        return Identity(customer_id, channel)


class EntraAuthenticator:
    """Validates a Microsoft Entra access token: signature, issuer, audience and expiry.

    The token subject is mapped to a customer through the customer_identities table.
    The confirmation scope marks a token issued to the customer-facing client.
    """
    def __init__(self, repository, tenant_id, audience, confirm_scope, customer_claim="oid", signing_key=None):
        if not tenant_id or not audience:
            raise AuthError("ENTRA_TENANT_ID and ENTRA_AUDIENCE are required when NORTHSTAR_AUTH_MODE=entra")
        import jwt                           # PyJWT; imported here so demo mode runs without it
        self.jwt = jwt
        self.repository, self.audience = repository, audience
        self.confirm_scope, self.customer_claim = confirm_scope, customer_claim
        self.issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
        self.signing_key = signing_key or jwt.PyJWKClient(
            f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys").get_signing_key_from_jwt

    def authenticate(self, headers):
        scheme, _, token = headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise AuthError("Missing bearer token")
        try:
            key = self.signing_key(token)
            claims = self.jwt.decode(token, getattr(key, "key", key), algorithms=["RS256"], audience=self.audience,
                                     issuer=self.issuer, options={"require": ["exp", "iss", "aud"]})
        except Exception as error:           # any validation failure is the same 401
            raise AuthError("Invalid token") from error
        subject = claims.get(self.customer_claim)
        with self.repository.transaction() as uow:
            customer_id = subject and uow.customer_for_subject(subject)
        if not customer_id:
            raise AuthError("Identity is not linked to a customer")
        scopes = str(claims.get("scp", "")).split()
        return Identity(customer_id, CUSTOMER_CHANNEL if self.confirm_scope in scopes else AGENT_CHANNEL)


def build_authenticator(settings, repository):
    if settings.auth_mode == "demo":
        return DemoAuthenticator(repository)
    if settings.auth_mode == "entra":
        return EntraAuthenticator(repository, settings.entra_tenant_id, settings.entra_audience,
                                  settings.entra_confirm_scope, settings.entra_customer_claim)
    raise AuthError(f"Unknown NORTHSTAR_AUTH_MODE: {settings.auth_mode}")
