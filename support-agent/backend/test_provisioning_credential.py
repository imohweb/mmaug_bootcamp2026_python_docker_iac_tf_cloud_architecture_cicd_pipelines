import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import provisioning_credential as module

ACTIONS_ENV = {
    "ACTIONS_ID_TOKEN_REQUEST_URL": "https://actions.example/token?api-version=2.0",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-token",
    "ARM_CLIENT_ID": "client",
    "ARM_TENANT_ID": "tenant",
}


class ProvisioningCredentialTest(unittest.TestCase):
    @patch.dict("os.environ", ACTIONS_ENV, clear=True)
    @patch("provisioning_credential.DefaultAzureCredential")
    @patch("provisioning_credential.ClientAssertionCredential")
    def test_github_actions_uses_fresh_assertion_per_exchange(self, assertion_credential, default_credential):
        self.assertIs(module.provisioning_credential(), assertion_credential.return_value)
        default_credential.assert_not_called()
        tenant, client, fetch = assertion_credential.call_args.args
        self.assertEqual((tenant, client), ("tenant", "client"))
        with patch("provisioning_credential.urlopen") as urlopen:
            urlopen.side_effect = [
                io.BytesIO(json.dumps({"value": value}).encode())
                for value in ("first-jwt", "fresh-jwt")
            ]
            self.assertEqual(fetch(), "first-jwt")
            self.assertEqual(fetch(), "fresh-jwt")
        self.assertEqual(urlopen.call_count, 2)
        request = urlopen.call_args.args[0]
        self.assertEqual(parse_qs(urlsplit(request.full_url).query), {
            "api-version": ["2.0"], "audience": [module.AUDIENCE],
        })
        self.assertEqual(request.get_header("Authorization"), "Bearer " + ACTIONS_ENV["ACTIONS_ID_TOKEN_REQUEST_TOKEN"])
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)

    @patch.dict("os.environ", ACTIONS_ENV, clear=True)
    @patch("provisioning_credential.ClientAssertionCredential")
    def test_missing_oidc_token_fails_clearly(self, assertion_credential):
        module.provisioning_credential()
        fetch = assertion_credential.call_args.args[2]
        for body in (b"{}", b'{"value": ""}'):
            with self.subTest(body=body), patch(
                "provisioning_credential.urlopen", return_value=io.BytesIO(body)
            ):
                with self.assertRaisesRegex(RuntimeError, "OIDC token"):
                    fetch()

    @patch.dict("os.environ", ACTIONS_ENV, clear=True)
    @patch("provisioning_credential.DefaultAzureCredential")
    @patch("provisioning_credential.ClientAssertionCredential")
    def test_oidc_request_failure_does_not_fall_back_to_stale_cli(self, assertion_credential, default_credential):
        module.provisioning_credential()
        fetch = assertion_credential.call_args.args[2]
        with patch("provisioning_credential.urlopen", side_effect=HTTPError(
            ACTIONS_ENV["ACTIONS_ID_TOKEN_REQUEST_URL"], 403, "Forbidden", {}, None
        )):
            with self.assertRaises(HTTPError):
                fetch()
        default_credential.assert_not_called()

    @patch.dict("os.environ", {}, clear=True)
    @patch("provisioning_credential.DefaultAzureCredential")
    @patch("provisioning_credential.ClientAssertionCredential")
    def test_outside_actions_uses_default_credential(self, assertion_credential, default_credential):
        self.assertIs(module.provisioning_credential(), default_credential.return_value)
        assertion_credential.assert_not_called()

    @patch.dict("os.environ", ACTIONS_ENV, clear=True)
    @patch("provisioning_credential.ClientAssertionCredential")
    def test_azure_settings_and_url_without_query(self, assertion_credential):
        with patch.dict("os.environ", {
            "ARM_CLIENT_ID": " ", "ARM_TENANT_ID": "",
            "AZURE_CLIENT_ID": " azure-client ", "AZURE_TENANT_ID": "azure-tenant",
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://actions.example/token",
        }):
            module.provisioning_credential()
        tenant, client, fetch = assertion_credential.call_args.args
        self.assertEqual((tenant, client), ("azure-tenant", "azure-client"))
        with patch("provisioning_credential.urlopen", return_value=io.BytesIO(b'{"value":"jwt"}')) as urlopen:
            self.assertEqual(fetch(), "jwt")
        self.assertEqual(parse_qs(urlsplit(urlopen.call_args.args[0].full_url).query),
                         {"audience": [module.AUDIENCE]})


if __name__ == "__main__":
    unittest.main()
