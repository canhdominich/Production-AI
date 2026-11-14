import json
from pathlib import Path

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

CONTENT_ATTRIBUTES = {"gen_ai.input.messages", "gen_ai.output.messages", "gen_ai.system_instructions", "gen_ai.tool.call.arguments", "gen_ai.tool.call.result", "gen_ai.retrieval.query.text"}


def span_name(operation, subject=None):
    # TODO 1: trả về "operation subject" (ví dụ "chat fake-small"); không có subject thì chỉ trả về operation
    raise NotImplementedError


def inference_attributes(provider, model, input_tokens=None, output_tokens=None, finish_reason=None, max_tokens=None):
    # TODO 2: dict thuộc tính cho một lời gọi chat theo tên hiện hành; bỏ các giá trị None;
    # gen_ai.response.finish_reasons là một danh sách; không dùng gen_ai.system hay gen_ai.usage.prompt_tokens
    raise NotImplementedError


def tool_attributes(tool_name, call_id=None, error_type=None):
    # TODO 3: thuộc tính của span execute_tool; chỉ thêm gen_ai.tool.call.id và error.type khi có giá trị
    raise NotImplementedError


def validate_span(span, snapshot, allow_content=False):
    # TODO 4: trả về danh sách lỗi (chuỗi) theo đúng mẫu trong file test:
    #   thiếu thuộc tính bắt buộc, tên cũ (older_names), thuộc tính gen_ai.* lạ, nội dung prompt khi chưa bật opt-in.
    #   Span không có gen_ai.operation.name thì bỏ qua.
    raise NotImplementedError


class JsonlSpanExporter(SpanExporter):
    def __init__(self, path):
        self.path = Path(path)
        self.path.write_text("", encoding="utf-8")

    def export(self, spans):
        # TODO 5: ghi mỗi span thành một dòng JSON vào self.path với các khóa
        #   trace_id (32 hex), span_id (16 hex), parent_span_id (hoặc None), name, kind (tên), start_ns, end_ns, status (tên), attributes
        raise NotImplementedError

    def shutdown(self):
        pass


def trace_tree(spans):
    # TODO 6: trả về danh sách dòng, mỗi dòng là tên span thụt hai dấu cách theo độ sâu; con xếp theo start_ns
    raise NotImplementedError


def token_totals(spans, snapshot):
    # TODO 7: cộng token vào/ra theo anhti.feature; chấp nhận cả tên cũ lẫn tên hiện hành; bỏ qua span không có token
    #   kết quả dạng {"chat": (tổng_vào, tổng_ra)}
    raise NotImplementedError
