#!/usr/bin/env python3
"""
Script de diagnóstico para Arduino USB
Detecta problemas de conexión y comunicación
"""

import serial
import serial.tools.list_ports
import time
import json
import sys
from datetime import datetime

def detect_arduino_ports():
    """Detectar puertos Arduino disponibles"""
    print("🔍 Buscando puertos Arduino...")
    
    arduino_ports = []
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        # Buscar Arduino por VID/PID o descripción
        if (port.vid == 0x2341 or  # Arduino VID
            'arduino' in port.description.lower() or
            'uno' in port.description.lower() or
            'acm' in port.device.lower()):
            
            arduino_ports.append({
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid,
                'vid': port.vid,
                'pid': port.pid,
                'serial_number': port.serial_number
            })
            
    return arduino_ports

def test_serial_connection(port_device, baudrate=9600):
    """Probar conexión serial con el Arduino"""
    print(f"📡 Probando conexión en {port_device} a {baudrate} baud...")
    
    try:
        # Intentar conexión
        ser = serial.Serial(port_device, baudrate, timeout=2)
        time.sleep(2)  # Esperar reset del Arduino
        
        print(f"✅ Conexión establecida en {port_device}")
        
        # Limpiar buffer
        ser.flushInput()
        ser.flushOutput()
        
        # Enviar comando de prueba
        test_commands = [
            b'STATUS\n',
            b'READ_NOW\n',
            b'ping\n',
            b'\n'
        ]
        
        for cmd in test_commands:
            print(f"📤 Enviando: {cmd.decode().strip()}")
            ser.write(cmd)
            time.sleep(1)
            
            # Leer respuesta
            response_data = []
            start_time = time.time()
            
            while time.time() - start_time < 3:
                if ser.in_waiting > 0:
                    try:
                        line = ser.readline().decode('utf-8').strip()
                        if line:
                            response_data.append(line)
                            print(f"📥 Recibido: {line}")
                            
                            # Intentar parsear como JSON
                            try:
                                json_data = json.loads(line)
                                print(f"📊 JSON válido: {json_data}")
                            except:
                                print(f"📝 Texto plano: {line}")
                    except Exception as e:
                        print(f"❌ Error leyendo: {e}")
                time.sleep(0.1)
            
            if not response_data:
                print("⚠️  Sin respuesta a este comando")
            
            print("─" * 50)
        
        # Monitoreo continuo por 10 segundos
        print("🔄 Monitoreando datos automáticos por 10 segundos...")
        start_time = time.time()
        
        while time.time() - start_time < 10:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[{timestamp}] 📥 {line}")
                        
                        # Verificar si es JSON válido
                        try:
                            data = json.loads(line)
                            if 'sensors' in data:
                                sensors = data['sensors']
                                print(f"    🌡️  Temp1: {sensors.get('temperature_1', 'N/A')}°C")
                                print(f"    🌡️  Temp2: {sensors.get('temperature_2', 'N/A')}°C")
                                print(f"    🌡️  Temp3: {sensors.get('temperature_3', 'N/A')}°C")
                                print(f"    💡 Luz: {sensors.get('light_level', 'N/A')}%")
                except Exception as e:
                    print(f"❌ Error procesando datos: {e}")
            
            time.sleep(0.1)
        
        ser.close()
        return True
        
    except serial.SerialException as e:
        print(f"❌ Error de conexión serial: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def check_system_resources():
    """Verificar recursos del sistema"""
    print("💻 Verificando recursos del sistema...")
    
    try:
        # Verificar memoria
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
            for line in lines[:3]:
                print(f"   {line.strip()}")
        
        # Verificar carga del sistema
        with open('/proc/loadavg', 'r') as f:
            load = f.read().strip()
            print(f"   Load average: {load}")
            
        # Verificar procesos que usan puertos seriales
        import subprocess
        try:
            result = subprocess.run(['lsof', '/dev/ttyACM*'], 
                                  capture_output=True, text=True)
            if result.stdout:
                print("⚠️  Procesos usando puertos seriales:")
                print(result.stdout)
            else:
                print("✅ No hay procesos bloqueando puertos seriales")
        except:
            print("ℹ️  No se pudo verificar procesos (lsof no disponible)")
            
    except Exception as e:
        print(f"❌ Error verificando recursos: {e}")

def main():
    """Función principal de diagnóstico"""
    print("🔧 DIAGNÓSTICO ARDUINO USB")
    print("=" * 50)
    
    # 1. Verificar recursos del sistema
    check_system_resources()
    print("\n")
    
    # 2. Detectar puertos Arduino
    arduino_ports = detect_arduino_ports()
    
    if not arduino_ports:
        print("❌ No se encontraron puertos Arduino")
        print("\n📋 Verificaciones recomendadas:")
        print("   1. Verificar que el Arduino esté conectado")
        print("   2. Comprobar el cable USB")
        print("   3. Revisar que el Arduino esté encendido")
        print("   4. Ejecutar: lsusb | grep Arduino")
        return False
    
    print(f"✅ Encontrados {len(arduino_ports)} puerto(s) Arduino:")
    for i, port in enumerate(arduino_ports):
        print(f"   {i+1}. {port['device']} - {port['description']}")
        print(f"      Hardware ID: {port['hwid']}")
        print(f"      VID:PID: {port['vid']:04x}:{port['pid']:04x}")
        print(f"      Serial: {port['serial_number']}")
    
    print("\n")
    
    # 3. Probar cada puerto detectado
    success_count = 0
    for port in arduino_ports:
        print(f"🔍 Probando puerto: {port['device']}")
        print("─" * 50)
        
        # Probar diferentes velocidades
        baudrates = [9600, 115200, 57600, 38400]
        port_success = False
        
        for baudrate in baudrates:
            if test_serial_connection(port['device'], baudrate):
                success_count += 1
                port_success = True
                break
        
        if not port_success:
            print(f"❌ No se pudo establecer comunicación con {port['device']}")
        
        print("\n")
    
    # 4. Resumen
    print("📊 RESUMEN DEL DIAGNÓSTICO")
    print("=" * 50)
    print(f"Puertos Arduino encontrados: {len(arduino_ports)}")
    print(f"Puertos con comunicación exitosa: {success_count}")
    
    if success_count == 0:
        print("\n🔧 POSIBLES SOLUCIONES:")
        print("1. Verificar código Arduino (debe estar programado)")
        print("2. Presionar el botón RESET del Arduino")
        print("3. Desconectar y reconectar el USB")
        print("4. Revisar la configuración del puerto en config.py")
        print("5. Verificar permisos: sudo usermod -a -G dialout $USER")
        print("6. Reiniciar el servicio o aplicación que use el puerto")
        
        return False
    else:
        print("✅ Arduino funcionando correctamente")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
