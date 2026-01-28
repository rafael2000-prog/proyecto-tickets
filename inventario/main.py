from fastapi import FastAPI, HTTPException
import asyncio

app = FastAPI()

# Simulación de DB de asientos: {asiento_id: estado}
# Estados: "disponible", "bloqueado", "vendido"
inventario = {i: "disponible" for i in range(1, 11)}

@app.post("/bloquear/{asiento_id}")
async def bloquear_asiento(asiento_id: int):
    # Lógica para evitar la Condición de Carrera
    if asiento_id not in inventario:
        raise HTTPException(status_code=404, detail="Asiento no existe")
    
    if inventario[asiento_id] != "disponible":
        raise HTTPException(status_code=400, detail="Asiento ya ocupado o reservado")
    
    # Bloqueo atómico (simulado)
    inventario[asiento_id] = "bloqueado"
    return {"status": "reservado_temporalmente", "asiento": asiento_id}

@app.get("/estado")
def ver_inventario():
    return inventario