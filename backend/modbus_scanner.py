"""
Escáner y cliente para dispositivos Modbus
"""
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from backend.config import Config, get_logger
from backend.db_writer import SupabaseClient

logger = get_logger(__name__)

class ModbusScanner:
    """Escáner y lector para dispositivos Modbus"""
    
    def __init__(self, db_client: SupabaseClient):
        self.db_client = db_client
        self.modbus_devices = []
        self.clients = {}
    
    def scan_modbus_tcp(self, ip_list: List[str]) -> List[Dict[str, Any]]:
        """Escanear dispositivos Modbus TCP"""
        discovered = []
        
        for ip in ip_list:
            try:
                # Probar conexión Modbus TCP
                client = ModbusTcpClient(
                    host=ip, 
                    port=Config.MODBUS_PORT, 
                    timeout=Config.MODBUS_TIMEOUT
                )
                
                if client.connect():
                    logger.info(f"Dispositivo Modbus TCP encontrado: {ip}")
                    
                    # Intentar leer registros para identificar dispositivo
                    device_info = self._identify_modbus_device(client, ip)
                    
                    if device_info:
                        device_id = f"modbus_tcp_{ip.replace('.', '_')}"
                        device_data = {
                            'device_id': device_id,
                            'device_type': 'modbus_tcp',
                            'name': f'Modbus TCP {ip}',
                            'ip_address': ip,
                            'port': Config.MODBUS_PORT,
                            'status': 'online',
                            'metadata': {
                                'protocol': 'modbus_tcp',
                                'unit_id': device_info.get('unit_id', 1),
                                'registers': device_info.get('registers', [])
                            }
                        }
                        
                        # Registrar dispositivo
                        self.db_client.register_device(device_data)
                        self.db_client.log_system_event(
                            'device_connected', 
                            device_id, 
                            f'Dispositivo Modbus TCP conectado: {ip}'
                        )
                        
                        discovered.append(device_data)
                        
                        # Guardar cliente para uso posterior
                        self.clients[device_id] = client
                    else:
                        client.close()
                
            except Exception as e:
                logger.error(f"Error escaneando Modbus TCP {ip}: {e}")
                continue
        
        return discovered
    
    def _identify_modbus_device(self, client: ModbusTcpClient, ip: str) -> Optional[Dict[str, Any]]:
        """Identificar dispositivo Modbus leyendo registros comunes"""
        device_info = {'registers': []}
        
        # Rangos de registros comunes para probar
        test_ranges = [
            {'start': 0, 'count': 10, 'type': 'holding'},
            {'start': 10000, 'count': 10, 'type': 'holding'},
            {'start': 30000, 'count': 10, 'type': 'holding'},
            {'start': 40000, 'count': 10, 'type': 'holding'},
        ]
        
        for unit_id in [1, 2, 3]:  # Probar diferentes unit IDs
            try:
                for test_range in test_ranges:
                    # Leer registros holding
                    result = client.read_holding_registers(
                        address=test_range['start'],
                        count=test_range['count'],
                        unit=unit_id
                    )
                    
                    if not result.isError():
                        device_info['unit_id'] = unit_id
                        device_info['registers'].append({
                            'type': test_range['type'],
                            'start': test_range['start'],
                            'count': test_range['count'],
                            'accessible': True
                        })
                        
                        logger.info(f"Registros Modbus accesibles en {ip} unit {unit_id}: {test_range['start']}-{test_range['start'] + test_range['count'] - 1}")
                        
                        # Si encontramos al menos un rango, consideramos identificado
                        if len(device_info['registers']) >= 1:
                            return device_info
                
            except Exception as e:
                logger.debug(f"Error probando unit ID {unit_id} en {ip}: {e}")
                continue
        
        return None if not device_info['registers'] else device_info
    
    def read_modbus_data(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Leer datos de dispositivo Modbus"""
        if device_id not in self.clients:
            logger.error(f"Cliente Modbus no encontrado para {device_id}")
            return None
        
        client = self.clients[device_id]
        data_points = []
        
        try:
            # Obtener metadata del dispositivo
            devices = self.db_client.get_devices()
            device_metadata = None
            
            for device in devices:
                if device['device_id'] == device_id:
                    device_metadata = device.get('metadata', {})
                    break
            
            if not device_metadata:
                return None
            
            unit_id = device_metadata.get('unit_id', 1)
            registers = device_metadata.get('registers', [])
            
            for register_info in registers:
                try:
                    # Leer registros según tipo
                    if register_info['type'] == 'holding':
                        result = client.read_holding_registers(
                            address=register_info['start'],
                            count=register_info['count'],
                            unit=unit_id
                        )
                        
                        if not result.isError():
                            for i, value in enumerate(result.registers):
                                register_address = register_info['start'] + i
                                
                                data_point = {
                                    'device_id': device_id,
                                    'sensor_type': f'modbus_register_{register_address}',
                                    'value': value,
                                    'unit': '',
                                    'raw_data': {
                                        'register_address': register_address,
                                        'register_type': 'holding',
                                        'unit_id': unit_id
                                    },
                                    'timestamp': datetime.now(timezone.utc).isoformat()  # Siempre UTC ISO8601
                                }
                                
                                data_points.append(data_point)
                                
                                # Insertar en base de datos
                                self.db_client.insert_sensor_data(data_point)
                
                except Exception as e:
                    logger.error(f"Error leyendo registro {register_info}: {e}")
                    continue
            
            if data_points:
                logger.debug(f"Datos Modbus leídos de {device_id}: {len(data_points)} puntos")
                
                # Actualizar estado del dispositivo
                self.db_client.update_device_status(device_id, 'online')
            
            return data_points
            
        except Exception as e:
            logger.error(f"Error leyendo datos Modbus de {device_id}: {e}")
            
            # Marcar dispositivo como error
            self.db_client.update_device_status(device_id, 'error')
            return None
    
    def read_all_modbus_devices(self) -> Dict[str, List[Dict[str, Any]]]:
        """Leer datos de todos los dispositivos Modbus"""
        all_data = {}
        
        for device_id in self.clients.keys():
            data = self.read_modbus_data(device_id)
            if data:
                all_data[device_id] = data
        
        return all_data
    
    def close_all_connections(self):
        """Cerrar todas las conexiones Modbus"""
        for device_id, client in self.clients.items():
            try:
                client.close()
                logger.info(f"Conexión Modbus cerrada: {device_id}")
            except Exception as e:
                logger.error(f"Error cerrando conexión Modbus {device_id}: {e}")
        
        self.clients.clear()
