import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
print(f"Mensajes en cola (principal): {r.llen('cola_inventario')}")
print(f"Contenido (principal): {r.lrange('cola_inventario', 0, -1)}")
print(f"Mensajes en cola (processing): {r.llen('cola_inventario_processing')}")
print(f"Contenido (processing): {r.lrange('cola_inventario_processing', 0, -1)}")
print(f"Mensajes en cola (dead-letter): {r.llen('cola_inventario_muerta')}")
print(f"Contenido (dead-letter): {r.lrange('cola_inventario_muerta', 0, -1)}")