"""Contrato del comando de despliegue, sin acceso a GCP ni valores secretos."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy-backend.sh"


class DeployBackendTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.env = os.environ | {
            "PATH": f"{self.root}:{os.environ['PATH']}",
            "CALL_LOG": str(self.root / "calls.jsonl"),
            "GITHUB_OUTPUT": str(self.root / "output"),
            "GCP_PROJECT_ID": "test-project", "GCP_REGION": "us-central1",
            "GCP_RUNTIME_SERVICE_ACCOUNT": "runtime@test-project.iam.gserviceaccount.com",
            "BACKEND_IMAGE": "us-central1-docker.pkg.dev/test-project/agenta/backend@sha256:abc",
            "SUPABASE_URL": "https://example.supabase.co",
            "CLERK_JWKS_URL": "https://clerk.example.com/.well-known/jwks.json",
            "CLERK_AUTHORIZED_PARTIES": "https://app.example.com,https://app.vercel.app",
            "ANTHROPIC_MODEL": "test-model", "EMBEDDING_PROVIDER": "openai",
            "ANTHROPIC_API_KEY_VERSION": "2", "SUPABASE_SERVICE_KEY_VERSION": "3",
            "CLERK_SECRET_KEY_VERSION": "4", "OPENAI_API_KEY_VERSION": "5",
            "VOYAGE_API_KEY_VERSION": "6",
        }
        self.executable("gcloud", '''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
record = {"args": args}
for arg in args:
    if arg.startswith('--env-vars-file='):
        with open(arg.split('=', 1)[1]) as stream:
            record['config'] = json.load(stream)
with open(os.environ['CALL_LOG'], 'a') as stream:
    stream.write(json.dumps(record) + '\\n')
if args[:3] == ['run', 'services', 'describe']:
    print('https://agenta-api.example.run.app')
''')
        self.executable("curl", "#!/bin/sh\nexit \"${CURL_EXIT_CODE:-0}\"\n")

    def executable(self, name, content):
        path = self.root / name
        path.write_text(content)
        path.chmod(0o755)

    def run_script(self, **overrides):
        return subprocess.run(
            ["bash", str(SCRIPT)], env=self.env | overrides,
            text=True, capture_output=True, timeout=5,
        )

    def test_injects_exact_origins_and_versioned_secret_references(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in (self.root / "calls.jsonl").read_text().splitlines()]
        deploy = calls[0]
        self.assertEqual(deploy["config"]["CLERK_AUTHORIZED_PARTIES"], self.env["CLERK_AUTHORIZED_PARTIES"])
        self.assertEqual(deploy["config"]["AUTH_DISABLED"], "false")
        self.assertEqual(deploy["config"]["ENVIRONMENT"], "production")
        self.assertNotIn("OPENAI_API_KEY", deploy["config"])
        self.assertIn("--set-secrets=ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:2,SUPABASE_SERVICE_KEY=SUPABASE_SERVICE_KEY:3,CLERK_SECRET_KEY=CLERK_SECRET_KEY:4,OPENAI_API_KEY=OPENAI_API_KEY:5", deploy["args"])
        self.assertIn("--to-latest", calls[1]["args"])
        self.assertEqual((self.root / "output").read_text(), "url=https://agenta-api.example.run.app\n")
        temporary_config = next(arg.split("=", 1)[1] for arg in deploy["args"] if arg.startswith("--env-vars-file="))
        self.assertFalse(Path(temporary_config).exists())

    def test_voyage_selects_only_its_secret(self):
        result = self.run_script(EMBEDDING_PROVIDER="voyage", EMBEDDING_MODEL="voyage-4-lite")
        self.assertEqual(result.returncode, 0, result.stderr)
        command = (self.root / "calls.jsonl").read_text()
        self.assertIn("VOYAGE_API_KEY=VOYAGE_API_KEY:6", command)
        self.assertNotIn("OPENAI_API_KEY=", command)

    def test_invalid_config_never_contacts_gcloud(self):
        for overrides in [
            {"OPENAI_API_KEY_VERSION": "latest"}, {"ANTHROPIC_API_KEY_VERSION": ""},
            {"CLERK_AUTHORIZED_PARTIES": "http://localhost:3000"},
            {"CLERK_AUTHORIZED_PARTIES": "https://*.vercel.app"},
            {"CLERK_AUTHORIZED_PARTIES": "https://app.example.com/path"},
        ]:
            with self.subTest(overrides=overrides):
                result = self.run_script(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / "calls.jsonl").exists())

    def test_failed_readiness_blocks_frontend_output(self):
        result = self.run_script(CURL_EXIT_CODE="22")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "output").exists())


if __name__ == "__main__":
    unittest.main()
