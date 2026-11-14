import re
import sys
from pathlib import Path

import yaml

DEP_FILES = ("pyproject.toml", "uv.lock", "requirements")
INSTALL = re.compile(r"\b(uv sync|uv pip install|pip install)\b")
SECRET_KEYS = ("PASSWORD", "SECRET", "TOKEN", "API_KEY")
DEFAULT_PORTS = {"5432", "6379", "8000", "8080"}


def parse_dockerfile(text):
    # TODO 1: ghép các dòng kết thúc bằng "\", bỏ dòng trống và chú thích.
    # Mỗi FROM mở một stage: {"base": "python:3.12-slim", "name": "builder" (chữ thường, "" nếu không có AS), "instructions": [("RUN", "uv sync ..."), ...]}.
    # Tên lệnh viết hoa; trả về danh sách stage theo thứ tự xuất hiện.
    raise NotImplementedError


def check_dockerfile(text):
    # TODO 2: trả về danh sách lỗi đã sắp xếp, không trùng. Các quy tắc và câu chữ lỗi:
    # - dưới 2 stage: "single stage: build tools stay in the final image, use a builder stage"
    # - base không có tag hoặc tag latest (trừ tên stage trước đó và scratch): f"base image not pinned to a tag: {base}"
    # - trong một stage, COPY/ADD mã nguồn (không phải pyproject.toml, uv.lock, requirements*, và không có --from=) đứng trước RUN cài thư viện (uv sync, uv pip install, pip install):
    #   f"stage {name hoặc base}: application code copied before dependencies are installed, cache is lost on every edit"
    # - stage cuối không có USER hoặc USER cuối là root/0: "final stage runs as root, add a non-root USER"
    raise NotImplementedError


def parse_compose(text):
    # TODO 3: dùng yaml.safe_load. Trả về {"services": {tên: {"image", "build" (bool), "ports" (list str), "healthcheck" (bool),
    # "depends_on" (dict tên -> condition, danh sách thì condition là service_started), "volumes" (list str), "restart" (chuỗi, "" khi không khai báo), "environment"}}, "volumes": [tên volume khai báo ở cấp cao nhất]}
    raise NotImplementedError


def check_compose(text):
    # TODO 4: trả về danh sách lỗi đã sắp xếp, không trùng, câu chữ chính xác như test mong đợi:
    # - f"{name}: long-running service has no healthcheck" (mọi dịch vụ không khai báo restart: "no")
    # - f"{name}: depends_on {dep} needs condition {want}, found {cond}" với want là service_completed_successfully khi dep khai báo restart: "no" và không có healthcheck, ngược lại service_healthy
    # - f"{name}: image not pinned to a tag: {image}" (bỏ qua dịch vụ có build)
    # - f"{name}: published port {p} is not bound to 127.0.0.1" và f"{name}: host port {port} is a default port, use a project port"
    # - f"{name}: database data is not on a named volume" cho image chứa postgres hoặc pgvector, nếu không có volume tên đã khai báo gắn vào /var/lib/postgresql...
    # - f"{name}: secret {key} written in the file, read it from the environment" khi khóa chứa PASSWORD, SECRET, TOKEN, API_KEY mà giá trị không có "${"
    raise NotImplementedError


def weights_strategy(size_mb, hosts=1, air_gapped=False):
    # TODO 5: "bake" khi air_gapped hoặc size_mb dưới 150; "volume" khi chỉ có một máy; ngược lại "mirror".
    raise NotImplementedError


def review(root):
    # TODO 6: đọc Dockerfile và compose.yaml trong thư mục root, trả về danh sách dòng báo cáo.
    # Mỗi tệp một dòng "Dockerfile: ok" hoặc "Dockerfile: N problem(s)" rồi mỗi lỗi một dòng "  - lỗi". Tệp thiếu là một lỗi "Dockerfile missing".
    raise NotImplementedError


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    lines = review(target)
    print("\n".join(lines))
    sys.exit(0 if all("problem" not in x and "missing" not in x for x in lines) else 1)
