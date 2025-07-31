# dev_roadmap.md


## Roadmap de Mejoras y Reparaciones IoT Dashboard

### Priorización de Tareas
1. **Automatizar la carga y actualización de la URL pública (Cloudflare Tunnel) en el frontend**
2. **Visualización de estados de servicios tipo semáforo (verde/amarillo/rojo) en el dashboard**
3. **Automatización de servicios: inicio/apagado con Jetson y reinicio mensual**
4. **Diagnóstico, monitoreo y robustez de adquisición y visualización de datos**
5. **Mejoras de usabilidad, mantenimiento y documentación**


### 1. Automatización de URL Pública (Cloudflare Tunnel) [PRIORIDAD 1]
- [x] Automatizar la carga de la URL pública del backend en el frontend, leyendo el valor de `secrets_tunnel.toml`. _(31/07/2025, GitHub Copilot)_
- [x] Detectar automáticamente si la URL cambia tras reiniciar el servicio y actualizarla en el frontend. _(31/07/2025, GitHub Copilot)_
- [x] El frontend debe esperar a que la URL esté disponible antes de intentar conectar. _(31/07/2025, GitHub Copilot)_
- [x] El usuario no debe ingresar la URL manualmente nunca más. _(31/07/2025, GitHub Copilot)_
- [x] Documentar el flujo de actualización automática de la URL. _(31/07/2025, GitHub Copilot)_

### 2. Visualización y Monitoreo de Servicios tipo Semáforo [PRIORIDAD 2]
- [x] Cambiar el nombre del estado "Adquisición USB" a "Adquisición de Datos" en el frontend. _(31/07/2025, GitHub Copilot)_
- [x] Los estados de "Adquisición de Datos" y "API Backend" deben funcionar como semáforo:
    - Verde: servicio corriendo y activo
    - Amarillo: servicio reiniciándose o con logs de advertencia
    - Rojo: servicio detenido o con error crítico
  _(31/07/2025, GitHub Copilot)_
- [x] Mostrar el estado en tiempo real de ambos servicios en el dashboard. _(31/07/2025, GitHub Copilot)_


### 3. Automatización de Servicios en Jetson Nano [PRIORIDAD 3]
- [ ] Configurar los servicios para que se inicien automáticamente al encender la Jetson Nano.
- [ ] Detener los servicios correctamente al apagar la Jetson.
- [ ] Crear un script o servicio que reinicie la Jetson Nano una vez al mes por seguridad.
- [ ] Reiniciar todos los servicios tras el reinicio mensual.
### 4. Visualización y Control de Dispositivos
- [ ] Mostrar ambos dispositivos (USB y Ethernet) en el frontend, con su estado y cantidad de registros.
- [ ] Revisar y ajustar la cantidad de registros mostrados por dispositivo (paginación o límite configurable).
- [ ] Permitir al usuario seleccionar cuántos registros ver en el dashboard.


### 5. Flujo de Datos Arduino USB y Ethernet
- [ ] Verificar que los datos del Arduino USB se almacenen correctamente en la base de datos.
- [ ] Verificar que los datos del Arduino ethernet se almacenen correctamente en la base de datos.
- [ ] Si no llegan datos, agregar logs detallados en cada paso del flujo: adquisición, almacenamiento, API y frontend.
- [ ] Validar que el frontend muestre los datos del Arduino USB cuando existan registros.
- [ ] Validar que el frontend muestre los datos del Arduino ethernet cuando existan registros.


### 6. Robustez y Usabilidad
- [ ] Mejorar mensajes de error y estados en el frontend para cada servicio/dispositivo.
- [ ] Documentar en este roadmap cada mejora aplicada y pendiente.
- [ ] Agregar instrucciones para nuevos desarrolladores sobre cómo reiniciar servicios y verificar logs.

### 7. Tareas de Mantenimiento y Futuras
- [ ] Revisar y limpiar logs antiguos periódicamente.
- [ ] Automatizar pruebas de adquisición y visualización de datos.
- [ ] Agregar sección de troubleshooting común en este archivo.

---

## Notas y Observaciones
- Cada mejora aplicada debe marcarse como completada y dejar un comentario de fecha y responsable.
- Este roadmap debe mantenerse actualizado y ser la referencia principal para el desarrollo y mantenimiento del sistema.
