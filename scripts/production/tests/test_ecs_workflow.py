"""Guard against losing task configuration or accepting an unfinished rollout."""

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


render = load("render_ecs", "render-ecs-task-definition.py").render
deployment_ready = load("wait_ecs", "wait-ecs-express.py").deployment_ready
IMAGE = "964862484349.dkr.ecr.us-east-2.amazonaws.com/agenta-backend@sha256:" + "a" * 64
TASK = "arn:aws:ecs:us-east-2:964862484349:task-definition/default-agenta-backend-smoke:4"


class EcsWorkflowTests(unittest.TestCase):
    def test_new_task_changes_only_main_image(self):
        current = {
            "family": "default-agenta-backend-smoke",
            "revision": 3,
            "requiresCompatibilities": ["FARGATE"],
            "executionRoleArn": "arn:aws:iam::964862484349:role/ecsTaskExecutionRole",
            "containerDefinitions": [{
                "name": "Main", "image": "old:tag",
                "portMappings": [{"containerPort": 8080, "name": "main-8080-tcp"}],
                "environment": [{"name": "SUPABASE_URL", "value": "https://example.com"}],
                "secrets": [{"name": "OPENAI_API_KEY", "valueFrom": "arn:aws:secretsmanager:example"}],
            }],
        }
        updated = render(current, IMAGE, "default-agenta-backend-smoke")
        self.assertEqual(updated["containerDefinitions"][0]["image"], IMAGE)
        self.assertEqual(updated["containerDefinitions"][0]["secrets"],
                         current["containerDefinitions"][0]["secrets"])
        self.assertEqual(updated["containerDefinitions"][0]["environment"],
                         current["containerDefinitions"][0]["environment"])
        self.assertEqual(updated["executionRoleArn"], current["executionRoleArn"])
        self.assertNotIn("revision", updated)
        self.assertEqual(current["containerDefinitions"][0]["image"], "old:tag")

    def test_wait_requires_active_new_revision_without_deployment(self):
        service = {
            "cluster": "arn:aws:ecs:us-east-2:964862484349:cluster/default",
            "serviceName": "agenta-backend-smoke",
            "status": {"statusCode": "ACTIVE"},
            "currentDeployment": None,
            "activeConfigurations": [{"taskDefinitionArn": TASK}],
        }
        self.assertTrue(deployment_ready(service, TASK, "default", "agenta-backend-smoke"))
        service["currentDeployment"] = "in-progress"
        self.assertFalse(deployment_ready(service, TASK, "default", "agenta-backend-smoke"))
        service["currentDeployment"] = None
        service["activeConfigurations"][0]["taskDefinitionArn"] = "old"
        self.assertFalse(deployment_ready(service, TASK, "default", "agenta-backend-smoke"))


if __name__ == "__main__":
    unittest.main()
