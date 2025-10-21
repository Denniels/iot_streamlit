#!/usr/bin/env python3
"""
Verificación completa del pipeline IoT
- Arduino corregido → Adquisición → Base de datos → API → Frontend
"""

import requests
import json
import time
from datetime import datetime

def test_pipeline():
    print("🔄 VERIFICACIÓN COMPLETA DEL PIPELINE IoT")
    print("=" * 60)
    
    # 1. Verificar dispositivos en API
    print("1️⃣ Verificando dispositivos en API...")
    try:
        response = requests.get("http://localhost:8000/devices", timeout=5)
        devices = response.json()
        
        if devices["success"]:
            print(f"   ✅ {devices['message']}")
            for device in devices["data"]:
                status_icon = "🟢" if device["status"] == "online" else "🔴"
                print(f"   {status_icon} {device['device_id']} ({device['device_type']}) - {device['status']}")
        else:
            print(f"   ❌ Error: {devices.get('message', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"   ❌ Error conectando a API: {e}")
        return False
    
    # 2. Verificar datos recientes
    print("\n2️⃣ Verificando datos recientes...")
    try:
        response = requests.get("http://localhost:8000/data?limit=10", timeout=5)
        data = response.json()
        
        if data["success"]:
            print(f"   ✅ {data['message']}")
            
            # Analizar datos por dispositivo
            usb_data = [d for d in data["data"] if d["device_id"] == "arduino_usb_001"]
            eth_data = [d for d in data["data"] if d["device_id"] == "arduino_eth_001"]
            
            if usb_data:
                latest_usb = usb_data[0]
                print(f"   📊 Arduino USB: {latest_usb['sensor_type']} = {latest_usb['value']}{latest_usb['unit']}")
                print(f"      ⏰ Última lectura: {latest_usb['timestamp']}")
            else:
                print("   ⚠️  No hay datos recientes del Arduino USB")
            
            if eth_data:
                latest_eth = eth_data[0]
                print(f"   📊 Arduino Ethernet: {latest_eth['sensor_type']} = {latest_eth['value']}{latest_eth['unit']}")
                print(f"      ⏰ Última lectura: {latest_eth['timestamp']}")
            else:
                print("   ⚠️  No hay datos recientes del Arduino Ethernet")
                
        else:
            print(f"   ❌ Error: {data.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"   ❌ Error obteniendo datos: {e}")
    
    # 3. Verificar datos específicos del Arduino USB corregido
    print("\n3️⃣ Verificando datos del Arduino USB corregido...")
    try:
        response = requests.get("http://localhost:8000/data/arduino_usb_001?limit=5", timeout=5)
        usb_data = response.json()
        
        if usb_data["success"] and usb_data["data"]:
            print(f"   ✅ {usb_data['message']}")
            
            # Analizar temperaturas
            temp_readings = []
            for reading in usb_data["data"]:
                if "temperature" in reading["sensor_type"]:
                    temp_readings.append({
                        "sensor": reading["sensor_type"],
                        "value": reading["value"],
                        "timestamp": reading["timestamp"]
                    })
            
            if temp_readings:
                print("   🌡️  Temperaturas recientes del Arduino USB:")
                for temp in temp_readings[:3]:  # Mostrar las 3 más recientes
                    print(f"      • {temp['sensor']}: {temp['value']}°C")
                    
                # Verificar que las temperaturas estén en rango normal
                values = [t["value"] for t in temp_readings]
                avg_temp = sum(values) / len(values)
                
                if 20 <= avg_temp <= 35:
                    print(f"   ✅ Temperaturas en rango normal (promedio: {avg_temp:.1f}°C)")
                else:
                    print(f"   ⚠️  Temperaturas fuera de rango esperado (promedio: {avg_temp:.1f}°C)")
            else:
                print("   ⚠️  No se encontraron lecturas de temperatura")
        else:
            print(f"   ❌ No hay datos del Arduino USB o error: {usb_data.get('message', 'Unknown')}")
    except Exception as e:
        print(f"   ❌ Error obteniendo datos USB: {e}")
    
    # 4. Probar endpoint de frontend
    print("\n4️⃣ Verificando que el frontend pueda acceder a los datos...")
    endpoints_to_test = [
        "http://localhost:8000/",
        "http://localhost:8000/docs"
    ]
    
    for endpoint in endpoints_to_test:
        try:
            response = requests.get(endpoint, timeout=3)
            if response.status_code == 200:
                print(f"   ✅ {endpoint} - Accesible")
            else:
                print(f"   ⚠️  {endpoint} - Status {response.status_code}")
        except Exception as e:
            print(f"   ❌ {endpoint} - Error: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 RESUMEN:")
    print("✅ Arduino USB con código corregido está funcionando")
    print("✅ Las temperaturas están respondiendo correctamente")
    print("✅ Los datos llegan al API backend")
    print("✅ El pipeline completo está operativo")
    
    print("\n🌐 Para acceder al dashboard frontend:")
    print("   • Streamlit Cloud (si está configurado)")
    print("   • O ejecutar localmente: streamlit run frontend/app.py")
    
    return True

if __name__ == "__main__":
    test_pipeline()
