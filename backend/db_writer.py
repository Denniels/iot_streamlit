"""
Cliente para interactuar con la base de datos local PostgreSQL
"""
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from backend.config import Config, get_logger

logger = get_logger(__name__)

class LocalPostgresClient:
    def get_system_events(self, limit: int = 50) -> List[Dict]:
        """Obtener los eventos recientes del sistema desde la base de datos local PostgreSQL"""
        if not self.client:
            return []
        try:
            result = self.client.table('system_events').select('*').order('timestamp', desc=True).limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error obteniendo eventos del sistema desde la base local: {e}")
            return []
    """Cliente para operaciones con la base de datos local PostgreSQL"""
    
    def __init__(self):
        try:
            self.client: Client = create_client(
                Config.SUPABASE_URL,
                Config.SUPABASE_SERVICE_KEY or Config.SUPABASE_KEY
            )
            logger.info("Conexión a la base de datos local PostgreSQL establecida (LocalPostgresClient)")
        except Exception as e:
            logger.error(f"Error conectando a la base de datos local PostgreSQL: {e}")
            self.client = None
    
    def register_device(self, device_data: Dict[str, Any]) -> bool:
        """Registrar o actualizar un dispositivo en la base de datos local PostgreSQL"""
        if not self.client:
            return False
        try:
            # Intentar insertar, si existe actualizarlo
            result = self.client.table('devices').upsert(
                device_data,
                on_conflict='device_id'
            ).execute()
            logger.info(f"Dispositivo registrado en base local: {device_data.get('device_id')}")
            return True
        except Exception as e:
            logger.error(f"Error registrando dispositivo en base local: {e}")
            return False
    
    def insert_sensor_data(self, sensor_data: Dict[str, Any]) -> bool:
        """Registrar el dispositivo si no existe y luego insertar/upsert datos de sensor en la base de datos local PostgreSQL evitando duplicados"""
        import requests
        if not self.client:
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
            # Forzar timestamp a string ISO8601 (UTC)
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

        # Registrar el dispositivo si no existe
        device_id = sensor_data_clean.get('device_id')
        device_type = sensor_data_clean.get('raw_data', {}).get('device_type') or sensor_data_clean.get('device_type', 'arduino_ethernet')
        if device_id:
            try:
                existing = self.client.table('devices').select('device_id').eq('device_id', device_id).execute()
                if not existing.data:
                    device_data = {
                        'device_id': device_id,
                        'device_type': device_type,
                        'status': 'online',
                        'last_seen': datetime.now().isoformat()
                    }
                    self.register_device(device_data)
            except Exception as e:
                logger.error(f"Error verificando/registrando dispositivo en base local: {e}")

        # Upsert manual (simulado) en base local
        try:
            logger.error(f"Intentando UPSERT en base de datos local: {json.dumps(sensor_data_clean, default=str)}")
            url = f"{Config.SUPABASE_URL}/rest/v1/sensor_data_clean"
            headers = {
                "apikey": Config.SUPABASE_SERVICE_KEY or Config.SUPABASE_KEY,
                "Authorization": f"Bearer {Config.SUPABASE_SERVICE_KEY or Config.SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            }
            params = [
                ("on_conflict", "device_id"),
                ("on_conflict", "sensor_type"),
                ("on_conflict", "timestamp")
            ]
            response = requests.post(url, headers=headers, params=params, data=json.dumps([sensor_data_clean]), timeout=10)
            if response.status_code in (200, 201, 204):
                logger.debug(f"Datos upsert para dispositivo en base local: {sensor_data_clean.get('device_id')}")
                return True
            else:
                logger.error(f"Error upsert datos de sensor en base local: {response.status_code} {response.text}")
                logger.error(f"Objeto problemático: {json.dumps(sensor_data_clean, default=str)}")
                return False
        except Exception as e:
            logger.error(f"Error upsert datos de sensor en base local: {e}")
            logger.error(f"Objeto problemático: {json.dumps(sensor_data_clean, default=str)}")
            return False
    
    def update_device_status(self, device_id: str, status: str) -> bool:
        """Actualizar estado de dispositivo en la base de datos local PostgreSQL"""
        if not self.client:
            return False
        try:
            result = self.client.table('devices').update({
                'status': status,
                'last_seen': datetime.now().isoformat()
            }).eq('device_id', device_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error actualizando estado del dispositivo {device_id} en base local: {e}")
            return False
    
    def log_system_event(self, event_type: str, device_id: Optional[str] = None, 
                        message: str = "", metadata: Optional[Dict] = None) -> bool:
        """Registrar evento del sistema en la base de datos local PostgreSQL"""
        if not self.client:
            return False
        try:
            event_data = {
                'event_type': event_type,
                'message': message,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            if device_id:
                event_data['device_id'] = device_id
            if metadata:
                event_data['metadata'] = metadata
            result = self.client.table('system_events').insert(event_data).execute()
            return True
        except Exception as e:
            logger.error(f"Error registrando evento del sistema en base local: {e}")
            return False
    
    def get_devices(self) -> List[Dict]:
        """Obtener todos los dispositivos desde la base de datos local PostgreSQL"""
        if not self.client:
            return []
        try:
            result = self.client.table('devices').select('*').execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error obteniendo dispositivos desde base local: {e}")
            return []
    
    def get_latest_sensor_data(self, limit: int = 100) -> List[Dict]:
        """Obtener datos más recientes de sensores desde la base de datos local PostgreSQL"""
        if not self.client:
            return []
        try:
            result = self.client.table('sensor_data_clean').select('*').order('timestamp', desc=True).limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error obteniendo datos de sensores desde base local: {e}")
            return []
