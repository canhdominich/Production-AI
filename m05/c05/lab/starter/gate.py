import json
import sys


def pass_rate(results):
    # TODO 1: trả về tỉ lệ ca có passed là True, từ 0.0 đến 1.0
    raise NotImplementedError


def by_category(results):
    # TODO 2: trả về dict {tên nhóm: tỉ lệ đạt của nhóm đó}
    raise NotImplementedError


def decide(baseline, candidate, max_drop=0.05, max_category_drop=0.17, min_cases=20):
    # TODO 3: trả về {"ok": bool, "reasons": [...]}
    # - ít hơn min_cases ca: thêm "too_few_cases: ..."
    # - tỉ lệ chung giảm quá max_drop: thêm "overall_drop: ..."
    # - nhóm nào giảm quá max_category_drop: thêm "category_drop:<nhóm>: ..."
    # Cho sai số nhỏ 1e-9 khi so sánh số thực.
    raise NotImplementedError


def check_workflow(doc):
    # TODO 4: trả về danh sách mã lỗi của workflow, danh sách rỗng nếu hợp lệ:
    # "missing_job" (thiếu job eval-gate hoặc deploy, trả về ngay),
    # "deploy_not_after_gate" (deploy không có eval-gate trong needs),
    # "gate_continue_on_error" (một step của eval-gate có continue-on-error),
    # "deploy_not_main_only" (điều kiện if của deploy không nhắc refs/heads/main),
    # "secret_in_run" (một lệnh run chứa secrets.)
    raise NotImplementedError


def main(argv):
    baseline = json.load(open(argv[0], encoding="utf-8"))
    candidate = json.load(open(argv[1], encoding="utf-8"))
    # TODO 5: dùng decide, in PASS hoặc BLOCK cùng từng lý do, trả về 0 khi qua và 1 khi bị chặn
    result = decide(baseline, candidate)
    print("gate:", "PASS" if result["ok"] else "BLOCK")
    for reason in result["reasons"]:
        print(" -", reason)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
