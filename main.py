"""
Aplicación principal y orquestador del sistema IoT
"""
import sys
import argparse
import signal
import threading
import time
from backend.config import get_logger, IOT_CONFIG
from backend.data_acquisition import DataAcquisition
from backend.api import run_api_server

logger = get_logger(__name__)

class IoTSystemMain:
    """Clase principal del sistema IoT"""
    
    def __init__(self):
        self.data_acquisition = DataAcquisition()
        self.api_thread = None
        self.acquisition_thread = None
        self.running = False
        
        # Configurar manejo de señales
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Manejo de señales para cierre graceful"""
        logger.info(f"Señal recibida: {signum}")
        self.shutdown()
    
    def initialize_system(self):
        """Inicializar todo el sistema"""
        logger.info("=" * 50)
        logger.info("INICIANDO SISTEMA IOT STREAMLIT")
        logger.info("=" * 50)
        
        try:
            # 1. Verificar configuración
            logger.info("Verificando configuración...")
            required_config = ['supabase_url', 'supabase_key']
            for key in required_config:
                if not IOT_CONFIG.get(key):
                    logger.error(f"Configuración faltante: {key}")
                    return False
            
            # 2. Inicializar detección de dispositivos
            logger.info("Inicializando detección de dispositivos...")
            self.data_acquisition.initialize_devices()
            
            logger.info("Sistema inicializado correctamente ✓")
            return True
            
        except Exception as e:
            logger.error(f"Error en inicialización del sistema: {e}")
            return False
    
    def start_api_server(self):
        """Iniciar servidor API en thread separado"""
        logger.info("Iniciando servidor API...")
        
        def run_api():
            try:
                run_api_server()
            except Exception as e:
                logger.error(f"Error en servidor API: {e}")
        
        self.api_thread = threading.Thread(target=run_api, daemon=True)
        self.api_thread.start()
        
        # Esperar un momento para que el servidor se inicie
        time.sleep(2)
        logger.info("Servidor API iniciado ✓")
    
    def start_data_acquisition(self, interval: int = 10):
        """Iniciar adquisición de datos en thread separado"""
        logger.info(f"Iniciando adquisición de datos (intervalo: {interval}s)...")
        
        def run_acquisition():
            try:
                self.data_acquisition.start_continuous_acquisition(interval)
            except Exception as e:
                logger.error(f"Error en adquisición de datos: {e}")
        
        self.acquisition_thread = threading.Thread(target=run_acquisition, daemon=True)
        self.acquisition_thread.start()
        
        logger.info("Adquisición de datos iniciada ✓")
    
    def run_full_system(self, acquisition_interval: int = 10):
        """Ejecutar sistema completo (API + Adquisición)"""
        if not self.initialize_system():
            logger.error("Error en inicialización. Abortando...")
            return False
        
        try:
            self.running = True
            
            # 1. Iniciar servidor API
            self.start_api_server()
            
            # 2. Iniciar adquisición de datos
            self.start_data_acquisition(acquisition_interval)
            
            logger.info("=" * 50)
            logger.info("SISTEMA IOT COMPLETAMENTE OPERATIVO")
            logger.info("=" * 50)
            logger.info("API disponible en: http://localhost:8000")
            logger.info("Documentación: http://localhost:8000/docs")
            logger.info("Estado del sistema: http://localhost:8000/status")
            logger.info("=" * 50)
            logger.info("Presiona Ctrl+C para detener el sistema")
            
            # Mantener el proceso principal vivo
            while self.running:
                time.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f"Error ejecutando sistema completo: {e}")
            return False
    
    def run_api_only(self):
        """Ejecutar solo la API REST"""
        if not self.initialize_system():
            logger.error("Error en inicialización. Abortando...")
            return False
        
        try:
            logger.info("Ejecutando SOLO servidor API...")
            run_api_server()  # Ejecutar directamente (bloquea)
            return True
            
        except Exception as e:
            logger.error(f"Error ejecutando API: {e}")
            return False
    
    def run_acquisition_only(self, interval: int = 10):
        """Ejecutar solo la adquisición de datos"""
        if not self.initialize_system():
            logger.error("Error en inicialización. Abortando...")
            return False
        
        try:
            logger.info(f"Ejecutando SOLO adquisición de datos (cada {interval}s)...")
            self.data_acquisition.start_continuous_acquisition(interval)
            return True
            
        except Exception as e:
            logger.error(f"Error ejecutando adquisición: {e}")
            return False
    
    def run_scan_only(self):
        """Ejecutar solo escaneo de dispositivos (una vez)"""
        if not self.initialize_system():
            logger.error("Error en inicialización. Abortando...")
            return False
        
        try:
            logger.info("Ejecutando escaneo de dispositivos...")
            
            # Mostrar dispositivos antes
            devices_before = self.data_acquisition.db_client.get_devices()
            logger.info(f"Dispositivos antes del escaneo: {len(devices_before)}")
            
            # Realizar escaneo completo
            logger.info("Escaneando red...")
            discovered = self.data_acquisition.device_scanner.scan_network()
            logger.info(f"Dispositivos de red encontrados: {len(discovered)}")
            
            logger.info("Detectando Arduinos Ethernet...")
            arduinos = self.data_acquisition.arduino_detector.detect_ethernet_arduinos()
            logger.info(f"Arduinos Ethernet encontrados: {len(arduinos)}")
            
            logger.info("Detectando dispositivos Modbus...")
            ip_list = [d.get('ip_address') for d in discovered if d.get('ip_address')]
            if ip_list:
                modbus_devices = self.data_acquisition.modbus_scanner.scan_modbus_tcp(ip_list)
                logger.info(f"Dispositivos Modbus encontrados: {len(modbus_devices)}")
            
            # Mostrar dispositivos después
            devices_after = self.data_acquisition.db_client.get_devices()
            logger.info(f"Dispositivos después del escaneo: {len(devices_after)}")
            
            logger.info("Escaneo completado ✓")
            return True
            
        except Exception as e:
            logger.error(f"Error ejecutando escaneo: {e}")
            return False
    
    def shutdown(self):
        """Cierre graceful del sistema"""
        logger.info("Iniciando cierre del sistema...")
        
        self.running = False
        
        # Detener adquisición de datos
        if self.data_acquisition:
            self.data_acquisition.stop_acquisition()
        
        # Los threads daemon se cerrarán automáticamente
        
        logger.info("Sistema cerrado correctamente ✓")

def main():
    """Función principal con argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(description='Sistema IoT Streamlit')
    
    parser.add_argument(
        '--mode', 
        choices=['full', 'api', 'acquisition', 'scan'],
        default='full',
        help='Modo de ejecución (default: full)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=10,
        help='Intervalo de adquisición en segundos (default: 10)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Activar logging detallado'
    )
    
    args = parser.parse_args()
    
    # Configurar nivel de logging
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("Logging detallado activado")
    
    # Crear instancia del sistema
    system = IoTSystemMain()
    
    # Ejecutar según el modo seleccionado
    success = False
    
    try:
        if args.mode == 'full':
            success = system.run_full_system(args.interval)
        elif args.mode == 'api':
            success = system.run_api_only()
        elif args.mode == 'acquisition':
            success = system.run_acquisition_only(args.interval)
        elif args.mode == 'scan':
            success = system.run_scan_only()
        
    except KeyboardInterrupt:
        logger.info("Interrupción por teclado recibida")
    except Exception as e:
        logger.error(f"Error no manejado: {e}")
        success = False
    finally:
        system.shutdown()
    
    # Código de salida
    exit_code = 0 if success else 1
    logger.info(f"Sistema terminado con código: {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
