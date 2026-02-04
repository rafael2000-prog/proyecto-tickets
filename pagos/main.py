from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import redis.asyncio as redis # Necesario para leer la bandera de caos

app = FastAPI()

# Cliente Redis para leer flags de caos
redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/procesar")
async def procesar_pago():
    try:
        print("--> Recibiendo petición de pago...")
        
        # --- CHAOS MONKEY: LA PASARELA LENTA ---
        # Verificamos si el modo caos está activado
        modo_lento = await redis_client.get("chaos:pagos:latencia")
        
        if modo_lento == "true":
            print("CHAOS ACTIVADO: Simulando latencia de 20 segundos...")
            await asyncio.sleep(20) # Esto forzará un Timeout en el servicio de Reservas
        else:
            # Latencia normal simulada (1 segundo)
            await asyncio.sleep(1) 
        # ---------------------------------------

        # Enviamos un JSON claro y directo
        return {"status": "success", "mensaje": "Aprobado"}
    except Exception as e:
        print(f"Error interno en pagos: {e}")
        return {"status": "error", "mensaje": str(e)}
