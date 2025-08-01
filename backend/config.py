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
    """Configuración central de la aplicación"""
    
    
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
    LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    ACQUIRE_LOG = os.path.join(LOG_DIR, 'acquire_data.log')
    BACKEND_LOG = os.path.join(LOG_DIR, 'iot_backend.log')
    SYNC_LOG = os.path.join(LOG_DIR, 'sync_local_db.log')

    # Base de datos
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 5432))
    DB_NAME = os.getenv('DB_NAME', 'iot_db')
    DB_USER = os.getenv('DB_USER', 'iot_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'iot_password')

def setup_logging(logfile: str = None):
    """Configurar logging para toda la aplicación, permitiendo especificar el archivo de log"""
    if logfile is None:
        logfile = Config.BACKEND_LOG
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logfile),
            logging.StreamHandler()
        ]
    )

def get_logger(name: str) -> logging.Logger:
    """Obtener logger configurado"""
    return logging.getLogger(name)
