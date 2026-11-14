from pathlib import Path

import yaml

GPU_KEY = "nvidia.com/gpu"

MANIFESTS = {
    "limits only": """
spec:
  containers:
  - name: vllm
    resources:
      limits: {nvidia.com/gpu: 1, cpu: "4", memory: 24Gi}
""",
    "requests equal limits": """
spec:
  containers:
  - name: vllm
    resources:
      requests: {nvidia.com/gpu: 1}
      limits: {nvidia.com/gpu: 1}
""",
    "requests only": """
spec:
  containers:
  - name: vllm
    resources:
      requests: {nvidia.com/gpu: 1}
""",
    "requests differ from limits": """
spec:
  containers:
  - name: vllm
    resources:
      requests: {nvidia.com/gpu: 1}
      limits: {nvidia.com/gpu: 2}
""",
    "half a GPU": """
spec:
  containers:
  - name: vllm
    resources:
      limits: {nvidia.com/gpu: 0.5}
""",
}


def check(text):
    problems = []
    for c in yaml.safe_load(text)["spec"]["containers"]:
        res = c.get("resources", {})
        req, lim = res.get("requests", {}), res.get("limits", {})
        if GPU_KEY in req and GPU_KEY not in lim:
            problems.append("GPU in requests without limits")
        if GPU_KEY in req and GPU_KEY in lim and req[GPU_KEY] != lim[GPU_KEY]:
            problems.append("GPU requests and limits differ")
        for value in (req.get(GPU_KEY), lim.get(GPU_KEY)):
            if value is not None and int(value) != value:
                problems.append(f"GPU quantity {value} is not a whole number")
    return problems


for name, text in MANIFESTS.items():
    found = check(text)
    print(f"{name:<28} {'ok' if not found else 'REJECTED: ' + '; '.join(found)}")

file_problems = check(Path("vllm_pod.yaml").read_text(encoding="utf-8"))
print(f"{'vllm_pod.yaml':<28} {'ok' if not file_problems else 'REJECTED: ' + '; '.join(file_problems)}")
