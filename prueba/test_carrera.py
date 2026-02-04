import asyncio
import httpx

async def intentar_reserva(usuario, asiento_id):
    url = f"http://localhost:8000/comprar/{asiento_id}"
    try:
        async with httpx.AsyncClient() as client:
            # Enviamos la petición
            response = await client.post(url, json={"usuario": usuario})
            print(f"Usuario {usuario}: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Error para {usuario}: {e}")

async def main():
    asiento_id = 5  # El asiento que vamos a pelear
    print(f" Iniciando duelo por el asiento {asiento_id}...")
    
    # Lanzamos las dos peticiones EXACTAMENTE al mismo tiempo
    await asyncio.gather(
        intentar_reserva("Juan", asiento_id),
        intentar_reserva("Maria", asiento_id)
    )

if __name__ == "__main__":
    asyncio.run(main())