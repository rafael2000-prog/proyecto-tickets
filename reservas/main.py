import json
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware 
import httpx
import asyncio
import redis.asyncio as redis # Si usas FastAPI asíncrono

redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)

app = FastAPI()

# 2. Configurar el Middleware de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite cualquier origen
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PAGOS_URL = "http://127.0.0.1:8002" 
INVENTARIO_URL = "http://127.0.0.1:8001"
NOTIFICACIONES_URL = "http://127.0.0.1:8003"

# Función de apoyo para las notificaciones
async def enviar_email_en_segundo_plano(asiento_id: int):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(f"{NOTIFICACIONES_URL}/enviar", 
                             json={"email": "usuario@ejemplo.com", "asiento": asiento_id},
                             timeout=2.0)
        except Exception:
            print(f"Error enviando correo para asiento {asiento_id}")

@app.post("/comprar/{asiento_id}")
async def reservar_inicial(asiento_id: int):
    # 1. Intentamos bloquear en REDIS (Caché/Memoria rápida)
    # SETNX solo tiene éxito si la llave no existe (Atomicidad)
    clave_bloqueo = f"asiento:{asiento_id}"
    exito_bloqueo = await redis_client.setnx(clave_bloqueo, "bloqueado")
    
    if exito_bloqueo:
        # Ponemos un tiempo de vida (ej. 2 minutos) por si el usuario nunca paga
        await redis_client.expire(clave_bloqueo, 120)
        
        # 2. Intentamos avisar al inventario (POSTGRES) - SEGUNDO PLANO
        # Si falla, no importa, porque Redis ya tiene el asiento bloqueado
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{INVENTARIO_URL}/bloquear/{asiento_id}", timeout=0.5)
        except Exception:
            print(f"Aviso: Inventario offline. Bloqueo mantenido en Redis para asiento {asiento_id}")

        return {"status": "bloqueado", "mensaje": "Asiento reservado en caché. Procede al pago."}
    
    else:
        # Si SETNX devuelve False, es que alguien más ya lo bloqueó en Redis
        return {"status": "error", "error": "Asiento ya reservado o vendido"}

@app.post("/finalizar-pago/{asiento_id}")
async def finalizar_pago(asiento_id: int):
    pago_key = f"pago:{asiento_id}"

    # Intentamos marcar el pago como "en proceso" de forma atómica para evitar dobles cobros
    marcado = await redis_client.setnx(pago_key, "en_proceso")
    if not marcado:
        return {"status": "error", "mensaje": "Pago ya en proceso o ya realizado"}

    # Expiramos la marca por si algo sale muy mal (evita bloqueos infinitos)
    await redis_client.expire(pago_key, 3600)

    async with httpx.AsyncClient() as client:
        # --- PASO 1: PAGO (Si falla, el cliente no paga, así que nos detenemos) ---
        try:
            res_pago = await client.post(f"{PAGOS_URL}/procesar", timeout=3.0)
            data_pago = res_pago.json()

            # Verificamos que el código sea 200 O que el status diga success
            if res_pago.status_code != 200 or data_pago.get("status") != "success":
                # Liberamos la marca para permitir reintentos
                await redis_client.delete(pago_key)
                return {"status": "error", "mensaje": "Pago rechazado por el banco"}

        except Exception as e:
            # Liberamos la marca para permitir reintentos
            await redis_client.delete(pago_key)
            return {"status": "error", "mensaje": f"Error de conexión con pagos: {str(e)}"}

        # --- PASO 2: NOTIFICACIÓN (Si falla, NO nos detenemos) ---
        notif_ok = False
        try:
            # Timeout corto para que no se trabe el botón
            await client.post(f"{NOTIFICACIONES_URL}/enviar", json={"asiento": asiento_id}, timeout=0.8)
            notif_ok = True
        except:
            notif_ok = False # Toleramos el fallo

        # --- PASO 3: INVENTARIO (Uso de Cola para Resiliencia) ---
        # Incluimos la bandera `notificado` para que el worker pueda marcar en DB si ya se envió correo
        evento = {"asiento_id": asiento_id, "accion": "vender", "retries": 0, "notificado": notif_ok}
        mensaje = json.dumps(evento)

        fallback_used = False
        try:
            await redis_client.rpush("cola_inventario", mensaje)
            print(f"🔥 ÉXITO: Mensaje enviado a Redis para asiento {asiento_id}")
        except Exception as e:
            print(f"❌ ERROR CRÍTICO REDIS: {e}")
            # Fallback local (archivo) para resiliencia cuando Redis no está disponible
            try:
                with open("outbox_fallback.jsonl", "a", encoding="utf-8") as f:
                    f.write(mensaje + "\n")
                fallback_used = True
                print(f"💾 Fallback: mensaje escrito en outbox_fallback.jsonl para asiento {asiento_id}")
            except Exception as e2:
                # Si ni siquiera el fallback local funciona, liberamos la marca de pago para permitir reintentos
                await redis_client.delete(pago_key)
                return {"status": "error", "mensaje": "Fallo crítico: no se pudo encolar ni escribir fallback"}

        # Marcamos pago definitivamente realizado (evitamos que otro intento cobre de nuevo)
        await redis_client.set(pago_key, "realizado")
        await redis_client.expire(pago_key, 86400)  # 24 horas

        # Confirmación final al cliente
        return {"status": "success", "mensaje": "Pago procesado", "notificado": notif_ok, "fallback": fallback_used}