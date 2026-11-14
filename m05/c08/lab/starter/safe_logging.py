import contextlib
import contextvars
import json
import logging
import re
import secrets
import unicodedata
from datetime import datetime, timezone

trace_var = contextvars.ContextVar("trace", default=None)

TRACEPARENT = re.compile(r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")
OWN_KEYS = {"ts", "level", "service", "trace_id", "span_id", "request_id"}
DENY_KEYS = {"message", "prompt", "answer", "address", "phone", "authorization"}
RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}

PLACE_WORDS = ("hoa sen man trang non lua vang sao mai duong mia ca ro che xanh dua xiem cau go xom vui "
               "ben song bai bien cho moi doi thong dau pho khu cong nghiep").split()


def fold(text):
    return "".join("d" if ch == "đ" else "D" if ch == "Đ" else unicodedata.normalize("NFD", ch)[0] for ch in text)


def new_traceparent(sampled=True):
    # TODO 1: trả về "00-<32 hex>-<16 hex>-<flags>" bằng secrets.token_hex; flags là "01" khi sampled, "00" nếu không.
    raise NotImplementedError


def parse_traceparent(header):
    # TODO 2: trả về {"version", "trace_id", "parent_id", "flags"} hoặc None.
    # Từ chối: sai hình dạng (TRACEPARENT), chữ hoa, version "ff", trace_id hoặc parent_id toàn số 0, header rỗng hoặc None.
    raise NotImplementedError


def child_traceparent(header):
    # TODO 3: giữ trace_id và flags của header hợp lệ, sinh parent_id mới (16 hex). Header không hợp lệ thì trả về new_traceparent().
    raise NotImplementedError


def redact_phone(text):
    # TODO 4: thay mỗi số điện thoại bằng "[phone]". Gợi ý: một biểu thức chính quy có lookbehind chặn ký tự chữ, số, dấu chấm, phẩy, gạch, cộng đứng trước
    # và lookahead chặn chữ số đứng sau; đầu số +84, 84, (+84) hoặc 0, rồi 3, 5, 7, 8 hoặc 9, rồi 8 chữ số, cho phép khoảng trắng, dấu chấm, gạch giữa các chữ số.
    raise NotImplementedError


def redact_address(text):
    # TODO 5: thay mỗi địa chỉ bằng "[address]". Khớp trên fold(text).lower() (cùng độ dài với text) rồi cắt theo vị trí trên text gốc.
    # Một địa chỉ gồm các đoạn: "số N" theo sau là đoạn khóa; "N/M" theo sau là tên địa danh; khóa (ngõ, ngách, hẻm, đường, phường, quận, phố, p., q., tp.)
    # cộng số hoặc địa danh trong PLACE_WORDS; "khu phố N"; "chung cư <địa danh>"; "tòa X"; "căn NNN". Các đoạn nối nhau bằng dấu phẩy hoặc khoảng trắng.
    raise NotImplementedError


def redact_text(text):
    # TODO 6: che số điện thoại trước, địa chỉ sau (thứ tự quan trọng vì "số 0901234567" không phải địa chỉ).
    raise NotImplementedError


def redact_value(value, key=""):
    # TODO 7: đi xuyên qua dict, list, tuple. Khóa trong OWN_KEYS giữ nguyên giá trị; khóa trong DENY_KEYS thành "[removed]";
    # chuỗi qua redact_text; kiểu khác (số, bool, None) giữ nguyên. Trả về bản mới, không sửa đối tượng đầu vào.
    raise NotImplementedError


class JsonFormatter(logging.Formatter):
    def __init__(self, service):
        super().__init__()
        self.service = service

    def format(self, record):
        # TODO 8: một dòng JSON gồm ts (ISO 8601 UTC), level, service, event (record.getMessage()), trace_id và span_id nếu trace_var đang gắn,
        # các trường extra của record (những khóa không nằm trong RESERVED) và "exc" khi có exc_info (self.formatException).
        # Che toàn bộ dict bằng redact_value trước khi json.dumps(..., ensure_ascii=False, default=str).
        raise NotImplementedError


def make_logger(name, service, stream):
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(service))
    log = logging.getLogger(name)
    log.handlers[:] = [handler]
    log.setLevel(logging.INFO)
    log.propagate = False
    return log


@contextlib.contextmanager
def bind(header):
    parsed = parse_traceparent(child_traceparent(header))
    token = trace_var.set({"trace_id": parsed["trace_id"], "span_id": parsed["parent_id"], "flags": parsed["flags"]})
    try:
        yield trace_var.get()
    finally:
        trace_var.reset(token)


def current_traceparent():
    ids = trace_var.get()
    return f"00-{ids['trace_id']}-{ids['span_id']}-{ids['flags']}"


def find_leaks(lines, secrets_):
    # TODO 9: trả về danh sách đã sắp xếp, không trùng, các giá trị trong secrets_ xuất hiện trong ít nhất một dòng.
    # Với giá trị chỉ gồm chữ số sau khi bỏ khoảng trắng, dấu chấm, gạch, ngoặc, dấu cộng và có từ 9 chữ số trở lên, so sánh cả dạng đã bỏ các ký tự đó
    # ở giá trị lẫn ở dòng, để bắt trường hợp số bị viết lại khác định dạng.
    raise NotImplementedError
