#!/usr/bin/env python3
"""
Script de adquisición de datos desde dispositivos de red (ESP32 WiFi y Arduino Ethernet)
"""
import json
import sys
import time
from datetime import datetime, timezone
from backend.data_acquisition import DataAcquisition
from backend.config import get_logger, setup_logging

from backend.config import Config
setup_logging(Config.ACQUIRE_LOG)
logger = get_logger(__name__)


def main():
    logger.info("Iniciando adquisición de datos de dispositivos de red (ESP32 WiFi y Arduino Ethernet)...")
    
    # Usar el coordinador de adquisición de datos
    acquisition = DataAcquisition()
    
    # Debug: verificar conexión a base de datos
    if acquisition.db_client.conn:
        logger.info("✅ Cliente de base de datos conectado exitosamente")
        print("✅ Cliente de base de datos conectado exitosamente")
    else:
        logger.error("❌ Cliente de base de datos NO conectado")
        print("❌ Cliente de base de datos NO conectado")
        
    logger.info("🔍 Inicializando detección de dispositivos de red...")
    print("🔍 Inicializando detección de dispositivos de red...")
    
    # Inicializar dispositivos (solo red, no USB)
    acquisition.initialize_devices()
    
    logger.info("🚀 Iniciando bucle de adquisición de datos...")
    print("Adquiriendo datos... (Ctrl+C para detener)")
    
    try:
        # Usar adquisición continua cada 10 segundos
        acquisition.start_continuous_acquisition(interval=10)
    except KeyboardInterrupt:
        print("\nAdquisición detenida por el usuario.")
        logger.info("Adquisición detenida por el usuario.")
        acquisition.stop_acquisition()
    except Exception as e:
        logger.error(f"Error en la adquisición: {e}")
        print(f"Error en la adquisición: {e}")
        acquisition.stop_acquisition()
        sys.exit(1)
        
if __name__ == "__main__":
    main()