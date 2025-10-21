"""
Cliente para interactuar con la base de datos local PostgreSQL
Versión mejorada con manejo robusto de errores y timeouts para Jetson Nano
"""

import json
import psycopg2
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from backend.config import Config, get_logger
import os

logger = get_logger(__name__)

class LocalPostgresClient:
    """Cliente para operaciones con la base de datos local PostgreSQL con manejo robusto de errores"""
    
    def __init__(self):
        # Configuración mejorada de timeouts para Jetson Nano
        self.connection_timeout = 15  # Aumentado de 3s a 15s
        self.query_timeout = 30       # Timeout para queries complejas
        self.max_retries = 3          # Máximo 3 reintentos
        self.retry_delay = 2          # 2 segundos entre reintentos
        
        # Estado de conexión
        self.conn = None
        self.last_connection_attempt = 0
        self.connection_failures = 0
        
        # Intentar conexión inicial
        self._connect_with_retry()

    def _connect_with_retry(self) -> bool:
        """Conectar a PostgreSQL con reintentos automáticos"""
        for attempt in range(self.max_retries):
            try:
                self.last_connection_attempt = time.time()
                
                # Configuración de conexión optimizada para Jetson Nano
                self.conn = psycopg2.connect(
                    dbname=os.getenv('DB_NAME', 'iot_db'),
                    user=os.getenv('DB_USER', 'iot_user'),
                    password=os.getenv('DB_PASSWORD', 'DAms15820'),
                    host=os.getenv('DB_HOST', 'localhost'),
                    port=os.getenv('DB_PORT', '5432'),
                    connect_timeout=self.connection_timeout,
                    # Configuraciones adicionales para estabilidad
                    options='-c statement_timeout=30000'  # 30s timeout para statements
                )
                
                # Configurar autocommit para operaciones simples
                self.conn.autocommit = True
                
                logger.info(f"✅ Conexión PostgreSQL establecida (intento {attempt + 1}/{self.max_retries})")
                self.connection_failures = 0
                return True
                
            except psycopg2.OperationalError as e:
                self.connection_failures += 1
                logger.warning(f"⚠️  Intento {attempt + 1}/{self.max_retries} falló: {e}")
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Backoff exponencial
                    logger.info(f"🔄 Reintentando en {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"💥 Falló conexión PostgreSQL tras {self.max_retries} intentos")
                    self.conn = None
                    
            except Exception as e:
                logger.error(f"❌ Error inesperado conectando a PostgreSQL: {e}")
                self.conn = None
                break
        
        return False

    def _ensure_connection(self) -> bool:
        """Asegurar que la conexión esté activa, reconectar si es necesario"""
        try:
            # Verificar si la conexión está activa
            if self.conn and not self.conn.closed:
                # Test rápido de conectividad
                with self.conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                return True
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            logger.warning("🔌 Conexión PostgreSQL perdida, intentando reconectar...")
        except Exception as e:
            logger.warning(f"⚠️  Error verificando conexión: {e}")
        
        # Reconectar si es necesario
        return self._connect_with_retry()

    def _execute_with_retry(self, query: str, params: tuple = None) -> Optional[List[Dict]]:
        """Ejecutar query con reintentos automáticos y manejo de errores"""
        
        for attempt in range(self.max_retries):
            try:
                # Asegurar conexión activa
                if not self._ensure_connection():
                    logger.error(f"No se pudo establecer conexión (intento {attempt + 1})")
                    continue
                
                with self.conn.cursor() as cur:
                    # Ejecutar query con timeout
                    if params:
                        cur.execute(query, params)
                    else:
                        cur.execute(query)
                    
                    # Si es SELECT, retornar resultados
                    if query.strip().upper().startswith('SELECT'):
                        columns = [desc[0] for desc in cur.description]
                        rows = cur.fetchall()
                        data = [dict(zip(columns, row)) for row in rows]
                        
                        # Convertir timestamps para serialización JSON
                        for row in data:
                            for key, value in row.items():
                                if hasattr(value, 'isoformat'):
                                    row[key] = value.isoformat()
                        
                        return data
                    else:
                        # Para INSERT/UPDATE/DELETE, retornar número de filas afectadas
                        return [{"affected_rows": cur.rowcount}]
                
            except psycopg2.OperationalError as e:
                logger.warning(f"🔄 Error operacional PostgreSQL (intento {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"💥 Query falló tras {self.max_retries} intentos: {query[:100]}...")
                    
            except psycopg2.DatabaseError as e:
                logger.error(f"❌ Error de base de datos: {e}")
                break  # No reintentar errores de BD (syntax, constraints, etc.)
                
            except Exception as e:
                logger.error(f"❌ Error inesperado ejecutando query: {e}")
                break
        
        return None

    def get_recent_data(self, device_id: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Obtener los datos más recientes de un dispositivo con manejo robusto de errores"""
        query = """
            SELECT * FROM sensor_data 
            WHERE device_id = %s 
            ORDER BY timestamp DESC 
            LIMIT %s OFFSET %s
        """
        
        try:
            result = self._execute_with_retry(query, (device_id, limit, offset))
            if result is not None:
                logger.debug(f"📊 Obtenidos {len(result)} registros recientes para {device_id}")
                return result
            else:
                logger.warning(f"⚠️  No se pudieron obtener datos recientes para {device_id}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo datos recientes de {device_id}: {e}")
            return []

    def get_data_by_hours(self, device_id: str, hours: float) -> List[Dict]:
        """Obtener datos de un dispositivo desde las últimas N horas con manejo robusto"""
        query = """
            SELECT * FROM sensor_data 
            WHERE device_id = %s AND timestamp >= NOW() - INTERVAL '%s hours'
            ORDER BY timestamp DESC
        """
        
        try:
            result = self._execute_with_retry(query, (device_id, hours))
            if result is not None:
                logger.debug(f"📊 Obtenidos {len(result)} registros ({hours}h) para {device_id}")
                return result
            else:
                logger.warning(f"⚠️  No se pudieron obtener datos por horas para {device_id}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo datos por horas de {device_id}: {e}")
            return []

    def get_data_by_days(self, device_id: str, days: int) -> List[Dict]:
        """Obtener datos de un dispositivo desde los últimos N días con manejo robusto"""
        query = """
            SELECT * FROM sensor_data 
            WHERE device_id = %s AND timestamp >= NOW() - INTERVAL '%s days'
            ORDER BY timestamp DESC
        """
        
        try:
            result = self._execute_with_retry(query, (device_id, days))
            if result is not None:
                logger.debug(f"📊 Obtenidos {len(result)} registros ({days}d) para {device_id}")
                return result
            else:
                logger.warning(f"⚠️  No se pudieron obtener datos por días para {device_id}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo datos por días de {device_id}: {e}")
            return []

    def get_all_data_by_hours(self, hours: float) -> List[Dict]:
        """Obtener datos de todos los dispositivos desde las últimas N horas con manejo robusto"""
        query = """
            SELECT * FROM sensor_data 
            WHERE timestamp >= NOW() - INTERVAL '%s hours'
            ORDER BY timestamp DESC
        """
        
        try:
            result = self._execute_with_retry(query, (hours,))
            if result is not None:
                logger.debug(f"📊 Obtenidos {len(result)} registros totales ({hours}h)")
                return result
            else:
                logger.warning(f"⚠️  No se pudieron obtener datos globales por horas")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo datos globales por horas: {e}")
            return []

    def get_all_data_by_days(self, days: int) -> List[Dict]:
        """Obtener datos de todos los dispositivos desde los últimos N días con manejo robusto"""
        query = """
            SELECT * FROM sensor_data 
            WHERE timestamp >= NOW() - INTERVAL '%s days'
            ORDER BY timestamp DESC
        """
        
        try:
            result = self._execute_with_retry(query, (days,))
            if result is not None:
                logger.debug(f"📊 Obtenidos {len(result)} registros totales ({days}d)")
                return result
            else:
                logger.warning(f"⚠️  No se pudieron obtener datos globales por días")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo datos globales por días: {e}")
            return []

    def get_devices(self) -> List[Dict]:
        """Obtener lista de todos los dispositivos con manejo robusto"""
        query = "SELECT * FROM devices ORDER BY last_seen DESC"
        
        try:
            result = self._execute_with_retry(query)
            if result is not None:
                logger.debug(f"📊 Obtenidos {len(result)} dispositivos")
                return result
            else:
                logger.warning(f"⚠️  No se pudieron obtener dispositivos")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo dispositivos: {e}")
            return []

    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Ejecutar una consulta SQL personalizada y devolver los resultados"""
        if not self.conn:
            return []
        try:
            with self.conn.cursor() as cur:
                if params:
                    cur.execute(query, params)
                else:
                    cur.execute(query)
                columns = [desc[0] for desc in cur.description]
                data = [dict(zip(columns, row)) for row in cur.fetchall()]
                
                # Convertir timestamps a string para serialización
                for row in data:
                    if 'timestamp' in row and hasattr(row['timestamp'], 'isoformat'):
                        row['timestamp'] = row['timestamp'].isoformat()
                        
            return data
        except Exception as e:
            logger.error(f"Error ejecutando consulta personalizada: {e}")
            return []

    def get_system_events(self, limit: int = 50) -> List[Dict]:
        """Obtener los eventos recientes del sistema desde la base de datos local PostgreSQL"""
        if not self.conn:
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT * FROM system_events ORDER BY timestamp DESC LIMIT %s;", (limit,))
                columns = [desc[0] for desc in cur.description]
                events = [dict(zip(columns, row)) for row in cur.fetchall()]
            return events
        except Exception as e:
            logger.error(f"Error obteniendo eventos del sistema desde la base local: {e}")
            return []
    
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

    def register_device(self, device_data: Dict[str, Any]) -> bool:
        """Registrar o actualizar un dispositivo en la base de datos local PostgreSQL"""
        if not self.conn:
            return False
        try:
            with self.conn.cursor() as cur:
                # Preparar metadata JSON si viene como dict
                metadata = device_data.get('metadata')
                try:
                    metadata_json = json.dumps(metadata) if isinstance(metadata, dict) else metadata
                except Exception:
                    metadata_json = None

                # Intentar insertar, si existe actualizarlo (incluir ip_address/port/name/metadata)
                cur.execute("""
                    INSERT INTO devices (
                        device_id, device_type, name, ip_address, port, status, metadata, last_seen, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()), NOW())
                    ON CONFLICT (device_id) DO UPDATE SET
                        device_type = EXCLUDED.device_type,
                        name = COALESCE(EXCLUDED.name, devices.name),
                        ip_address = COALESCE(EXCLUDED.ip_address, devices.ip_address),
                        port = COALESCE(EXCLUDED.port, devices.port),
                        status = EXCLUDED.status,
                        metadata = COALESCE(EXCLUDED.metadata, devices.metadata),
                        last_seen = EXCLUDED.last_seen,
                        updated_at = NOW();
                """, (
                    device_data.get('device_id'),
                    device_data.get('device_type'),
                    device_data.get('name'),
                    device_data.get('ip_address'),
                    device_data.get('port'),
                    device_data.get('status', 'online'),
                    metadata_json,
                    device_data.get('last_seen', datetime.now().isoformat()),
                    device_data.get('created_at')
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
                            metadata = device_data.get('metadata')
                            try:
                                metadata_json = json.dumps(metadata) if isinstance(metadata, dict) else metadata
                            except Exception:
                                metadata_json = None

                            cur.execute("""
                                INSERT INTO devices (
                                    device_id, device_type, name, ip_address, port, status, metadata, last_seen, created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()), NOW())
                                ON CONFLICT (device_id) DO UPDATE SET
                                    device_type = EXCLUDED.device_type,
                                    name = COALESCE(EXCLUDED.name, devices.name),
                                    ip_address = COALESCE(EXCLUDED.ip_address, devices.ip_address),
                                    port = COALESCE(EXCLUDED.port, devices.port),
                                    status = EXCLUDED.status,
                                    metadata = COALESCE(EXCLUDED.metadata, devices.metadata),
                                    last_seen = EXCLUDED.last_seen,
                                    updated_at = NOW();
                            """, (
                                device_data.get('device_id'),
                                device_data.get('device_type'),
                                device_data.get('name'),
                                device_data.get('ip_address'),
                                device_data.get('port'),
                                device_data.get('status', 'online'),
                                metadata_json,
                                device_data.get('last_seen', datetime.now().isoformat()),
                                device_data.get('created_at')
                            ))
                            self.conn.commit()
                        logger.info(f"Dispositivo registrado tras reconexión: {device_data.get('device_id')}")
                        return True
                    except Exception as e2:
                        logger.error(f"Error tras reconexión registrando dispositivo: {e2}")
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
        # Preferir device_type reportado dentro de raw_data si existe
        device_type = sensor_data_clean.get('raw_data', {}).get('device_type') or sensor_data_clean.get('device_type', 'arduino_ethernet')
        if device_id:
            try:
                # Extraer IP/port/metadata desde raw_data si están presentes
                raw = sensor_data_clean.get('raw_data', {}) or {}
                ip_addr = raw.get('ip') or raw.get('ip_address')
                port_val = raw.get('port') or sensor_data_clean.get('port')

                device_data = {
                    'device_id': device_id,
                    'device_type': device_type,
                    'status': 'online',
                    'last_seen': datetime.now(timezone.utc).isoformat(),
                    'ip_address': ip_addr,
                    'port': port_val,
                    'metadata': raw
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
