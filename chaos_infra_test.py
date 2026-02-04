import subprocess
import time
import random
import sys

# Ajusta estos nombres según tus contenedores reales (docker ps)
SERVICES = [
    "ticket-system-inventario-1",
    "ticket-system-pagos-1",
    "ticket-system-notificaciones-1"
]

def docker_action(action, container):
    """Ejecuta start, stop o pause en un contenedor"""
    print(f"Acción: {action.upper()} -> {container}...")
    subprocess.run(["docker", action, container], check=False)

def chaos_loop():
    print("MODO CHAOS ACTIVADO (Ctrl+C para detener)")
    try:
        while True:
            target = random.choice(SERVICES)
            # 1. Matar servicio
            docker_action("stop", target)
            
            # 2. Esperar (simular tiempo de caída)
            wait_time = random.randint(5, 15)
            print(f"Servicio caído por {wait_time} segundos...")
            time.sleep(wait_time)
            
            # 3. Revivir servicio
            docker_action("start", target)
            print(f"Servicio {target} recuperado.")
            
            # 4. Esperar antes del siguiente ataque
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nDeteniendo caos. Asegurando que todo esté encendido...")
        for s in SERVICES:
            docker_action("start", s)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "loop":
        chaos_loop()
    else:
        print("Uso: python chaos_infra.py loop")
