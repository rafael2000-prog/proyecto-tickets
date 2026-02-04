import redis
import sys

# Conexión a Redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def menu():
    print("\n--- PANEL DE CONTROL DE CHAOS MONKEY ---")
    print("1. Activar 'Inventario Fantasma' (Simular caída/timeout del Inventario)")
    print("2. Activar 'Pasarela Lenta' (Latencia de 20s en Pagos)")
    print("3. Activar 'Correo Perdido' (Fallo 100% en Notificaciones)")
    print("4. RESTAURAR SISTEMA (Borrar todos los fallos)")
    print("0. Salir")
    return input("Selecciona una opción: ")

def aplicar_caos():
    while True:
        opcion = menu()
        
        if opcion == "1":
            # Hacemos que el inventario se "cuelgue" simulando un crash/timeout
            r.set("chaos:inventario:fail", "true")
            print("Inventario ahora simulará estar caído (Timeout/Error).")
        
        elif opcion == "2":
            # Latencia de 20s para forzar timeout en reservas
            r.set("chaos:pagos:latencia", "true")
            print("Pagos ahora tardará 20 segundos en responder.")
            
        elif opcion == "3":
            # Forzamos error 500 en notificaciones
            r.set("chaos:email:fail", "true")
            print("Notificaciones fallará siempre.")
            
        elif opcion == "4":
            r.delete("chaos:inventario:fail")
            r.delete("chaos:pagos:latencia")
            r.delete("chaos:email:fail")
            print("Sistema restaurado a la normalidad.")
            
        elif opcion == "0":
            break

if __name__ == "__main__":
    aplicar_caos()
