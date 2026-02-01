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
    async with httpx.AsyncClient() as client:
        # --- PASO 1: PAGO (Si falla, el cliente no paga, así que nos detenemos) ---
        try:
            res_pago = await client.post(f"{PAGOS_URL}/procesar", timeout=3.0)
            data_pago = res_pago.json()
            
            # Verificamos que el código sea 200 O que el status diga success
            if res_pago.status_code != 200 or data_pago.get("status") != "success":
                return {"status": "error", "mensaje": "Pago rechazado por el banco"}
                
            # Si llega aquí, el pago es exitoso... sigue el flujo
        except Exception as e:
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
        try:
            evento = {"asiento_id": asiento_id, "accion": "vender"}
            # Convertimos a JSON string
            mensaje = json.dumps(evento)
            
            # IMPORTANTE: Usa await porque redis_client es asíncrono
            await redis_client.rpush("cola_inventario", mensaje)
            
            print(f"🔥 ÉXITO: Mensaje enviado a Redis para asiento {asiento_id}")
            
        except Exception as e:
            print(f"❌ ERROR CRÍTICO REDIS: {e}")
            # Solo si Redis falla de verdad, intentamos el plan B
            # (Pero en la demo Redis debería estar siempre ON)
    
        try:
            res_pago = await client.post(f"{PAGOS_URL}/procesar", timeout=5.0)
            
            # Verificamos si la respuesta está vacía o es un error de servidor
            if res_pago.status_code != 200:
                return {"status": "error", "mensaje": "El servicio de pagos devolvió un error técnico"}
            
            data_pago = res_pago.json() # Ahora es seguro convertir
            
            if data_pago.get("status") != "success":
                return {"status": "error", "mensaje": "Pago rechazado por el banco"}

        except Exception as e:
            print(f"Error de conexión o formato: {e}")
            return {"status": "error", "mensaje": "No se pudo procesar el pago (Servicio Offline o Error de JSON)"}