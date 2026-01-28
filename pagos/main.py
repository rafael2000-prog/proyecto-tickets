from fastapi import FastAPI
import asyncio

app = FastAPI()

@app.post("/procesar")
async def procesar_pago():
    # SIMULACIÓN DE FALLA: Latencia extrema (20 segundos)
    print("Procesando pago... (va a tardar)")
    await asyncio.sleep(20) 
    return {"status": "pago_exitoso", "transaction_id": "TX12345"}