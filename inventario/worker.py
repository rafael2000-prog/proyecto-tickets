import redis, httpx, json, asyncio

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

async def procesar_cola():
    print("👷 Worker iniciado y esperando mensajes...")
    while True:
        # LINDEX mira el mensaje sin borrarlo (Seguridad)
        tarea = r.lindex("cola_inventario", 0)
        
        if tarea:
            data = json.loads(tarea)
            asiento_id = data["asiento_id"]
            print(f"📦 Detectado asiento #{asiento_id} en la cola. Intentando sincronizar...")
            
            try:
                async with httpx.AsyncClient() as client:
                    # INTENTO DE ENVÍO
                    res = await client.post(f"http://localhost:8001/confirmar-final/{asiento_id}", timeout=2.0)
                    
                    print(f"📡 Respuesta del Inventario (8001): {res.status_code} - {res.json()}")

                    if res.status_code == 200:
                        r.lpop("cola_inventario") # AHORA SÍ lo borramos
                        print(f"✅ ÉXITO: Asiento {asiento_id} guardado en Postgres y borrado de Redis.")
                    else:
                        print(f"⚠️ El Inventario rechazó el dato. ¿Existe el asiento {asiento_id}?")
            
            except Exception as e:
                print(f"⏳ Inventario (8001) sigue apagado o inaccesible... reintentando.")
        
        await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(procesar_cola())