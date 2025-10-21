#!/usr/bin/env python3
"""
Script de diagnóstico específico para Arduino Ethernet
"""

import requests
import time
import json
from datetime import datetime

def test_arduino_ethernet():
    """Probar específicamente el Arduino Ethernet"""
    print("🌐 DIAGNÓSTICO ARDUINO ETHERNET")
    print("=" * 50)
    
    # IP del Arduino Ethernet (según los logs anteriores)
    arduino_ip = "192.168.0.110"
    url = f"http://{arduino_ip}/status"
    
    print(f"🔍 Probando conexión con: {url}")
    
    try:
        # Hacer petición HTTP GET
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            print(f"✅ Conexión exitosa! Código: {response.status_code}")
            print(f"📊 Contenido recibido:")
            print(f"Raw: {response.text}")
            
            # Intentar parsear como JSON
            try:
                data = response.json()
                print(f"JSON: {json.dumps(data, indent=2)}")
                
                # Mostrar información de sensores
                if isinstance(data, dict):
                    for key, value in data.items():
                        if 'temperature' in key.lower():
                            print(f"🌡️ {key}: {value}°C")
                        elif 'light' in key.lower():
                            print(f"💡 {key}: {value}%")
                        else:
                            print(f"📊 {key}: {value}")
                
                return True
                
            except json.JSONDecodeError:
                print("⚠️ La respuesta no es JSON válido")
                return False
                
        else:
            print(f"❌ Error HTTP: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectTimeout:
        print("❌ Timeout de conexión - Arduino no responde")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Error de conexión - Arduino no accesible")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def test_multiple_requests():
    """Hacer múltiples peticiones para probar estabilidad"""
    print("\n🔄 PRUEBA DE MÚLTIPLES PETICIONES")
    print("-" * 40)
    
    arduino_ip = "192.168.0.110"
    url = f"http://{arduino_ip}/status"
    
    success_count = 0
    total_requests = 5
    
    for i in range(total_requests):
        print(f"Petición {i+1}/{total_requests}...", end=" ")
        
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                print("✅")
                success_count += 1
            else:
                print(f"❌ ({response.status_code})")
        except Exception as e:
            print(f"❌ ({type(e).__name__})")
        
        time.sleep(1)
    
    print(f"\n📊 Resultado: {success_count}/{total_requests} exitosas")
    return success_count > 0

def test_network_connectivity():
    """Probar conectividad de red básica"""
    print("\n🌐 PRUEBA DE CONECTIVIDAD DE RED")
    print("-" * 40)
    
    arduino_ip = "192.168.0.110"
    
    # Ping test
    import subprocess
    try:
        result = subprocess.run(['ping', '-c', '3', arduino_ip], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print(f"✅ Ping exitoso a {arduino_ip}")
            # Extraer tiempo de respuesta
            lines = result.stdout.split('\n')
            for line in lines:
                if 'time=' in line:
                    print(f"⏱️ {line.strip()}")
            return True
        else:
            print(f"❌ Ping falló a {arduino_ip}")
            print(f"Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ Ping timeout a {arduino_ip}")
        return False
    except Exception as e:
        print(f"❌ Error en ping: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 INICIANDO DIAGNÓSTICO COMPLETO ARDUINO ETHERNET")
    print("=" * 60)
    
    # 1. Prueba de conectividad de red
    network_ok = test_network_connectivity()
    
    # 2. Prueba de conexión HTTP
    http_ok = test_arduino_ethernet()
    
    # 3. Prueba de múltiples peticiones (solo si HTTP funciona)
    stability_ok = False
    if http_ok:
        stability_ok = test_multiple_requests()
    
    # Resumen final
    print("\n" + "=" * 60)
    print("📋 RESUMEN DEL DIAGNÓSTICO")
    print("-" * 40)
    print(f"🌐 Conectividad de red: {'✅ OK' if network_ok else '❌ FALLO'}")
    print(f"🔗 Conexión HTTP: {'✅ OK' if http_ok else '❌ FALLO'}")
    print(f"🔄 Estabilidad: {'✅ OK' if stability_ok else '❌ FALLO'}")
    
    if network_ok and http_ok and stability_ok:
        print("\n🎉 ¡ARDUINO ETHERNET FUNCIONANDO CORRECTAMENTE!")
        print("💡 El problema debe estar en la detección automática del servicio")
        print("🔧 Próximo paso: Verificar el código de detección ethernet")
        return True
    else:
        print("\n⚠️ PROBLEMAS DETECTADOS:")
        if not network_ok:
            print("- Arduino no responde a ping (verificar conexión física/IP)")
        if not http_ok:
            print("- Servidor HTTP no funciona (verificar programa Arduino)")
        if not stability_ok and http_ok:
            print("- Conexión inestable (verificar red/Arduino)")
        return False

if __name__ == "__main__":
    main()
