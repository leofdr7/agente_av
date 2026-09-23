#!/usr/bin/env python3
"""Wait until ECS Express Mode serves the requested task revision."""

import json
import subprocess
import sys
import time


def deployment_ready(service: dict, task_arn: str, cluster: str, name: str) -> bool:
    if service.get("serviceName") != name:
        raise ValueError("ECS returned a different service")
    if service.get("cluster", "").split("/")[-1] != cluster:
        raise ValueError("ECS returned a different cluster")
    status = service.get("status", {}).get("statusCode")
    if status != "ACTIVE":
        raise ValueError(f"ECS service is {status}: {service.get('status', {}).get('statusReason', '')}")
    configurations = service.get("activeConfigurations", [])
    if service.get("currentDeployment") or len(configurations) != 1:
        return False
    return configurations[0].get("taskDefinitionArn") == task_arn


def main(service_arn: str, task_arn: str, cluster: str, name: str) -> None:
    deadline = time.monotonic() + 30 * 60
    while time.monotonic() < deadline:
        response = subprocess.run(
            ["aws", "ecs", "describe-express-gateway-service", "--service-arn", service_arn,
             "--output", "json"], check=True, capture_output=True, text=True,
        )
        service = json.loads(response.stdout)["service"]
        if deployment_ready(service, task_arn, cluster, name):
            print(f"ECS deployment active with {task_arn}")
            return
        print("Waiting for ECS Express deployment to finish", flush=True)
        time.sleep(20)
    raise TimeoutError(f"ECS did not stabilize on {task_arn} within 30 minutes")


if __name__ == "__main__":
    main(*sys.argv[1:])
