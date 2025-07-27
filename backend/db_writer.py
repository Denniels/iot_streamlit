"""
Cliente para interactuar con Supabase
"""
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from backend.config import Config, get_logger

logger = get_logger(__name__)

class SupabaseClient:
    """Cliente para operaciones con Supabase"""
    
    def __init__(self):
        try:
            self.client: Client = create_client(
                Config.SUPABASE_URL,
                Config.SUPABASE_SERVICE_KEY or Config.SUPABASE_KEY
            )
            logger.info("Conexión a Supabase establecida")
        except Exception as e:
            logger.error(f"Error conectando a Supabase: {e}")
            self.client = None
    
    def register_device(self, device_data: Dict[str, Any]) -> bool:
        """Registrar o actualizar un dispositivo"""
        if not self.client:
            return False
        
        try:
            # Intentar insertar, si existe actualizarlo
            result = self.client.table('devices').upsert(
                device_data,
                on_conflict='device_id'
            ).execute()
            
            logger.info(f"Dispositivo registrado: {device_data.get('device_id')}")
            return True
        except Exception as e:
            logger.error(f"Error registrando dispositivo: {e}")
            return False
    
    def insert_sensor_data(self, sensor_data: Dict[str, Any]) -> bool:
        """Insertar datos de sensor"""
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
            try:
                if hasattr(sensor_data_clean['timestamp'], 'isoformat'):
                    sensor_data_clean['timestamp'] = sensor_data_clean['timestamp'].isoformat()
            except Exception:
                pass
        # Eliminar el campo created_at si existe
        sensor_data_clean.pop('created_at', None)

        try:
            # Logging detallado del objeto antes de insertar
            logger.error(f"Intentando insertar en Supabase: {json.dumps(sensor_data_clean, default=str)}")
            result = self.client.table('sensor_data').insert(sensor_data_clean).execute()
            logger.debug(f"Datos insertados para dispositivo: {sensor_data_clean.get('device_id')}")
            return True
        except Exception as e:
            logger.error(f"Error insertando datos de sensor: {e}")
            logger.error(f"Objeto problemático: {json.dumps(sensor_data_clean, default=str)}")
            return False
    
    def update_device_status(self, device_id: str, status: str) -> bool:
        """Actualizar estado de dispositivo"""
        if not self.client:
            return False
        
        try:
            result = self.client.table('devices').update({
                'status': status,
                'last_seen': datetime.now().isoformat()
            }).eq('device_id', device_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error actualizando estado del dispositivo {device_id}: {e}")
            return False
    
    def log_system_event(self, event_type: str, device_id: Optional[str] = None, 
                        message: str = "", metadata: Optional[Dict] = None) -> bool:
        """Registrar evento del sistema"""
        if not self.client:
            return False
        
        try:
            event_data = {
                'event_type': event_type,
                'message': message,
                'timestamp': datetime.now().isoformat()
            }
            
            if device_id:
                event_data['device_id'] = device_id
            if metadata:
                event_data['metadata'] = metadata
            
            result = self.client.table('system_events').insert(event_data).execute()
            return True
        except Exception as e:
            logger.error(f"Error registrando evento del sistema: {e}")
            return False
    
    def get_devices(self) -> List[Dict]:
        """Obtener todos los dispositivos"""
        if not self.client:
            return []
        
        try:
            result = self.client.table('devices').select('*').execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error obteniendo dispositivos: {e}")
            return []
    
    def get_latest_sensor_data(self, limit: int = 100) -> List[Dict]:
        """Obtener datos más recientes de sensores"""
        if not self.client:
            return []
        
        try:
            result = self.client.table('sensor_data').select('*').order('timestamp', desc=True).limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error obteniendo datos de sensores: {e}")
            return []
