# 10 · Tareas programadas y avisos al celular

Las tareas son las que hacen que la fábrica trabaje sola. Corren desde la app de Claude: la Mac tiene que estar prendida, despierta y con la app abierta.

1. Las plantillas están en `kit/tareas/*.json` (id, horario cron, descripción y prompt ya personalizado con la ruta de esta carpeta). Leelas.
2. Creá cada una con la herramienta de tareas programadas (`create_scheduled_task`, con el `taskId`, el `prompt` y el `cronExpression` del archivo). Cargala con ToolSearch si hace falta («scheduled task»).
   - **Prendidas desde el principio:** `radar-ofertas`, `buscar-ofertas`, `vigilancia-ofertas` (protege la plata: apaga lo que pierde; sin ofertas lanzadas termina sin gastar) y `soporte-clientes` (solo si el paso 4 quedó hecho).
   - **Creadas pero apagadas:** `lanzar-ofertas` (lanza 2 ofertas por día solo y gasta presupuesto) y `renovacion-diaria`. Se prenden cuando la persona haya lanzado su primera oferta con vos y diga «prendé el piloto automático».
3. Comprobá con `list_scheduled_tasks` que estén las seis, con su horario y su estado.
4. **Avisos al celular:** que la persona instale la app de Claude en el celular con la misma cuenta y permita notificaciones. Mandá una notificación de prueba con la herramienta de notificaciones y pedile que confirme que le llegó.

Marcá `tareas` y `celular`.
