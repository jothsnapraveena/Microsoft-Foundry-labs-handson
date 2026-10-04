"""HTTP layer and authentication. Skipped when FastAPI or PyJWT are not installed."""
from datetime import datetime, timedelta, timezone
import unittest

from fixtures import Environment, case

try:
    from cryptography.hazmat.primitives.asymmetric import rsa
    from fastapi.testclient import TestClient
    import jwt

    from northstar.api import create_app
    from northstar.auth import AuthError, DemoAuthenticator, EntraAuthenticator
    from northstar.config import Settings
    AVAILABLE = True
except ImportError:
    AVAILABLE = False

TENANT, AUDIENCE = "00000000-0000-0000-0000-000000000001", "api://northstar-tools"


@unittest.skipUnless(AVAILABLE, "install requirements.txt to run API tests")
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.env = Environment()
        self.addCleanup(self.env.close)
        self.settings = Settings.from_env({"NORTHSTAR_AUTH_MODE": "demo"})
        self.client = TestClient(create_app(self.settings, self.env.service, DemoAuthenticator(self.env.repository)))
        self.owner, self.request, _ = case("defective-early")
        self.body = self.request.__dict__

    def headers(self, customer=None, channel="agent", **extra):
        return {"X-Demo-Customer-Id": customer or self.owner, "X-Demo-Channel": channel, **extra}

    def test_requests_without_identity_are_rejected(self):
        self.assertEqual(self.client.get(f"/orders/{self.request.order_id}").status_code, 401)
        self.assertEqual(self.client.get(f"/orders/{self.request.order_id}", headers=self.headers("CUST-999")).status_code, 401)

    def test_unowned_and_missing_orders_give_identical_responses(self):
        intruder = self.headers("CUST-001" if self.owner != "CUST-001" else "CUST-002")
        unowned = self.client.get(f"/orders/{self.request.order_id}", headers=intruder)
        missing = self.client.get("/orders/ORD-9999", headers=intruder)
        self.assertEqual((unowned.status_code, unowned.json()), (404, missing.json()))
        self.assertEqual(missing.status_code, 404)
        self.assertNotIn(self.request.order_id, unowned.text)

    def test_customer_id_in_the_body_is_rejected_not_trusted(self):
        response = self.client.post("/returns/eligibility", headers=self.headers("CUST-001" if self.owner != "CUST-001" else "CUST-002"),
                                    json={**self.body, "customer_id": self.owner})
        self.assertEqual(response.status_code, 422)

    def test_full_confirmed_return_flow(self):
        eligibility = self.client.post("/returns/eligibility", headers=self.headers(), json=self.body).json()
        self.assertEqual(eligibility["outcome"], "eligible")
        proposal_id = eligibility["proposal"]["proposal_id"]
        # The agent channel cannot confirm on the customer's behalf.
        self.assertEqual(self.client.post("/confirmations", headers=self.headers(), json={"proposal_id": proposal_id}).status_code, 403)
        unconfirmed = self.client.post("/returns", headers=self.headers(**{"Idempotency-Key": "k1"}),
                                       json={"proposal_id": proposal_id, "confirmation_token": "guess"})
        self.assertEqual(unconfirmed.status_code, 403)
        token = self.client.post("/confirmations", headers=self.headers(channel="customer"), json={"proposal_id": proposal_id}).json()["confirmation_token"]
        write = {"proposal_id": proposal_id, "confirmation_token": token}
        self.assertEqual(self.client.post("/returns", headers=self.headers(), json=write).status_code, 422)   # no idempotency key
        created = self.client.post("/returns", headers=self.headers(**{"Idempotency-Key": "k1"}), json=write)
        self.assertEqual((created.status_code, created.json()["status"]), (200, "authorized"))
        retry = self.client.post("/returns", headers=self.headers(**{"Idempotency-Key": "k1"}), json=write).json()
        self.assertEqual(retry["return_id"], created.json()["return_id"])
        self.assertEqual(self.client.post("/returns", headers=self.headers(**{"Idempotency-Key": "k2"}), json=write).status_code, 409)
        status = self.client.get(f"/returns/{created.json()['return_id']}", headers=self.headers()).json()
        self.assertEqual((status["status"], status["refund"], status["refund_issued"]), ("authorized", None, False))

    def test_invalid_input_and_trace_link(self):
        bad = self.client.post("/returns/eligibility", headers=self.headers(), json={**self.body, "quantity": "1"})
        self.assertEqual(bad.status_code, 422)
        trace = "0af7651916cd43dd8448eb211c80319c"
        self.client.get(f"/orders/{self.request.order_id}", headers=self.headers("CUST-001" if self.owner != "CUST-001" else "CUST-002",
                        traceparent=f"00-{trace}-b7ad6b7169203331-01"))
        self.assertEqual(self.env.query("SELECT trace_id FROM audit_log ORDER BY audit_id DESC LIMIT 1")[0][0], trace)

    def test_confirmation_endpoint_is_not_an_advertised_tool(self):
        operations = {operation["operationId"] for path in self.client.get("/openapi.json").json()["paths"].values() for operation in path.values()}
        self.assertEqual(operations, {"get_order", "check_return_eligibility", "create_return", "get_return_status",
                                      "propose_cancel_order", "cancel_order", "propose_support_ticket", "create_support_ticket"})


@unittest.skipUnless(AVAILABLE, "install requirements.txt to run API tests")
class EntraTokenTests(unittest.TestCase):
    """Validates tokens signed by a key generated here. No live tenant is contacted."""
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.env = Environment()
        self.addCleanup(self.env.close)
        self.env.execute("INSERT INTO customer_identities (subject, customer_id) VALUES ('subject-1', 'CUST-001')")
        self.auth = EntraAuthenticator(self.env.repository, TENANT, AUDIENCE, "Returns.Confirm",
                                       signing_key=lambda token: self.key.public_key())

    def token(self, key=None, **overrides):
        claims = {"iss": f"https://login.microsoftonline.com/{TENANT}/v2.0", "aud": AUDIENCE, "oid": "subject-1",
                  "exp": datetime.now(timezone.utc) + timedelta(minutes=5), "scp": "Support.Tools", **overrides}
        return {"authorization": "Bearer " + jwt.encode({k: v for k, v in claims.items() if v is not None}, key or self.key, algorithm="RS256")}

    def test_valid_token_maps_to_customer_and_channel(self):
        self.assertEqual(self.auth.authenticate(self.token()).__dict__, {"customer_id": "CUST-001", "channel": "agent"})
        self.assertEqual(self.auth.authenticate(self.token(scp="Support.Tools Returns.Confirm")).channel, "customer")

    def test_invalid_tokens_are_rejected(self):
        bad = {"wrong signature": self.token(key=self.other_key), "wrong audience": self.token(aud="api://other"),
               "wrong issuer": self.token(iss="https://login.microsoftonline.com/other/v2.0"),
               "expired": self.token(exp=datetime.now(timezone.utc) - timedelta(minutes=5)), "no expiry": self.token(exp=None),
               "unlinked subject": self.token(oid="subject-2"), "no header": {}, "not bearer": {"authorization": "Basic abc"},
               "unsigned": {"authorization": "Bearer " + jwt.encode({"aud": AUDIENCE}, None, algorithm="none")}}
        for name, headers in bad.items():
            with self.subTest(name), self.assertRaises(AuthError):
                self.auth.authenticate(headers)

    def test_entra_mode_refuses_to_start_unconfigured(self):
        with self.assertRaises(AuthError):
            EntraAuthenticator(self.env.repository, None, None, "Returns.Confirm")
        self.assertEqual(Settings.from_env({}).auth_mode, "entra")


if __name__ == "__main__":
    unittest.main()
