import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
print(f"Mensajes en cola: {r.llen('cola_inventario')}")
print(f"Contenido: {r.lrange('cola_inventario', 0, -1)}")