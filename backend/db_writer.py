"""
Cliente para interactuar con la base de datos local PostgreSQL
"""

import json
import psycopg2
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from backend.config import Config, get_logger
import os

logger = get_logger(__name__)

class LocalPostgresClient:

    def get_recent_data(self, device_id: str, limit: int = 100) -> List[Dict]:
        """Obtener los datos más recientes de un dispositivo desde la base de datos local PostgreSQL"""
        if not self.conn:
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT * FROM sensor_data WHERE device_id = %s ORDER BY timestamp DESC LIMIT %s;", (device_id, limit))
                columns = [desc[0] for desc in cur.description]
                data = [dict(zip(columns, row)) for row in cur.fetchall()]
                
                # Convertir timestamps a string para serialización
                for row in data:
                    if 'timestamp' in row and hasattr(row['timestamp'], 'isoformat'):
                        row['timestamp'] = row['timestamp'].isoformat()
                        
            return data
        except Exception as e:
            logger.error(f"Error obteniendo datos recientes de {device_id} desde base local: {e}")
            return []

    def get_data_by_hours(self, device_id: str, hours: float) -> List[Dict]:
        """Obtener datos de un dispositivo desde las últimas N horas"""
        if not self.conn:
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM sensor_data 
                    WHERE device_id = %s AND timestamp >= NOW() - INTERVAL '%s hours'
                    ORDER BY timestamp DESC
                """, (device_id, hours))
                columns = [desc[0] for desc in cur.description]
                data = [dict(zip(columns, row)) for row in cur.fetchall()]
                
                # Convertir timestamps a string para serialización
                for row in data:
                    if 'timestamp' in row and hasattr(row['timestamp'], 'isoformat'):
                        row['timestamp'] = row['timestamp'].isoformat()
                        
            return data
        except Exception as e:
            logger.error(f"Error obteniendo datos por horas de {device_id} desde base local: {e}")
            return []

    def get_data_by_days(self, device_id: str, days: int) -> List[Dict]:
        """Obtener datos de un dispositivo desde los últimos N días"""
        if not self.conn:
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM sensor_data 
                    WHERE device_id = %s AND timestamp >= NOW() - INTERVAL '%s days'
                    ORDER BY timestamp DESC
                """, (device_id, days))
                columns = [desc[0] for desc in cur.description]
                data = [dict(zip(columns, row)) for row in cur.fetchall()]
                
                # Convertir timestamps a string para serialización
                for row in data:
                    if 'timestamp' in row and hasattr(row['timestamp'], 'isoformat'):
                        row['timestamp'] = row['timestamp'].isoformat()
                        
            return data
        except Exception as e:
            logger.error(f"Error obteniendo datos por días de {device_id} desde base local: {e}")
            return []

    def get_all_data_by_hours(self, hours: float) -> List[Dict]:
        """Obtener datos de todos los dispositivos desde las últimas N horas"""
        if not self.conn:
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM sensor_data 
                    WHERE timestamp >= NOW() - INTERVAL '%s hours'
                    ORDER BY timestamp DESC
                """, (hours,))
                columns = [desc[0] for desc in cur.description]
                data = [dict(zip(columns, row)) for row in cur.fetchall()]
                
                # Convertir timestamps a string para serialización
                for row in data:
                    if 'timestamp' in row and hasattr(row['timestamp'], 'isoformat'):
                        row['timestamp'] = row['timestamp'].isoformat()
                        
            return data
        except Exception as e:
            logger.error(f"Error obteniendo todos los datos por horas desde base local: {e}")
            return []

    def get_all_data_by_days(self, days: int) -> List[Dict]:
        """Obtener datos de todos los dispositivos desde los últimos N días"""
        if not self.conn:
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM sensor_data 
                    WHERE timestamp >= NOW() - INTERVAL '%s days'
                    ORDER BY timestamp DESC
                """, (days,))
                columns = [desc[0] for desc in cur.description]
                data = [dict(zip(columns, row)) for row in cur.fetchall()]
                
                # Convertir timestamps a string para serialización
                for row in data:
                    if 'timestamp' in row and hasattr(row['timestamp'], 'isoformat'):
                        row['timestamp'] = row['timestamp'].isoformat()
                        
            return data
        except Exception as e:
            logger.error(f"Error obteniendo todos los datos por días desde base local: {e}")
            return []
    def get_system_events(self, limit: int = 50) -> List[Dict]:
        """Obtener los eventos recientes del sistema desde la base de datos local PostgreSQL"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT * FROM system_events ORDER BY timestamp DESC LIMIT %s;", (limit,))
                columns = [desc[0] for desc in cur.description]
                events = [dict(zip(columns, row)) for row in cur.fetchall()]
            return events
        except Exception as e:
            logger.error(f"Error obteniendo eventos del sistema desde la base local: {e}")
            return []
    """Cliente para operaciones con la base de datos local PostgreSQL"""
    
    def __init__(self):
        try:
            self.conn = psycopg2.connect(
                dbname=os.getenv('DB_NAME', 'iot_db'),
                user=os.getenv('DB_USER', 'iot_user'),
                password=os.getenv('DB_PASSWORD', 'DAms15820'),
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432')
            )
            logger.info("Conexión a la base de datos local PostgreSQL establecida (LocalPostgresClient)")
        except Exception as e:
            logger.error(f"Error conectando a la base de datos local PostgreSQL: {e}")
            self.conn = None
            self.client = None
    
    def register_device(self, device_data: Dict[str, Any]) -> bool:
        """Registrar o actualizar un dispositivo en la base de datos local PostgreSQL"""
        if not self.conn:
            return False
        try:
            with self.conn.cursor() as cur:
                # Intentar insertar, si existe actualizarlo
                cur.execute("""
                    INSERT INTO devices (device_id, device_type, status, last_seen)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (device_id) DO UPDATE SET
                        device_type = EXCLUDED.device_type,
                        status = EXCLUDED.status,
                        last_seen = EXCLUDED.last_seen;
                """, (
                    device_data.get('device_id'),
                    device_data.get('device_type'),
                    device_data.get('status', 'online'),
                    device_data.get('last_seen', datetime.now().isoformat())
                ))
                self.conn.commit()
            logger.info(f"Dispositivo registrado en base local: {device_data.get('device_id')}")
            return True
        except Exception as e:
            logger.error(f"Error registrando dispositivo en base local: {e}")
            
            # Si hay error de transacción abortada, reconectar y reintentar
            if "current transaction is aborted" in str(e):
                logger.warning("Transacción abortada detectada en registro de dispositivo, reconectando...")
                if self._reconnect():
                    try:
                        with self.conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO devices (device_id, device_type, status, last_seen)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (device_id) DO UPDATE SET
                                    device_type = EXCLUDED.device_type,
                                    status = EXCLUDED.status,
                                    last_seen = EXCLUDED.last_seen;
                            """, (
                                device_data.get('device_id'),
                                device_data.get('device_type'),
                                device_data.get('status', 'online'),
                                device_data.get('last_seen', datetime.now().isoformat())
                            ))
                            self.conn.commit()
                        logger.info(f"Dispositivo registrado tras reconexión: {device_data.get('device_id')}")
                        return True
                    except Exception as e2:
                        logger.error(f"Error tras reconexión registrando dispositivo: {e2}")
            return False
    
    def _reconnect(self):
        """Reconectar a la base de datos cuando hay errores de transacción"""
        try:
            if self.conn:
                self.conn.close()
            self.conn = psycopg2.connect(
                dbname=os.getenv('DB_NAME', 'iot_db'),
                user=os.getenv('DB_USER', 'iot_user'),
                password=os.getenv('DB_PASSWORD', 'DAms15820'),
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432')
            )
            logger.info("Reconexión a la base de datos local PostgreSQL establecida")
            return True
        except Exception as e:
            logger.error(f"Error reconectando a la base de datos local PostgreSQL: {e}")
            self.conn = None
            return False

    def insert_sensor_data(self, sensor_data: Dict[str, Any]) -> bool:
        """Registrar el dispositivo si no existe y luego insertar datos de sensor en la base de datos local PostgreSQL evitando duplicados"""
        if not self.conn:
            return False

        # Convertir Decimal a float en todos los campos
        def convert_decimal(obj):
            try:
                from decimal import Decimal
            except ImportError:
                return obj
            if isinstance(obj, dict):
                return {k: convert_decimal(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_decimal(v) for v in obj]
            elif 'Decimal' in str(type(obj)):
                return float(obj)
            else:
                return obj

        sensor_data_clean = convert_decimal(sensor_data)
        # Convertir timestamp a string ISO si es datetime
        if 'timestamp' in sensor_data_clean:
            import dateutil.parser
            ts = sensor_data_clean['timestamp']
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                sensor_data_clean['timestamp'] = dt.isoformat()
            elif hasattr(ts, 'isoformat'):
                sensor_data_clean['timestamp'] = ts.astimezone(timezone.utc).isoformat()
            elif isinstance(ts, str):
                try:
                    dt = dateutil.parser.isoparse(ts)
                    sensor_data_clean['timestamp'] = dt.astimezone(timezone.utc).isoformat()
                except Exception:
                    pass
        sensor_data_clean.pop('created_at', None)

        # Registrar o actualizar el dispositivo cada vez que llega un dato de sensor
        device_id = sensor_data_clean.get('device_id')
        device_type = sensor_data_clean.get('raw_data', {}).get('device_type') or sensor_data_clean.get('device_type', 'arduino_ethernet')
        if device_id:
            try:
                device_data = {
                    'device_id': device_id,
                    'device_type': device_type,
                    'status': 'online',
                    'last_seen': datetime.now().isoformat()
                }
                self.register_device(device_data)
            except Exception as e:
                logger.error(f"Error registrando/actualizando dispositivo en base local: {e}")
                # Si hay error de transacción abortada, reconectar
                if "current transaction is aborted" in str(e):
                    logger.warning("Transacción abortada detectada, reconectando...")
                    if self._reconnect():
                        try:
                            self.register_device(device_data)
                        except Exception as e2:
                            logger.error(f"Error tras reconexión registrando dispositivo: {e2}")

        # Insertar en la tabla sensor_data
        try:
            with self.conn.cursor() as cur:
                query = """
                    INSERT INTO sensor_data (device_id, sensor_type, value, unit, raw_data, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (device_id, sensor_type, timestamp) DO NOTHING;
                """
                cur.execute(query, (
                    sensor_data_clean.get('device_id'),
                    sensor_data_clean.get('sensor_type'),
                    sensor_data_clean.get('value'),
                    sensor_data_clean.get('unit'),
                    json.dumps(sensor_data_clean.get('raw_data', {})),
                    sensor_data_clean.get('timestamp')
                ))
                self.conn.commit()
            logger.info(f"Dato de sensor insertado en base local: {json.dumps(sensor_data_clean, default=str)}")
            return True
        except Exception as e:
            logger.error(f"Error insertando dato de sensor en base local: {e}")
            logger.error(f"Objeto problemático: {json.dumps(sensor_data_clean, default=str)}")
            
            # Si hay error de transacción abortada, reconectar y reintentar
            if "current transaction is aborted" in str(e):
                logger.warning("Transacción abortada detectada en inserción, reconectando...")
                if self._reconnect():
                    try:
                        with self.conn.cursor() as cur:
                            cur.execute(query, (
                                sensor_data_clean.get('device_id'),
                                sensor_data_clean.get('sensor_type'),
                                sensor_data_clean.get('value'),
                                sensor_data_clean.get('unit'),
                                json.dumps(sensor_data_clean.get('raw_data', {})),
                                sensor_data_clean.get('timestamp')
                            ))
                            self.conn.commit()
                        logger.info(f"Dato de sensor insertado tras reconexión: {json.dumps(sensor_data_clean, default=str)}")
                        return True
                    except Exception as e2:
                        logger.error(f"Error tras reconexión insertando sensor: {e2}")
            return False
    
    def update_device_status(self, device_id: str, status: str) -> bool:
        """Actualizar estado de dispositivo en la base de datos local PostgreSQL"""
        if not self.conn:
            return False
        try:
            with self.conn.cursor() as cur:
                query = """
                    UPDATE devices SET status = %s, last_seen = %s WHERE device_id = %s;
                """
                cur.execute(query, (status, datetime.now(timezone.utc).isoformat(), device_id))
                self.conn.commit()
            logger.info(f"Estado del dispositivo {device_id} actualizado a {status} en base local.")
            return True
        except Exception as e:
            logger.error(f"Error actualizando estado del dispositivo {device_id} en base local: {e}")
            return False
    
    def log_system_event(self, event_type: str, device_id: Optional[str] = None, 
                        message: str = "", metadata: Optional[Dict] = None) -> bool:
        """Registrar evento del sistema en la base de datos local PostgreSQL"""
        if not self.conn:
            return False
        try:
            with self.conn.cursor() as cur:
                query = """
                    INSERT INTO system_events (event_type, device_id, message, metadata, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cur.execute(query, (
                    event_type,
                    device_id,
                    message,
                    json.dumps(metadata) if metadata else None,
                    datetime.now(timezone.utc).isoformat()
                ))
                self.conn.commit()
            logger.info(f"Evento del sistema registrado: {event_type} - {device_id} - {message}")
            return True
        except Exception as e:
            logger.error(f"Error registrando evento del sistema en base local: {e}")
            return False
    
    def get_devices(self) -> List[Dict]:
        """Obtener todos los dispositivos desde la base de datos local PostgreSQL"""
        if not self.conn:
            return []
        try:
            logger.info("Obteniendo dispositivos desde la base local.")
            with self.conn.cursor() as cur:
                cur.execute("SELECT * FROM devices;")
                columns = [desc[0] for desc in cur.description]
                devices = [dict(zip(columns, row)) for row in cur.fetchall()]
            return devices
        except Exception as e:
            logger.error(f"Error obteniendo dispositivos desde base local: {e}")
            return []
    
    def get_latest_sensor_data(self, limit: int = 100) -> List[Dict]:
        """Obtener datos más recientes de sensores desde la base de datos local PostgreSQL"""
        if not self.conn:
            return []
        try:
            logger.info("Obteniendo datos de sensores desde la base local.")
            with self.conn.cursor() as cur:
                cur.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT %s;", (limit,))
                columns = [desc[0] for desc in cur.description]
                data = [dict(zip(columns, row)) for row in cur.fetchall()]
                
                # Convertir timestamps a string para serialización
                for row in data:
                    if 'timestamp' in row and hasattr(row['timestamp'], 'isoformat'):
                        row['timestamp'] = row['timestamp'].isoformat()
                        
            return data
        except Exception as e:
            logger.error(f"Error obteniendo datos de sensores desde base local: {e}")
            return []
