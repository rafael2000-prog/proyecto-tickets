from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

# Importante para que el dashboard pueda leer los datos sin bloqueos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cliente Redis para administración de colas (no crítico para la lógica de inventario)
import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

@app.get("/admin/cola")
def ver_cola_redis():
    try:
        return {
            "principal_len": r.llen("cola_inventario"),
            "principal_sample": r.lrange("cola_inventario", 0, 9),
            "processing_len": r.llen("cola_inventario_processing"),
            "processing_sample": r.lrange("cola_inventario_processing", 0, 9),
            "dead_letter_len": r.llen("cola_inventario_muerta"),
            "dead_letter_sample": r.lrange("cola_inventario_muerta", 0, 9)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {e}")


@app.post("/admin/reencolar-muerta")
def reencolar_muerta(limit: int = 10):
    moved = 0
    try:
        for _ in range(limit):
            item = r.rpop("cola_inventario_muerta")
            if not item:
                break
            r.rpush("cola_inventario", item)
            moved += 1
        return {"moved": moved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {e}")

def get_db_connection():
    # Asegúrate de poner tu contraseña real aquí
    return psycopg2.connect(
        host="localhost", 
        database="ticket_system", 
        user="postgres", 
        password="Rafa1234",
        cursor_factory=RealDictCursor
    )

@app.get("/estado")
def ver_inventario():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, estado FROM asientos ORDER BY id;")
    rows = cur.fetchall()
    # Retorna { "1": "disponible", "2": "vendido" ... }
    res = {str(row['id']): row['estado'] for row in rows}
    cur.close()
    conn.close()
    return res

@app.get("/detalle-completo")
def obtener_detalle_completo():
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT a.id as asiento_id, a.estado, 
               COALESCE(r.estado_pago, 'n/a') as pago, 
               COALESCE(r.notificado, FALSE) as notificado
        FROM asientos a
        LEFT JOIN reservas r ON a.id = r.asiento_id
        ORDER BY a.id ASC;
    """
    cur.execute(query)
    detalles = cur.fetchall()
    cur.close()
    conn.close()
    return detalles

@app.post("/bloquear/{asiento_id}")
async def bloquear_asiento(asiento_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Bloqueo atómico en base de datos
        cur.execute("""
            UPDATE asientos SET estado = 'bloqueado' 
            WHERE id = %s AND estado = 'disponible' RETURNING id;
        """, (asiento_id,))
        
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Asiento ocupado o inexistente")

        # Crear registro de reserva inicial
        cur.execute("""
            INSERT INTO reservas (asiento_id, cliente_email, estado_pago, notificado)
            VALUES (%s, 'cliente@ejemplo.com', 'pendiente', FALSE);
        """, (asiento_id,))
        
        conn.commit()
        return {"status": "reservado_temporalmente", "asiento": asiento_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.post("/confirmar-final/{asiento_id}")
async def confirmar_final(asiento_id: int, notificado: str = "false"):
    # Convertimos el texto a booleano real
    fue_notificado = notificado.lower() in ["true", "1", "yes"]

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 0. Comprobamos que el asiento exista
        cur.execute("SELECT estado FROM asientos WHERE id = %s", (asiento_id,))
        fila = cur.fetchone()
        if not fila:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Asiento no encontrado")

        # Si ya está vendido, no fallamos (idempotencia)
        estado_actual = fila['estado'] if isinstance(fila, dict) else fila[0]
        if estado_actual == 'vendido':
            # Intentamos actualizar la reserva; si no existe, la creamos
            cur.execute("""
                UPDATE reservas
                SET estado_pago = 'completado', notificado = %s
                WHERE asiento_id = %s
            """, (fue_notificado, asiento_id))
            if cur.rowcount == 0:
                cur.execute("""
                    INSERT INTO reservas (asiento_id, cliente_email, estado_pago, notificado)
                    VALUES (%s, %s, 'completado', %s)
                """, (asiento_id, 'cliente@recovery.local', fue_notificado))
            conn.commit()
            return {"status": "already_sold", "db_notificado": fue_notificado}

        # 1. Marcar como vendido
        cur.execute("UPDATE asientos SET estado = 'vendido' WHERE id = %s", (asiento_id,))

        # 2. Intentamos actualizar la reserva; si no existe, la creamos
        cur.execute("""
            UPDATE reservas
            SET estado_pago = 'completado', notificado = %s
            WHERE asiento_id = %s
        """, (fue_notificado, asiento_id))
        if cur.rowcount == 0:
            cur.execute("""
                INSERT INTO reservas (asiento_id, cliente_email, estado_pago, notificado)
                VALUES (%s, %s, 'completado', %s)
            """, (asiento_id, 'cliente@recovery.local', fue_notificado))

        conn.commit()
        return {"status": "actualizado", "db_notificado": fue_notificado}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"Error SQL: {e}")
        return {"status": "error", "msg": str(e)}
    finally:
        cur.close()
        conn.close()


@app.post("/reset-db")
async def reset_db():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM reservas;")
        cur.execute("UPDATE asientos SET estado = 'disponible';")
        conn.commit()
        return {"status": "Base de datos limpia"}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "details": str(e)}
    finally:
        cur.close()
        conn.close()

@app.post("/liberar/{asiento_id}")
async def liberar_asiento(asiento_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Volvemos el asiento a disponible
        cur.execute("UPDATE asientos SET estado = 'disponible' WHERE id = %s;", (asiento_id,))
        # Borramos la reserva pendiente
        cur.execute("DELETE FROM reservas WHERE asiento_id = %s AND estado_pago = 'pendiente';", (asiento_id,))
        conn.commit()
        return {"status": "liberado"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()