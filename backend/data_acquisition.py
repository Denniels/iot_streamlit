"""
Adquisición y formateo de datos de todos los dispositivos
"""
import asyncio
"""
Adquisición y formateo de datos de todos los dispositivos.

Coordina la lectura de ESP32 (HTTP), Arduino Ethernet (HTTP) y
dispositivos Modbus. Implementa reconciliación automática de IP cuando
una lectura a la IP guardada falla.
"""

import time
from datetime import datetime, timezone
from typing import Dict, Any

from backend.config import get_logger, Config
from backend.db_writer import LocalPostgresClient
from backend.arduino_detector import ArduinoDetector
from backend.device_scanner import DeviceScanner
from backend.modbus_scanner import ModbusScanner

logger = get_logger(__name__)


class DataAcquisition:
    """Coordinator for collecting data from network devices and modbus.

    Responsibilities:
    - Load devices from DB
    - Attempt reads (ESP32 HTTP, Arduino Ethernet HTTP)
    - On ethernet read failure, throttle and run network scan to find device_id
      and update DB via register_device() (reconciliation)
    """

    def __init__(self):
        self.db_client = LocalPostgresClient()
        self.arduino_detector = ArduinoDetector(self.db_client)
        self.device_scanner = DeviceScanner(self.db_client)
        self.modbus_scanner = ModbusScanner(self.db_client)
        self.running = False
        self.data_cache = {}
        # last_reconcile: device_id -> timestamp (seconds) to throttle scans
        self.last_reconcile = {}

    def initialize_devices(self) -> None:
        logger.info("Iniciando detección de dispositivos de red...")
        try:
            discovered_devices = self.device_scanner.scan_network()
            logger.info(f"{len(discovered_devices)} dispositivos de red encontrados")
        except Exception as e:
            logger.error(f"Error escaneando red: {e}")
            discovered_devices = []

        # specialized detections
        try:
            ethernet_arduinos = self.arduino_detector.detect_ethernet_arduinos()
            logger.info(f"{len(ethernet_arduinos)} Arduinos Ethernet detectados")
        except Exception as e:
            logger.error(f"Error detectando Arduinos Ethernet: {e}")

        try:
            esp32_devices = self.arduino_detector.detect_esp32_wifi()
            logger.info(f"{len(esp32_devices)} ESP32 WiFi detectados")
        except Exception as e:
            logger.error(f"Error detectando ESP32 WiFi: {e}")

        try:
            ip_list = [d.get('ip_address') for d in discovered_devices if d.get('ip_address')]
            if ip_list:
                modbus_devices = self.modbus_scanner.scan_modbus_tcp(ip_list)
                logger.info(f"{len(modbus_devices)} dispositivos Modbus detectados")
        except Exception as e:
            logger.error(f"Error detectando Modbus: {e}")

        logger.info("Inicialización de dispositivos completada")

    def collect_all_data(self) -> Dict[str, Any]:
        collected_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'network_devices': [],
            'modbus_devices': {},
            'errors': []
        }

        try:
            devices = self.db_client.get_devices()
        except Exception as e:
            logger.error(f"No se pudo leer la lista de dispositivos desde BD: {e}")
            collected_data['errors'].append(str(e))
            return collected_data

        network_devices = [d for d in devices if d.get('device_type') in ('arduino_ethernet', 'esp32_wifi')]

        for device in network_devices:
            device_id = device.get('device_id')
            device_type = device.get('device_type')
            ip = device.get('ip_address')

            # fallback known IPs for local development (non-destructive)
            if not ip:
                if device_id == 'esp32_wifi_001':
                    ip = '192.168.0.110'
                elif device_id == 'arduino_eth_001':
                    ip = '192.168.0.109'

            if not ip:
                logger.warning(f"Dispositivo {device_id} sin IP configurada")
                collected_data['errors'].append(f"{device_id} sin IP")
                continue

            try:
                data = None
                if device_type == 'esp32_wifi':
                    data = self.arduino_detector.read_esp32_data(ip)
                else:
                    port = int(device.get('port') or 80)
                    data = self.arduino_detector.read_ethernet_data(ip, port, device_id=device_id)

                    # reconciliation flow for ethernet Arduinos
                    if data is None:
                        logger.warning(f"Fallo lectura en {device_id} ({ip}:{port}), intentando reconciliación")
                        now = time.time()
                        last = self.last_reconcile.get(device_id, 0)
                        # throttle según configuración (por defecto 300s)
                        throttle = getattr(Config, 'RECONCILE_THROTTLE', 300)
                        if now - last < throttle:
                            logger.debug(f"Reconciliación omitida para {device_id} (último intento hace {int(now-last)}s, umbral={throttle}s)")
                        else:
                            self.last_reconcile[device_id] = now
                            try:
                                netrange = self.device_scanner.get_network_range()
                                found = None

                                # Intentar resolver por MAC si está presente en metadata o como ARP de la IP antigua
                                try:
                                    meta = device.get('metadata') or {}
                                    if isinstance(meta, str):
                                        import json as _json
                                        try:
                                            meta = _json.loads(meta)
                                        except Exception:
                                            meta = {}

                                    mac = meta.get('mac')
                                    if not mac and device.get('ip_address'):
                                        try:
                                            mac = self.arduino_detector._get_mac_for_ip(device.get('ip_address'))
                                        except Exception:
                                            mac = None

                                    if mac:
                                        try:
                                            # Buscar la IP que tenga esa MAC en la subred
                                            for i in range(1, 255):
                                                candidate_ip = f"{netrange}.{i}"
                                                try:
                                                    cand_mac = self.arduino_detector._get_mac_for_ip(candidate_ip)
                                                except Exception:
                                                    cand_mac = None
                                                if cand_mac and cand_mac.lower() == mac.lower():
                                                    found = {'ip': candidate_ip, 'port': 80, 'mac': mac}
                                                    break
                                        except Exception:
                                            found = None
                                except Exception as e:
                                    logger.debug(f"Error intentando resolver MAC para {device_id}: {e}")

                                # Si no se resolvió por MAC, hacer escaneo completo
                                if not found:
                                    found = self.arduino_detector.find_device_on_network(device_id, netrange)
                            except Exception as e:
                                logger.error(f"Error buscando {device_id} en la red: {e}")
                                found = None

                            if found:
                                new_ip = found.get('ip')
                                new_port = found.get('port') or 80
                                try:
                                    new_port = int(new_port)
                                except Exception:
                                    new_port = 80

                                logger.info(f"Actualizando BD: {device_id} -> {new_ip}:{new_port}")
                                try:
                                    metadata = {'ip': new_ip, 'port': new_port}
                                    if found.get('mac'):
                                        metadata['mac'] = found.get('mac')

                                    self.db_client.register_device({
                                        'device_id': device_id,
                                        'device_type': device_type,
                                        'name': device.get('name'),
                                        'ip_address': new_ip,
                                        'port': new_port,
                                        'status': 'online',
                                        'metadata': metadata
                                    })
                                    self.db_client.log_system_event('device_reconciled', device_id, f'IP actualizada a {new_ip}:{new_port}')
                                except Exception as e:
                                    logger.error(f"Fallo actualizando BD para {device_id}: {e}")

                                # reintentar lectura
                                try:
                                    data = self.arduino_detector.read_ethernet_data(new_ip, new_port, device_id=device_id)
                                except Exception as e:
                                    logger.error(f"Error leyendo desde {new_ip}:{new_port} tras reconciliación: {e}")
                                    data = None

                if data:
                    collected_data['network_devices'].append({
                        'device_id': device_id,
                        'device_type': device_type,
                        'data': data
                    })

            except Exception as e:
                logger.error(f"Error leyendo {device_id} ({ip}): {e}")
                collected_data['errors'].append(str(e))

        # Modbus devices
        try:
            modbus_data = self.modbus_scanner.read_all_modbus_devices()
            collected_data['modbus_devices'] = modbus_data
        except Exception as e:
            logger.error(f"Error leyendo Modbus: {e}")
            collected_data['errors'].append(str(e))

        # cache and return
        self.data_cache = collected_data

        # summary log
        total_points = len(collected_data['network_devices'])
        try:
            total_points += sum(len(v) for v in collected_data['modbus_devices'].values())
        except Exception:
            pass

        logger.debug(f"Datos recopilados: {total_points} puntos de datos")
        return collected_data


    def start_continuous_acquisition(self, interval: int = 10) -> None:
        logger.info(f"Iniciando adquisición continua cada {interval} segundos")
        self.running = True
        while self.running:
            try:
                start = time.time()
                data = self.collect_all_data()
                if data.get('errors'):
                    try:
                        self.db_client.log_system_event('acquisition_errors', None, f"{len(data['errors'])} errores en adquisición", {'errors': data['errors']})
                    except Exception:
                        pass
                elapsed = time.time() - start
                to_sleep = max(0, interval - elapsed)
                logger.debug(f"Ciclo completado en {elapsed:.2f}s, durmiendo {to_sleep:.2f}s")
                if to_sleep > 0:
                    time.sleep(to_sleep)
            except KeyboardInterrupt:
                self.stop_acquisition()
                break
            except Exception as e:
                logger.error(f"Error en loop de adquisición: {e}")
                try:
                    self.db_client.log_system_event('acquisition_error', None, str(e))
                except Exception:
                    pass
                time.sleep(5)


    def stop_acquisition(self) -> None:
        logger.info("[SHUTDOWN] Deteniendo adquisición de datos...")
        self.running = False
        try:
            self.arduino_detector.close_connections()
        except Exception:
            pass
        try:
            self.modbus_scanner.close_all_connections()
        except Exception:
            pass
        try:
            self.db_client.log_system_event('acquisition_stopped', None, 'Adquisición detenida')
        except Exception:
            pass


    def get_current_status(self) -> Dict[str, Any]:
        try:
            devices = self.db_client.get_devices()
        except Exception:
            devices = []
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'running': self.running,
            'devices': {
                'total': len(devices),
                'online': len([d for d in devices if d.get('status') == 'online']),
                'offline': len([d for d in devices if d.get('status') == 'offline']),
                'error': len([d for d in devices if d.get('status') == 'error'])
            },
            'last_data': self.data_cache.get('timestamp'),
            'errors': self.data_cache.get('errors', [])
        }


    def get_latest_data(self) -> Dict[str, Any]:
        return self.data_cache if self.data_cache else {'timestamp': datetime.now(timezone.utc).isoformat(), 'message': 'No hay datos disponibles'}

