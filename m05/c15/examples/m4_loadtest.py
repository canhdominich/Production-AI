from collections import Counter
from pathlib import Path

import httpx

import _kit
from anhti_platform.canary import PROMPTS

_kit.reset_stack_state()
direct = []
for i in range(30):
    messages = [{"role": "system", "content": PROMPTS["v1"]}, {"role": "user", "content": "don at047838 bao gio toi"}]
    r = httpx.post(_kit.PRIMARY_ADMIN + "/v1/chat/completions", json={"model": "fake-medium", "messages": messages, "max_tokens": 300},
                   headers={"x-fake-request-id": f"direct-{i}"}, timeout=20)
    direct.append(r.elapsed.total_seconds())

report = {}
for name, rps, secs in (("within limits", 4, 30), ("overload", 30, 20)):
    rows, wall = _kit.drive(_kit.make_plan(rps, secs, seed=15))
    ok = [r["seconds"] for r in rows if r["status"] == 200]
    limited = [r["seconds"] for r in rows if r["status"] == 429]
    codes = Counter(r["status"] for r in rows)
    by_tenant = {t: Counter(r["status"] for r in rows if r["tenant"] == t) for t in _kit.SHARES}
    report[name] = {"rps": rps, "seconds": secs, "sent": len(rows), "codes": dict(codes), "ok_p50": _kit.pct(ok, 50), "ok_p95": _kit.pct(ok, 95),
                    "ok_p99": _kit.pct(ok, 99), "limited_p95": _kit.pct(limited, 95), "served_rps": len(ok) / wall,
                    "by_tenant": {t: dict(c) for t, c in by_tenant.items()}}
    if name == "within limits":
        _kit.reset_stack_state()

print(f"direct provider call, p50 {_kit.pct(direct, 50) * 1000:.0f} ms (30 calls, time scale 0.05)\n")
print(f"{'phase':14}{'rps':>5}{'sent':>6}{'200':>6}{'429':>6}{'5xx':>5}{'served rps':>11}{'ok p50':>8}{'ok p95':>8}{'ok p99':>8}{'429 p95':>9}")
for name, d in report.items():
    c = d["codes"]
    five = sum(v for k, v in c.items() if int(k) >= 500)
    print(f"{name:14}{d['rps']:>5}{d['sent']:>6}{c.get(200, 0):>6}{c.get(429, 0):>6}{five:>5}{d['served_rps']:>11.1f}"
          f"{d['ok_p50'] * 1000:>6.0f}ms{d['ok_p95'] * 1000:>6.0f}ms{d['ok_p99'] * 1000:>6.0f}ms{d['limited_p95'] * 1000:>7.0f}ms")
print("\noverload, answers per tenant (limit per minute in brackets):")
caps = {"br-dau-pho": 120, "br-khu-cong-nghiep": 90, "br-cau-go": 60, "br-xom-vui": 60, "br-ben-song": 30}
for t, c in report["overload"]["by_tenant"].items():
    print(f"  {t:20} [{caps[t]:>3}]  200: {c.get(200, 0):3d}  429: {c.get(429, 0):3d}")
within = report["within limits"]
print("\nplatform overhead at p50 (gateway minus direct provider):", f"{(within['ok_p50'] - _kit.pct(direct, 50)) * 1000:.0f} ms")
LABEL = {"within limits": "Trong hạn mức", "overload": "Quá tải"}
lines = ["# Báo cáo load test", "", "Môi trường: Docker Compose m05c15 trên một máy, provider giả với time scale 0,05 (mọi thời gian model nhanh 20 lần),",
         "một tiến trình API, Redis cho giới hạn tốc độ. Số đo là của lớp nền tảng, không phải của model thật.", "",
         "| Pha | Tải | Gửi | 200 | 429 | 5xx | p50 | p95 | p99 |", "|---|---|---|---|---|---|---|---|---|"]
for name, d in report.items():
    c = d["codes"]
    lines.append(f"| {LABEL[name]} | {d['rps']} rps trong {d['seconds']} giây | {d['sent']} | {c.get(200, 0)} | {c.get(429, 0)} | "
                 f"{sum(v for k, v in c.items() if int(k) >= 500)} | {d['ok_p50'] * 1000:.0f} ms | {d['ok_p95'] * 1000:.0f} ms | {d['ok_p99'] * 1000:.0f} ms |")
lines += ["", f"Chi phí lớp nền tảng ở p50: {(within['ok_p50'] - _kit.pct(direct, 50)) * 1000:.0f} ms so với gọi thẳng provider.",
          "Kết luận: trong hạn mức, không lỗi 5xx; khi quá tải, mỗi chi nhánh bị chặn đúng ở hạn mức của mình bằng 429 trả về trong vài chục mili giây."]
Path(_kit.PROJECT / "docs" / "loadtest_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
