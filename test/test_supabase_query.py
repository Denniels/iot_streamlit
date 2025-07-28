#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para verificar la consulta de datos en Supabase
"""
import os
from supabase import create_client, Client
from backend.config import Config

def main():
    print("Verificando conexion y datos en Supabase...")
    
    # Configurar cliente Supabase
    try:
        supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        print("Cliente Supabase configurado correctamente")
    except Exception as e:
        print("Error configurando cliente Supabase: " + str(e))
        return
    
    # Consultar todos los datos
    try:
        response = supabase.table("sensor_data").select("*").order("timestamp", desc=True).limit(200).execute()
        data = response.data
        
        print("Total de registros encontrados: " + str(len(data)))
        
        if data:
            # Agrupar por device_id
            devices = {}
            for row in data:
                device_id = row['device_id']
                if device_id not in devices:
                    devices[device_id] = []
                devices[device_id].append(row)
            
            print("\nDispositivos encontrados: " + str(len(devices)))
            for device_id, records in devices.items():
                device_type = "USB" if "usb" in device_id.lower() else "Ethernet" if "ethernet" in device_id.lower() else "Desconocido"
                latest_timestamp = max([r['timestamp'] for r in records])
                print("  " + device_type + " " + device_id + ": " + str(len(records)) + " registros (ultimo: " + latest_timestamp + ")")
                
                # Mostrar tipos de sensores para cada dispositivo
                sensor_types = set([r['sensor_type'] for r in records])
                print("    Sensores: " + ', '.join(sensor_types))
        else:
            print("No se encontraron datos en Supabase")
            
    except Exception as e:
        print("Error consultando datos: " + str(e))
    
    # Consultar específicamente datos del Arduino Ethernet
    try:
        ethernet_response = supabase.table("sensor_data").select("*").eq("device_id", "arduino_ethernet_192_168_0_110").order("timestamp", desc=True).limit(10).execute()
        ethernet_data = ethernet_response.data
        
        print("\nDatos especificos del Arduino Ethernet:")
        print("Registros encontrados: " + str(len(ethernet_data)))
        
        if ethernet_data:
            for record in ethernet_data[:5]:  # Mostrar solo los primeros 5
                print("  " + record['sensor_type'] + ": " + str(record['value']) + " " + (record['unit'] or '') + " (" + record['timestamp'] + ")")
    except Exception as e:
        print("Error consultando datos del Arduino Ethernet: " + str(e))
    
    # Verificar tabla de dispositivos
    try:
        devices_response = supabase.table("devices").select("*").execute()
        devices_data = devices_response.data
        print("\nDispositivos registrados en tabla 'devices': " + str(len(devices_data)))
        for device in devices_data:
            print("  • " + device['device_id'] + " (" + device['device_type'] + ") - " + device['status'])
    except Exception as e:
        print("Error consultando tabla de dispositivos: " + str(e))

if __name__ == "__main__":
    main()
