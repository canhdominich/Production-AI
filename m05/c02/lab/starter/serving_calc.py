HOURS_PER_MONTH = 730


def resolve_endpoint(profiles, name, env):
    # TODO 1: lấy profile `name`, cho biến môi trường CHAT_BASE_URL, CHAT_MODEL, CHAT_API_KEY ghi đè.
    # Bỏ dấu "/" cuối của base_url, báo ValueError nếu base_url không kết thúc bằng "/v1".
    # Trả về dict có bốn khóa: base_url, model, api_key, extra (bản sao của cfg["extra"], mặc định {}).
    raise NotImplementedError


def api_cost_per_request(price, avg_in, avg_out):
    # TODO 2: chi phí API của một yêu cầu trung bình (USD), giá tính theo một triệu token.
    raise NotImplementedError


def selfhost_fixed_cost(gpu_per_hour, gpus, ops_per_month, hours=HOURS_PER_MONTH):
    # TODO 3: chi phí cố định mỗi tháng của máy tự host: tiền thuê GPU cả tháng cộng công vận hành.
    raise NotImplementedError


def breakeven_requests(fixed_cost, per_request_api):
    # TODO 4: số yêu cầu mỗi tháng mà chi phí API bằng chi phí cố định. Báo ValueError nếu per_request_api <= 0.
    raise NotImplementedError


def required_utilization(requests_per_month, avg_out, tokens_per_second, gpus, hours=HOURS_PER_MONTH):
    # TODO 5: tỉ lệ công suất phải dùng (0 đến 1 hoặc hơn) để phục vụ số yêu cầu đó, tính theo token đầu ra.
    raise NotImplementedError


def decide(requests_per_month, per_request_api, fixed_cost, utilization, max_utilization=0.6):
    # TODO 6: trả về "api" nếu API không đắt hơn chi phí cố định; "self-host" nếu tự host rẻ hơn và
    # utilization không vượt max_utilization; ngược lại "self-host-needs-more-gpus".
    raise NotImplementedError
