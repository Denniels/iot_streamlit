#!/usr/bin/env python3
"""
Script de pruebas para validar la implementación de la Fase 1.1: Cache Interno de la API

Este script valida:
1. Funcionamiento del cache APIInternalCache
2. Persistencia en disco y recuperación
3. Respuestas resilientes de todos los endpoints
4. TTL y auto-cleanup

Ejecutar desde el directorio raíz del proyecto:
python3 test_phase1_cache.py
"""

import sys
import os
import time
import json
import requests
from datetime import datetime

# Agregar el directorio backend al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

def test_cache_system():
    """Prueba el sistema de cache interno"""
    print("🧪 INICIANDO PRUEBAS DE FASE 1.1: CACHE INTERNO API")
    print("=" * 60)
    
    try:
        from backend.api_cache import APIInternalCache, CacheKeys
        
        # Inicializar cache para pruebas
        cache = APIInternalCache(fallback_file="/tmp/test_cache_fallback.json")
        print("✅ 1. Cache APIInternalCache inicializado correctamente")
        
        # Prueba 1: Operaciones básicas de cache
        test_key = "test_data_001"
        test_data = {"device_id": "ESP32_001", "temperature": 23.5, "timestamp": datetime.now().isoformat()}
        
        # Guardar en cache
        cache.set_cache_data(test_key, test_data)
        print("✅ 2. Datos guardados en cache")
        
        # Recuperar del cache
        cached_result = cache.get_cached_data(test_key, ttl_override=60)
        if cached_result == test_data:
            print("✅ 3. Datos recuperados correctamente del cache")
        else:
            print(f"❌ 3. Error: datos recuperados no coinciden. Esperado: {test_data}, Obtenido: {cached_result}")
            return False
        
        # Prueba 2: Persistencia en disco
        cache.persist_fallback_data()
        
        # Crear nueva instancia de cache para simular reinicio
        cache2 = APIInternalCache(fallback_file="/tmp/test_cache_fallback.json")
        
        # Verificar que datos de fallback se cargaron
        fallback_result = cache2.get_fallback_data(test_key)
        if fallback_result == test_data:
            print("✅ 4. Persistencia en disco funcionando correctamente")
        else:
            print(f"❌ 4. Error: persistencia falló. Esperado: {test_data}, Obtenido: {fallback_result}")
            return False
        
        # Prueba 3: Claves de cache normalizadas
        device_key = CacheKeys.device_data("ESP32_001", limit=100, hours=1.0)
        devices_key = CacheKeys.devices_list(only_online=True)
        
        if "ESP32_001" in device_key and "hours_1.0" in device_key:
            print("✅ 5. CacheKeys generando claves correctas para datos de dispositivo")
        else:
            print(f"❌ 5. Error: clave de dispositivo incorrecta: {device_key}")
            return False
        
        if "devices_list_online_True" == devices_key:
            print("✅ 6. CacheKeys generando claves correctas para lista de dispositivos")
        else:
            print(f"❌ 6. Error: clave de dispositivos incorrecta: {devices_key}")
            return False
        
        # Prueba 4: TTL y expiración
        print("🕐 7. Probando TTL y expiración (esperando 3 segundos)...")
        cache.set_cache_data("temp_key", {"test": "ttl"})
        
        # Inmediatamente después debería estar disponible
        immediate_result = cache.get_cached_data("temp_key", ttl_override=2)  # TTL de 2 segundos
        if immediate_result:
            print("✅ 7a. Datos disponibles inmediatamente después de guardar")
        else:
            print("❌ 7a. Error: datos no disponibles inmediatamente")
            return False
        
        # Esperar que expire
        time.sleep(3)
        expired_result = cache.get_cached_data("temp_key", ttl_override=2)
        if expired_result is None:
            print("✅ 7b. TTL funcionando correctamente - datos expirados")
        else:
            print("❌ 7b. Error: datos no expiraron cuando debían")
            return False
        
        # Prueba 5: Auto-cleanup
        # Agregar varias entradas
        for i in range(5):
            cache.set_cache_data(f"cleanup_test_{i}", {"index": i})
        
        # Limpiar cache
        cache.cleanup_expired_entries()
        print("✅ 8. Auto-cleanup ejecutado sin errores")
        
        # Limpiar archivo de prueba
        try:
            os.remove("/tmp/test_cache_fallback.json")
        except:
            pass
        
        print("\n🎉 TODAS LAS PRUEBAS DE CACHE PASARON EXITOSAMENTE")
        return True
        
    except Exception as e:
        print(f"❌ Error durante pruebas de cache: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Prueba los endpoints de la API con cache implementado"""
    print("\n🌐 PROBANDO ENDPOINTS DE API CON CACHE")
    print("=" * 60)
    
    # URL base de la API (ajustar según configuración)
    api_base = "http://localhost:8008"  # Puerto por defecto de FastAPI
    
    endpoints_to_test = [
        ("/health", "GET"),
        ("/devices", "GET"),
        ("/data", "GET"),
    ]
    
    for endpoint, method in endpoints_to_test:
        try:
            url = f"{api_base}{endpoint}"
            print(f"🔍 Probando {method} {endpoint}...")
            
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                print(f"✅ {endpoint}: Status 200 OK")
                
                try:
                    data = response.json()
                    if 'success' in data:
                        print(f"   📊 Response format válido: success={data.get('success')}")
                    if 'message' in data:
                        print(f"   📝 Message: {data['message'][:50]}...")
                except:
                    print(f"   ⚠️  Warning: respuesta no es JSON válido")
            else:
                print(f"⚠️  {endpoint}: Status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"🔌 {endpoint}: API no disponible (conexión rechazada)")
            print("   💡 Asegúrate de que el servicio FastAPI esté ejecutándose")
        except requests.exceptions.Timeout:
            print(f"⏱️  {endpoint}: Timeout (>5s)")
        except Exception as e:
            print(f"❌ {endpoint}: Error inesperado: {e}")
    
    print("\n💡 Nota: Si la API no está disponible, las pruebas de cache interno aún son válidas")

def main():
    """Función principal de pruebas"""
    print("🚀 VALIDACIÓN COMPLETA DE FASE 1.1: CACHE INTERNO API")
    print("=" * 60)
    print(f"📅 Ejecutado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📁 Directorio de trabajo:", os.getcwd())
    print()
    
    # Prueba 1: Sistema de cache
    cache_success = test_cache_system()
    
    # Prueba 2: Endpoints de API (opcional si API no está ejecutándose)
    test_api_endpoints()
    
    print("\n" + "=" * 60)
    if cache_success:
        print("🎯 RESULTADO: Fase 1.1 Cache Interno - ✅ IMPLEMENTACIÓN EXITOSA")
        print("📋 Próximo paso: Continuar con Fase 1.2 (Mejorar manejo de errores PostgreSQL)")
    else:
        print("⚠️  RESULTADO: Fase 1.1 Cache Interno - ❌ REQUIERE REVISIÓN")
        print("🔧 Revisar errores anteriores y corregir antes de continuar")
    
    print("=" * 60)

if __name__ == "__main__":
    main()