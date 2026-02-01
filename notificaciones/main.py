from fastapi import FastAPI, HTTPException
import random

app = FastAPI()

@app.post("/enviar")
async def enviar_confirmacion(email_data: dict):
    # SIMULACIÓN DE FALLA: El servicio falla el 80% de las veces
    if random.random() < 0.8:
        print(" Error crítico en el servidor de correos.")
        raise HTTPException(status_code=500, detail="Error al enviar email")
    
    print(f" Correo enviado con éxito a {email_data['email']}")
    return {"status": "enviado"}