from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import httpx

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# URL del Servicio de Reservas
RESERVAS_URL = "http://localhost:8000"

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Aquí podrías consultar al inventario para mostrar asientos libres
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/checkout/{asiento_id}")
async def checkout(asiento_id: int):
    async with httpx.AsyncClient() as client:
        try:
            # El Gateway le pide al Servicio de Reservas que inicie el proceso
            response = await client.post(f"{RESERVAS_URL}/comprar/{asiento_id}", timeout=10.0)
            return response.json()
        except Exception as e:
            return {"status": "error", "message": "El sistema central no responde"}
        
@app.get("/healthcheck")
async def health_check():
    services = {
        "reservas": "http://localhost:8000",
        "inventario": "http://localhost:8001",
        "pagos": "http://localhost:8002",
        "notificaciones": "http://localhost:8003"
    }
    results = {}
    async with httpx.AsyncClient() as client:
        for name, url in services.items():
            try:
                # Intentamos una petición rápida de 1 segundo
                await client.get(url, timeout=1.0)
                results[name] = "ONLINE"
            except:
                results[name] = "OFFLINE"
    return results