#!/usr/bin/env python3
"""
Escáner de red para encontrar Arduino Ethernet
"""
import requests
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def check_http_port(ip, port=80, timeout=2):
    """Verificar si un puerto HTTP está abierto"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def check_arduino_endpoints(ip):
    """Probar múltiples endpoints para Arduino"""
    endpoints = ['/', '/data', '/sensor', '/status', '/index.html']
    
    for endpoint in endpoints:
        try:
            url = f'http://{ip}{endpoint}'
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                content = response.text.strip()
                print(f"✅ ENCONTRADO: {ip}{endpoint}")
                print(f"   Respuesta: {content[:200]}...")
                print(f"   Tamaño: {len(content)} bytes")
                return True, endpoint, content
        except Exception as e:
            continue
    
    return False, None, None

def scan_ip_range():
    """Escanear rango de IPs para Arduino"""
    print("🔍 Escaneando red 192.168.0.x para Arduino Ethernet...")
    
    # IPs más probables para Arduino
    priority_ips = [177, 50, 100, 200, 10, 20, 30, 40, 60, 70, 80, 90, 150, 170, 180, 190]
    
    # Agregar más IPs para escaneo completo
    all_ips = priority_ips + [i for i in range(2, 255) if i not in priority_ips]
    
    found_devices = []
    
    # Escanear IPs prioritarias primero
    print(f"🎯 Probando {len(priority_ips)} IPs prioritarias...")
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_ip = {}
        
        for ip_end in priority_ips:
            ip = f"192.168.0.{ip_end}"
            future = executor.submit(scan_single_ip, ip)
            future_to_ip[future] = ip
        
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                result = future.result()
                if result:
                    found_devices.append(result)
                    print(f"⭐ Arduino encontrado en IP prioritaria: {ip}")
            except Exception as e:
                pass
    
    # Si no encontramos nada, escanear todo el rango
    if not found_devices:
        print("🔍 Escaneando rango completo...")
        
        with ThreadPoolExecutor(max_workers=50) as executor:
            future_to_ip = {}
            
            for ip_end in range(2, 255):
                if ip_end not in priority_ips:  # Saltar las ya probadas
                    ip = f"192.168.0.{ip_end}"
                    future = executor.submit(scan_single_ip, ip)
                    future_to_ip[future] = ip
            
            for future in as_completed(future_to_ip):
                ip = future_to_ip[future]
                try:
                    result = future.result()
                    if result:
                        found_devices.append(result)
                        print(f"✅ Arduino encontrado: {ip}")
                except Exception as e:
                    pass
    
    return found_devices

def scan_single_ip(ip):
    """Escanear una IP específica"""
    try:
        # Primero verificar si el puerto 80 está abierto
        if check_http_port(ip, 80, timeout=1):
            print(f"🔍 Puerto 80 abierto en {ip}, probando Arduino...")
            
            # Probar endpoints de Arduino
            found, endpoint, content = check_arduino_endpoints(ip)
            if found:
                return {
                    'ip': ip,
                    'endpoint': endpoint,
                    'content': content,
                    'port': 80
                }
    except Exception as e:
        pass
    
    return None

def main():
    print("🚀 Iniciando escáner de red para Arduino Ethernet")
    print("📍 Red: 192.168.0.x")
    print("⏱️  Esto puede tomar unos minutos...")
    print("-" * 50)
    
    start_time = time.time()
    devices = scan_ip_range()
    end_time = time.time()
    
    print("-" * 50)
    print(f"⏱️  Escaneo completado en {end_time - start_time:.1f} segundos")
    
    if devices:
        print(f"🎉 ¡Encontrados {len(devices)} Arduino(s) Ethernet!")
        for i, device in enumerate(devices, 1):
            print(f"\n📱 Arduino #{i}:")
            print(f"   IP: {device['ip']}")
            print(f"   Endpoint: {device['endpoint']}")
            print(f"   Respuesta: {device['content'][:100]}...")
    else:
        print("❌ No se encontraron dispositivos Arduino Ethernet")
        print("\n💡 Sugerencias:")
        print("   1. Verifica que el Arduino Ethernet esté encendido")
        print("   2. Confirma que está en la red 192.168.0.x")
        print("   3. Revisa la configuración IP del Arduino")
        print("   4. Asegúrate que el servidor web esté corriendo")

if __name__ == "__main__":
    main()
