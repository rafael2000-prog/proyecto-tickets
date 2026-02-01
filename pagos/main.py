from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

app = FastAPI()

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
        await asyncio.sleep(1) # El servicio de pagos demora 20 segundos por una sobrecarga.
        # Enviamos un JSON claro y directo
        return {"status": "success", "mensaje": "Aprobado"}
    except Exception as e:
        print(f"Error interno en pagos: {e}")
        return {"status": "error", "mensaje": str(e)}