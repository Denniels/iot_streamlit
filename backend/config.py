"""
Configuración y utilidades compartidas para el backend IoT
"""
import os
import logging
from dotenv import load_dotenv
from typing import Optional

# Cargar variables de entorno
load_dotenv('.env.local')

class Config:
    """Configuración central de la aplicación"""
    
    # Supabase
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
    
    # API
    API_HOST = os.getenv('API_HOST', '0.0.0.0')
    API_PORT = int(os.getenv('API_PORT', 8000))
    
    # Serial/USB
    USB_PORT = os.getenv('USB_PORT', '/dev/ttyUSB0')
    USB_BAUDRATE = int(os.getenv('USB_BAUDRATE', 9600))
    
    # Network
    NETWORK_INTERFACE = os.getenv('NETWORK_INTERFACE', 'eth0')
    SCAN_TIMEOUT = int(os.getenv('SCAN_TIMEOUT', 5))
    
    # Modbus
    MODBUS_PORT = int(os.getenv('MODBUS_PORT', 502))
    MODBUS_TIMEOUT = int(os.getenv('MODBUS_TIMEOUT', 3))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

def setup_logging():
    """Configurar logging para toda la aplicación"""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('iot_backend.log'),
            logging.StreamHandler()
        ]
    )

def get_logger(name: str) -> logging.Logger:
    """Obtener logger configurado"""
    return logging.getLogger(name)
