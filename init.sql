-- init.sql

-- 1. Crear la tabla de asientos (según inventario/main.py)
CREATE TABLE IF NOT EXISTS asientos (
    id SERIAL PRIMARY KEY,
    estado VARCHAR(50) DEFAULT 'disponible' -- disponible, bloqueado, vendido
);

-- 2. Crear la tabla de reservas
CREATE TABLE IF NOT EXISTS reservas (
    id SERIAL PRIMARY KEY,
    asiento_id INT REFERENCES asientos(id),
    cliente_email VARCHAR(100),
    estado_pago VARCHAR(50), -- pendiente, completado
    notificado BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Insertar los 20 asientos que usa tu Frontend (index.html usa un loop de 1 a 20)
INSERT INTO asientos (id, estado) VALUES 
(1, 'disponible'), (2, 'disponible'), (3, 'disponible'), (4, 'disponible'), (5, 'disponible'),
(6, 'disponible'), (7, 'disponible'), (8, 'disponible'), (9, 'disponible'), (10, 'disponible'),
(11, 'disponible'), (12, 'disponible'), (13, 'disponible'), (14, 'disponible'), (15, 'disponible'),
(16, 'disponible'), (17, 'disponible'), (18, 'disponible'), (19, 'disponible'), (20, 'disponible')
ON CONFLICT (id) DO NOTHING;