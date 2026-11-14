def ttft(rec):
    # TODO 1: trả về thời gian từ lúc gửi tới token đầu tiên
    raise NotImplementedError


def tpot(rec):
    # TODO 2: thời gian trung bình giữa hai token liên tiếp (0.0 nếu chỉ có một token)
    raise NotImplementedError


def window(recs):
    # TODO 3: từ lúc gửi sớm nhất tới token cuối cùng muộn nhất của cả nhóm
    raise NotImplementedError


def throughput(recs):
    # TODO 4: tổng số token chia cho độ dài cửa sổ
    raise NotImplementedError


def meets_slo(rec, slo_ttft, slo_tpot):
    # TODO 5: đúng khi cả TTFT và TPOT đều không vượt ngưỡng
    raise NotImplementedError


def goodput(recs, slo_ttft, slo_tpot):
    # TODO 6: chỉ đếm token của request đạt SLO, chia cho cùng cửa sổ
    raise NotImplementedError


def max_concurrency_within_slo(curve, min_ok_fraction=0.9):
    # TODO 7: duyệt tăng dần theo concurrency, dừng ở điểm đầu tiên có ok_fraction thấp hơn ngưỡng
    raise NotImplementedError
