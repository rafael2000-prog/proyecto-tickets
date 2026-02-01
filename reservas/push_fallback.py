import redis
import os

FALLBACK_FILE = "outbox_fallback.jsonl"

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

if not os.path.exists(FALLBACK_FILE):
    print("No hay archivo fallback.")
    exit(0)

pushed = 0
with open(FALLBACK_FILE, "r", encoding="utf-8") as f:
    lines = [l.strip() for l in f if l.strip()]

for line in lines:
    try:
        r.rpush("cola_inventario", line)
        pushed += 1
    except Exception as e:
        print(f"Error empujando a Redis: {e}")
        break

if pushed == len(lines):
    # Renombramos el archivo para indicar que fue procesado
    os.rename(FALLBACK_FILE, FALLBACK_FILE + ".processed")
    print(f"OK: {pushed} mensajes reencolados y archivo renombrado.")
else:
    print(f"Parcialmente empujados: {pushed} mensajes. Manteniendo archivo para reintento.")