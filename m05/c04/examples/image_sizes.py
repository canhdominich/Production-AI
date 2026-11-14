from _dock import STACK, build, image_info, sh

t_naive, log_naive = build("m05c04-naive:1", STACK / "variants" / "Dockerfile.naive")
t_multi, log_multi = build("m05c04-app:1", STACK / "Dockerfile")
build("m05c04-builder:1", STACK / "Dockerfile", target="builder")

rows = [("naive, one stage, runs as root", "m05c04-naive:1"), ("multi-stage, non-root", "m05c04-app:1"), ("builder stage (thrown away)", "m05c04-builder:1")]
print(f"{'image':<34}{'size MB':>9}{'layers':>8}  user")
for name, tag in rows:
    i = image_info(tag)
    print(f"{name:<34}{i['mb']:>9.0f}{i['layers']:>8}  {i['user']}")

print("python:3.12-slim base on disk:", f"{image_info('python:3.12-slim')['mb']:.0f} MB")
r = sh("docker", "run", "--rm", "m05c04-app:1", "python", "-c", "import fastapi, uvicorn, psycopg, redis; print('runtime imports ok')")
print(r.stdout.strip())
