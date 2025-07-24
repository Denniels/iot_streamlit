"""
Cliente para interactuar con PostgreSQL local
"""
import psycopg2
import psycopg2.extras
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from backend.config import Config, get_logger

logger = get_logger(__name__)

class PostgreSQLClient:
    """Cliente para operaciones con PostgreSQL local"""
    
    def __init__(self):
        self.conn = None
        self.connect()
    
    def connect(self):
        """Establecer conexión a PostgreSQL"""
        try:
            self.conn = psycopg2.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD
            )
            self.conn.autocommit = True
            logger.info("Conexión a PostgreSQL establecida")
        except Exception as e:
            logger.error(f"Error conectando a PostgreSQL: {e}")
            self.conn = None
    
    def execute_query(self, query: str, params: tuple = None) -> Optional[List[Dict]]:
        """Ejecutar una consulta SQL"""
        if not self.conn:
            self.connect()
        
        if not self.conn:
            return None
        
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params)
                if cursor.description:
                    return [dict(row) for row in cursor.fetchall()]
                return []
        except Exception as e:
            logger.error(f"Error ejecutando consulta: {e}")
            return None
    
    def register_device(self, device_data: Dict[str, Any]) -> bool:
        """Registrar o actualizar un dispositivo"""
        try:
            query = """
            INSERT INTO devices (device_id, device_type, name, ip_address, port, status, metadata)
            VALUES (%(device_id)s, %(device_type)s, %(name)s, %(ip_address)s, %(port)s, %(status)s, %(metadata)s)
            ON CONFLICT (device_id) 
            DO UPDATE SET 
                device_type = EXCLUDED.device_type,
                name = EXCLUDED.name,
                ip_address = EXCLUDED.ip_address,
                port = EXCLUDED.port,
                status = EXCLUDED.status,
                metadata = EXCLUDED.metadata,
                last_seen = NOW(),
                updated_at = NOW()
            """
            
            # Convertir metadata a JSON si es necesario
            if 'metadata' in device_data and isinstance(device_data['metadata'], dict):
                device_data['metadata'] = json.dumps(device_data['metadata'])
            
            self.execute_query(query, device_data)
            logger.info(f"Dispositivo registrado: {device_data.get('device_id')}")
            return True
        except Exception as e:
            logger.error(f"Error registrando dispositivo: {e}")
            return False
    
    def insert_sensor_data(self, sensor_data: Dict[str, Any]) -> bool:
        """Insertar datos de sensor"""
        try:
            query = """
            INSERT INTO sensor_data (device_id, sensor_type, value, unit, raw_data)
            VALUES (%(device_id)s, %(sensor_type)s, %(value)s, %(unit)s, %(raw_data)s)
            """
            
            # Convertir raw_data a JSON si es necesario
            if 'raw_data' in sensor_data and isinstance(sensor_data['raw_data'], dict):
                sensor_data['raw_data'] = json.dumps(sensor_data['raw_data'])
            
            self.execute_query(query, sensor_data)
            logger.debug(f"Datos de sensor insertados para dispositivo: {sensor_data.get('device_id')}")
            return True
        except Exception as e:
            logger.error(f"Error insertando datos de sensor: {e}")
            return False
    
    def log_system_event(self, event_type: str, device_id: str = None, 
                        message: str = None, metadata: Dict = None) -> bool:
        """Registrar evento del sistema"""
        try:
            query = """
            INSERT INTO system_events (event_type, device_id, message, metadata)
            VALUES (%(event_type)s, %(device_id)s, %(message)s, %(metadata)s)
            """
            
            event_data = {
                'event_type': event_type,
                'device_id': device_id,
                'message': message,
                'metadata': json.dumps(metadata) if metadata else None
            }
            
            self.execute_query(query, event_data)
            return True
        except Exception as e:
            logger.error(f"Error registrando evento del sistema: {e}")
            return False
    
    def get_devices(self, status: str = None) -> List[Dict]:
        """Obtener lista de dispositivos"""
        try:
            if status:
                query = "SELECT * FROM devices WHERE status = %s ORDER BY last_seen DESC"
                return self.execute_query(query, (status,)) or []
            else:
                query = "SELECT * FROM devices ORDER BY last_seen DESC"
                return self.execute_query(query) or []
        except Exception as e:
            logger.error(f"Error obteniendo dispositivos: {e}")
            return []
    
    def get_recent_sensor_data(self, device_id: str = None, limit: int = 100) -> List[Dict]:
        """Obtener datos recientes de sensores"""
        try:
            if device_id:
                query = """
                SELECT * FROM sensor_data 
                WHERE device_id = %s 
                ORDER BY timestamp DESC 
                LIMIT %s
                """
                return self.execute_query(query, (device_id, limit)) or []
            else:
                query = """
                SELECT * FROM sensor_data 
                ORDER BY timestamp DESC 
                LIMIT %s
                """
                return self.execute_query(query, (limit,)) or []
        except Exception as e:
            logger.error(f"Error obteniendo datos de sensores: {e}")
            return []
    
    def initialize_schema(self) -> bool:
        """Crear las tablas del esquema si no existen"""
        try:
            # Script SQL para crear las tablas
            schema_sql = """
            -- Tabla para dispositivos
            CREATE TABLE IF NOT EXISTS devices (
                id SERIAL PRIMARY KEY,
                device_id VARCHAR(255) UNIQUE NOT NULL,
                device_type VARCHAR(100) NOT NULL,
                name VARCHAR(255),
                ip_address INET,
                port INTEGER,
                status VARCHAR(50) DEFAULT 'active',
                metadata JSONB,
                first_seen TIMESTAMP DEFAULT NOW(),
                last_seen TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );

            -- Tabla para datos de sensores
            CREATE TABLE IF NOT EXISTS sensor_data (
                id SERIAL PRIMARY KEY,
                device_id VARCHAR(255) NOT NULL,
                sensor_type VARCHAR(100) NOT NULL,
                value NUMERIC(10,2),
                unit VARCHAR(50),
                raw_data JSONB,
                timestamp TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
            );

            -- Tabla para eventos del sistema
            CREATE TABLE IF NOT EXISTS system_events (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(100) NOT NULL,
                device_id VARCHAR(255),
                message TEXT,
                metadata JSONB,
                timestamp TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE SET NULL
            );

            -- Índices para optimizar consultas
            CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id);
            CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
            CREATE INDEX IF NOT EXISTS idx_sensor_data_device_id ON sensor_data(device_id);
            CREATE INDEX IF NOT EXISTS idx_sensor_data_timestamp ON sensor_data(timestamp);
            CREATE INDEX IF NOT EXISTS idx_system_events_timestamp ON system_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_system_events_device_id ON system_events(device_id);
            """
            
            # Ejecutar cada comando SQL por separado
            commands = [cmd.strip() for cmd in schema_sql.split(';') if cmd.strip()]
            
            with self.conn.cursor() as cursor:
                for command in commands:
                    if command:
                        cursor.execute(command)
            
            logger.info("Esquema de base de datos inicializado correctamente")
            return True
            
        except Exception as e:
            logger.error(f"Error inicializando esquema: {e}")
            return False

    def close(self):
        """Cerrar conexión"""
        if self.conn:
            self.conn.close()
            logger.info("Conexión a PostgreSQL cerrada")

# Instancia global del cliente PostgreSQL
db_client = PostgreSQLClient()
