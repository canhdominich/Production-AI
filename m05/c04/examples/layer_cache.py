import re
import time

from _dock import TMP, build, make_context, STACK

ctx = make_context(TMP / "ctx_cache")
app_file = ctx / "c04" / "stack" / "app" / "api.py"
dep_file = ctx / "c04" / "stack" / "pyproject.toml"
files = {"bad": "c04/stack/variants/Dockerfile.badorder", "good": "c04/stack/variants/Dockerfile.goodorder"}
res = {}
for name, df in files.items():
    build(f"m05c04-cache-{name}:1", ctx / df, context=ctx)
    app_file.write_text(app_file.read_text() + f"\nBUILD_MARK = '{name}-{time.time()}'\n")
    t, log = build(f"m05c04-cache-{name}:2", ctx / df, context=ctx)
    res[name] = (t, log.count("CACHED"), "Downloading" in log or "Installed" in log)

print("change one line in app/api.py, rebuild:")
print(f"{'Dockerfile order':<34}{'seconds':>9}{'cached steps':>14}{'reinstalled deps':>18}")
for name, label in (("bad", "COPY everything, then uv sync"), ("good", "COPY lock file, uv sync, then code")):
    t, c, reinstall = res[name]
    print(f"{label:<34}{t:>9.1f}{c:>14}{('yes' if reinstall else 'no'):>18}")
