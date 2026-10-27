import io
import json
import unittest
from unittest.mock import patch

import provisioning_credential as module

ACTIONS_ENV = {
    "ACTIONS_ID_TOKEN_REQUEST_URL": "https://actions.example/token?api-version=2.0",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-token",
    "ARM_CLIENT_ID": "client",
    "ARM_TENANT_ID": "tenant",
}


class ProvisioningCredentialTest(unittest.TestCase):
    @patch.dict("os.environ", ACTIONS_ENV, clear=True)
    @patch("provisioning_credential.ClientAssertionCredential")
    def test_github_actions_uses_fresh_assertion_per_exchange(self, assertion_credential):
        module.provisioning_credential()
        tenant, client, fetch = assertion_credential.call_args.args
        self.assertEqual((tenant, client), ("tenant", "client"))
        with patch("provisioning_credential.urlopen") as urlopen:
            urlopen.side_effect = lambda *_args, **_kwargs: io.BytesIO(json.dumps({"value": "jwt"}).encode())
            self.assertEqual(fetch(), "jwt")
            self.assertEqual(fetch(), "jwt")
        self.assertEqual(urlopen.call_count, 2)
        request = urlopen.call_args.args[0]
        self.assertIn("&audience=api%3A%2F%2FAzureADTokenExchange", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer request-token")

    @patch.dict("os.environ", ACTIONS_ENV, clear=True)
    @patch("provisioning_credential.urlopen", return_value=io.BytesIO(b"{}"))
    @patch("provisioning_credential.ClientAssertionCredential")
    def test_missing_oidc_token_fails_clearly(self, assertion_credential, _urlopen):
        module.provisioning_credential()
        fetch = assertion_credential.call_args.args[2]
        with self.assertRaisesRegex(RuntimeError, "OIDC token"):
            fetch()

    @patch.dict("os.environ", {"ARM_CLIENT_ID": "client", "ARM_TENANT_ID": "tenant"}, clear=True)
    @patch("provisioning_credential.DefaultAzureCredential")
    @patch("provisioning_credential.ClientAssertionCredential")
    def test_outside_actions_uses_default_credential(self, assertion_credential, default_credential):
        self.assertIs(module.provisioning_credential(), default_credential.return_value)
        assertion_credential.assert_not_called()


if __name__ == "__main__":
    unittest.main()
