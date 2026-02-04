from fastapi import FastAPI, HTTPException
import random
import redis.asyncio as redis

app = FastAPI()
redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)

@app.post("/enviar")
async def enviar_confirmacion(email_data: dict):
    
    # --- CHAOS MONKEY: EL CORREO PERDIDO ---
    chaos_fail = await redis_client.get("chaos:email:fail")
    
    # Si el caos está activado O si cae en el 20% de probabilidad original
    if chaos_fail == "true" or random.random() < 0.2: # Ajusté a 0.2 (20% fallo natural) para que sea más estable sin caos
        print("CHAOS/ERROR: Simulando fallo crítico en servidor de correos.")
        raise HTTPException(status_code=500, detail="Error al enviar email (Simulado)")
    # ---------------------------------------
    
    print(f"Correo enviado con éxito a {email_data.get('email', 'desconocido')}")
    return {"status": "enviado"}
