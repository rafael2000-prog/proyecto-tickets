import redis.asyncio as redis, httpx, json, asyncio

# Usamos un cliente asíncrono para no bloquear el bucle de eventos
r = redis.from_url("redis://localhost:6379", decode_responses=True)

SOURCE_QUEUE = "cola_inventario"
PROCESSING_QUEUE = "cola_inventario_processing"
DEAD_LETTER_QUEUE = "cola_inventario_muerta"
MAX_RETRIES = 50

async def procesar_cola():
    print("👷 Worker asíncrono iniciado y esperando mensajes...")
    while True:
        try:
            # BRPOPLPUSH: mueve atomáticamente de SOURCE_QUEUE a PROCESSING_QUEUE y devuelve el elemento
            tarea = await r.brpoplpush(SOURCE_QUEUE, PROCESSING_QUEUE, timeout=5)

            if not tarea:
                # Tiempo de espera cumplido, reintentar
                await asyncio.sleep(1)
                continue

            data = json.loads(tarea)
            asiento_id = data.get("asiento_id")
            retries = data.get("retries", 0)

            print(f"📦 Procesando asiento #{asiento_id} (intento {retries})...")

            try:
                async with httpx.AsyncClient() as client:
                    # Si no se había notificado en el flujo de reservas, intentamos notificar ahora
                    notificado = data.get("notificado", False)
                    if not notificado:
                        try:
                            await client.post("http://localhost:8003/enviar", json={"asiento": asiento_id}, timeout=2.0)
                            notificado = True
                            data['notificado'] = True
                            print(f"📧 Notificación enviada para asiento {asiento_id} durante reintento.")
                        except Exception:
                            print(f"⚠️ No fue posible notificar para asiento {asiento_id} en este intento.")

                    # Llamamos a confirmar-final con el flag notificado
                    notificado_param = "true" if notificado else "false"
                    res = await client.post(f"http://localhost:8001/confirmar-final/{asiento_id}?notificado={notificado_param}", timeout=3.0)

                    try:
                        respuesta_json = res.json()
                    except Exception:
                        respuesta_json = res.text
                    print(f"📡 Respuesta del Inventario (8001): {res.status_code} - {respuesta_json}")

                    if res.status_code == 200:
                        # Si el inventario devolvió detalles, mostramos si la DB guardó la notificación
                        if isinstance(respuesta_json, dict):
                            print(f"🔎 db_notificado: {respuesta_json.get('db_notificado')}")

                        # Éxito: borramos de la lista de processing y limpiamos el lock redis
                        await r.lrem(PROCESSING_QUEUE, 1, tarea)
                        await r.delete(f"asiento:{asiento_id}")
                        print(f"✅ ÉXITO: Asiento {asiento_id} guardado en Postgres y borrado de Redis.")
                    else:
                        # El inventario devolvió un error --> si es 4xx, lo consideramos definitivo y mandamos a dead-letter
                        if 400 <= res.status_code < 500:
                            print(f"❌ Error definitivo del inventario para asiento {asiento_id}: {res.status_code}")
                            await r.lrem(PROCESSING_QUEUE, 1, tarea)
                            await r.rpush(DEAD_LETTER_QUEUE, json.dumps(data))
                        else:
                            # 5xx: problema temporal del inventario -> reencolamos al origen para intentar continuamente
                            print(f"⚠️ Inventario temporalmente con fallo ({res.status_code}). Reencolando para reintento continuo.")
                            await r.lrem(PROCESSING_QUEUE, 1, tarea)
                            await r.rpush(SOURCE_QUEUE, json.dumps(data))
                            # Esperamos un poco antes de procesar la siguiente para evitar tight-loop
                            await asyncio.sleep(3)
            except Exception as e:
                # Problema de conexión con inventario: reencolamos con incremento de retries
                print(f"⏳ Inventario (8001) inaccesible... reencolando (error: {e})")
                data['retries'] = retries + 1
                new_msg = json.dumps(data)
                await r.lrem(PROCESSING_QUEUE, 1, tarea)
                if data['retries'] >= MAX_RETRIES:
                    await r.rpush(DEAD_LETTER_QUEUE, new_msg)
                    print(f"❌ Mensaje enviado a Dead-Letter después de {data['retries']} intentos")
                else:
                    await r.rpush(SOURCE_QUEUE, new_msg)

        except Exception as e:
            print(f"Error inesperado en worker: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(procesar_cola())