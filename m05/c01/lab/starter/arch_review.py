import re
import sys
from pathlib import Path

REQUIRED_NODES = ["User", "Caddy", "API", "Gateway", "Worker", "PostgreSQL", "Redis", "Provider", "Observability"]
SECTIONS = ["status", "context", "options", "decision", "consequences"]
MODES = ("sync", "streaming", "job")

NODE_DEF = re.compile(r'(\w+)(?:\[\(|\[|\(\(|\(|\{)"([^"]*)"(?:\)\]|\]|\)\)|\)|\})')
EDGE = re.compile(r"(\w+)\s*(?:-->|-\.->|==>)\s*(?:\|([^|]*)\|\s*)?(\w+)")


def parse_containers(text):
    """Return (nodes, edges): nodes maps id to label, edges is a list of (source, target, label)."""
    # TODO 1: đọc từng dòng Mermaid. Nút có dạng ID["nhãn"], ID[("nhãn")] hoặc ID(("nhãn")); cạnh có dạng A -->|nhãn| B.
    # Bỏ phần sau %%, bỏ hậu tố :::class; nút chỉ xuất hiện trong cạnh thì lấy chính id làm nhãn.
    raise NotImplementedError


def check_architecture(text):
    """Return a sorted list of problems; an empty list means the diagram follows the course rules."""
    # TODO 2: trả về danh sách lỗi (chuỗi) khi sơ đồ vi phạm quy tắc của khóa:
    #   thiếu một nút trong REQUIRED_NODES; cạnh không có nhãn; nút khác Gateway gọi thẳng Provider;
    #   API nối thẳng Worker; API không đưa job vào Redis hoặc PostgreSQL; Worker không nối Redis;
    #   Worker không gọi Gateway; Gateway không ghi usage vào PostgreSQL; thiếu Caddy tới API hoặc User tới Caddy;
    #   API, Gateway, Worker chưa cùng báo cho Observability.
    raise NotImplementedError


def parse_adr(text):
    """Return {'title': ..., 'status': ..., 'context': ..., ...} with lower-case section names."""
    # TODO 3: lấy tiêu đề từ dòng bắt đầu bằng "# " và nội dung mỗi mục "## Tên" (tên viết thường) làm giá trị.
    raise NotImplementedError


def adr_mode(adr):
    """The mode named on the first line of the Decision section, or None."""
    first = (adr.get("decision") or "").strip().splitlines()[:1]
    found = [m for m in MODES if first and m in first[0].lower()]
    return found[0] if len(found) == 1 else None


def check_adr(text):
    adr = parse_adr(text)
    problems = []
    # TODO 4: thêm lỗi khi: tiêu đề không bắt đầu bằng "ADR-"; thiếu một mục trong SECTIONS;
    #   status không phải Proposed, Accepted hoặc Superseded; context có ít hơn hai con số;
    #   options không nhắc đủ sync, streaming, job; dòng đầu của decision không gọi tên đúng một chế độ;
    #   consequences có ít hơn hai dòng gạch đầu dòng.
    raise NotImplementedError


def choose_mode(p95_seconds, user_waiting, partial_useful, proxy_timeout_s=60):
    """sync, streaming or job from the 95th percentile duration and who is waiting."""
    # TODO 5: người dùng không chờ thì job; p95 từ nửa timeout của proxy trở lên thì job;
    #   p95 không quá 2 giây thì sync; còn lại streaming nếu đọc dở có ích, ngược lại sync.
    raise NotImplementedError


def audit(folder):
    folder = Path(folder)
    report = {}
    arch = folder / "architecture.mmd"
    report["architecture.mmd"] = check_architecture(arch.read_text(encoding="utf-8")) if arch.exists() else ["file not found"]
    for f in sorted(folder.glob("adr-*.md")):
        report[f.name] = check_adr(f.read_text(encoding="utf-8"))
    return report


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "deliverables"
    result = audit(folder)
    for name, problems in result.items():
        print(f"{name:<32}", "ok" if not problems else f"{len(problems)} problem(s)")
        for p in problems:
            print("   -", p)
    modes = {f.name: adr_mode(parse_adr(f.read_text(encoding="utf-8"))) for f in sorted(Path(folder).glob("adr-*.md"))}
    print("decisions:", modes)
    sys.exit(1 if any(result.values()) else 0)
