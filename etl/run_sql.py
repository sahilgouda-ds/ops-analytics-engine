import sys
from sqlalchemy import text
from db import get_engine

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    sql = f.read()

with get_engine().begin() as conn:
    conn.execute(text(sql))

print("Done:", path)