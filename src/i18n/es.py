# es.py — Español
STRINGS: dict[str, str] = {
    # --- común ---
    "dlg.ok": "Aceptar",
    "dlg.cancel": "Cancelar",
    "dlg.yes": "Sí",
    "dlg.no": "No",
    "dlg.close": "Cerrar",
    "dlg.error": "Error",
    "dlg.warning": "Advertencia",
    "dlg.info": "Aviso",
    "unit.seconds": "{value} s",
    "unit.frames": "{value} fotogramas",

    # --- inicio ---
    "app.already_running.title": "Ya está en ejecución",
    "app.already_running.text": "APEX GIF MAKER ya está en ejecución.\nSe ha traído la ventana existente al frente.",

    # --- barra superior ---
    "top.open": "Abrir video",
    "top.open.tip": "Abre un archivo de video (Ctrl+O). También puedes soltar un archivo en la ventana.",
    "top.no_video": "Abre un video o suéltalo en la ventana",
    "top.play": "Reproducir rango",
    "top.play.tip": "Reproduce el rango seleccionado en tu reproductor predeterminado (Ctrl+P).",
    "top.menu.tip": "Configuración",
    "top.open_dialog": "Abrir video",
    "top.video_filter": "Videos ({patterns});;Todos los archivos (*.*)",

    # --- menú de configuración ---
    "menu.theme": "Tema",
    "menu.theme.system": "Según el sistema",
    "menu.theme.light": "Claro",
    "menu.theme.dark": "Oscuro",
    "menu.language": "Idioma",
    "menu.language.auto": "Automático (sistema)",
    "menu.confirm_exit": "Confirmar al salir",
    "menu.check_update": "Buscar actualizaciones",
    "menu.about": "Acerca de",
    "lang.restart": "El cambio de idioma se aplicará al reiniciar la aplicación.",

    # --- vista previa ---
    "preview.start": "Inicio",
    "preview.end": "Fin",
    "preview.empty.title": "Suelta un video aquí",
    "preview.empty.body": "Compatible con MP4, MOV, MKV, WEBM, AVI y más.",
    "preview.crop_hint": "El recuadro punteado muestra la zona que se conserva en el GIF.",
    "preview.error": "No se pudo cargar el fotograma",

    # --- línea de tiempo ---
    "timeline.title": "Rango",
    "timeline.hint": "Arrastra los tiradores para recortar · arrastra el centro para mover · rueda para ampliar · "
                     "Mayús+rueda para desplazar · doble clic para ampliar la selección",
    "timeline.placeholder": "La línea de tiempo aparece al abrir un video",
    "timeline.zoom_in": "Acercar (+)",
    "timeline.zoom_out": "Alejar (−)",
    "timeline.zoom_fit": "Ajustar (0)",
    "timeline.zoom_sel": "Ampliar la selección",
    "timeline.frames": "≈ {frames} fotogramas",
    "timeline.frames_max": "hasta {frames} fotogramas",
    "timeline.over_reco": "Más de {sec} s recomendados",
    "timeline.limits": "El rango puede durar de {min} a {max} segundos.",
    "field.start": "Inicio",
    "field.length": "Duración (s)",
    "field.end": "Fin",
    "field.back": "−0,1 s (Mayús: −1 s)",
    "field.forward": "+0,1 s (Mayús: +1 s)",
    "field.invalid": "Tiempo no válido. (p. ej., 01:23.500 o 83.5)",

    # --- opciones de GIF ---
    "options.title": "Opciones de GIF",
    "options.size": "Tamaño",
    "options.size.reset": "Restablecer al valor de APEX (160×80)",
    "options.fps": "FPS",
    "options.fps.tip": "Fotogramas por segundo. Más alto es más fluido, pero el archivo pesa más.",
    "options.scale": "Escala",
    "options.scale.cover": "Rellenar (recortar)",
    "options.scale.cover.tip": "Mantiene la proporción, rellena la pantalla y recorta lo que sobra.",
    "options.scale.letterbox": "Ajustar (bandas)",
    "options.scale.letterbox.tip": "Reduce el fotograma completo para que quepa y rellena el resto con bandas negras.",
    "options.scale.stretch": "Estirar",
    "options.scale.stretch.tip": "Ignora la proporción y estira hasta el tamaño indicado.",
    "options.dither": "Tramado",
    "options.dither.floyd_steinberg": "Floyd–Steinberg",
    "options.dither.floyd_steinberg.tip": "Tramado suave y natural (recomendado)",
    "options.dither.bayer": "Bayer",
    "options.dither.bayer.tip": "Patrón de cuadrícula ordenado (nítido)",
    "options.dither.none": "Ninguno",
    "options.dither.none.tip": "Sin tramado (nítido, pueden aparecer bandas)",
    "options.dither.help": "¿Qué es el tramado?",
    "options.dither.help_text": (
        "Cada fotograma de un GIF puede usar como máximo 256 colores. El tramado mezcla pequeños patrones de puntos "
        "para que las bandas de color se noten menos.\n\n"
        "• Floyd–Steinberg: suave y natural (recomendado)\n"
        "• Bayer: patrón de cuadrícula ordenado, nítido\n"
        "• Ninguno: nítido, pero pueden aparecer bandas"),
    "options.frames": "Fotogramas",
    "options.frames.even": "Uniforme (mantener tiempo)",
    "options.frames.even.tip": "Toma el rango a intervalos regulares. Las partes estáticas ocupan muy poco.",
    "options.frames.dedupe": "Sin duplicados (saltar partes quietas)",
    "options.frames.dedupe.tip": "Elimina los fotogramas repetidos. Las partes quietas se omiten, así que "
                                 "la reproducción puede ser más corta.",

    # --- salida ---
    "output.title": "Salida",
    "output.folder": "Carpeta",
    "output.folder.placeholder": "Carpeta de la aplicación",
    "output.folder.choose": "Elegir carpeta",
    "output.folder.open": "Abrir carpeta",
    "output.filename": "Nombre",
    "output.filename.auto": "Usar el nombre automático",
    "output.generate": "Crear GIF",
    "output.generate.tip": "Crea un GIF a partir del rango (Ctrl+Intro).",
    "output.cancel": "Cancelar",
    "output.stage.palette": "Analizando colores…",
    "output.stage.encode": "Codificando GIF… {percent}%",

    # --- registro ---
    "log.title": "Registro",
    "log.clear": "Borrar registro",
    "log.ffmpeg_checking": "Comprobando ffmpeg/ffprobe…",
    "log.ffmpeg_ready": "ffmpeg: {ffmpeg} | ffprobe: {ffprobe}",
    "log.ffmpeg_progress": "Descargando ffmpeg {percent}%",
    "log.video_loaded": "Cargado: {name} ({info})",
    "log.settings_error": "No se pudo leer la configuración; se usan los valores predeterminados: {error}",
    "log.settings_save_error": "No se pudo guardar la configuración: {error}",
    "log.legacy_cache": "Se eliminó la caché antigua: {items}",
    "log.update_available": "Hay una nueva versión: {tag}",
    "log.update_latest": "Tienes la última versión. (v{version})",
    "log.update_failed": "No se pudo buscar actualizaciones: {error}",
    "log.gif_saved": "GIF guardado: {path} ({details})",
    "log.gif_failed": "Error al crear el GIF: {error}",
    "log.gif_cancelled": "Se canceló la creación del GIF.",
    "log.frame_failed": "No se pudo extraer el fotograma ({time}): {error}",
    "log.clip_failed": "No se pudo crear el clip de vista previa: {error}",

    # --- estado ---
    "status.ffmpeg.checking": "Comprobando ffmpeg…",
    "status.ffmpeg.downloading": "Descargando ffmpeg… {percent}%",
    "status.ffmpeg.ready": "ffmpeg {version}",
    "status.ffmpeg.missing": "Falta ffmpeg",
    "status.loading_video": "Leyendo el video…",
    "status.exporting_clip": "Preparando el clip de vista previa…",
    "status.generating": "Creando GIF…",
    "status.done": "GIF guardado: {name}",
    "status.cancelled": "Se canceló la creación del GIF.",

    # --- mensajes ---
    "msg.file_missing": "No se encontró el archivo.\n{path}",
    "msg.ffmpeg_not_ready": "Se está preparando ffmpeg. Inténtalo de nuevo en un momento.",
    "msg.ffmpeg_failed": "No se pudo preparar ffmpeg.\nComprueba tu conexión a Internet o copia ffmpeg.exe y "
                         "ffprobe.exe en la carpeta bin.\n\n{path}",
    "msg.probe_failed": "No se pudo leer el video.\n{error}",
    "msg.load_video_first": "Primero abre un video.",
    "msg.overwrite.title": "Sobrescribir",
    "msg.overwrite": "Ya existe un archivo con el mismo nombre.\n{name}\n\n¿Quieres reemplazarlo?",
    "msg.invalid_filename": "El nombre contiene caracteres no permitidos.\n{chars}",
    "msg.folder_unwritable": "No se puede escribir en la carpeta de salida.\n{path}",
    "msg.gif_failed": "No se pudo crear el GIF.\nConsulta el registro para más detalles.\n\n{error}",
    "msg.clip_failed": "No se pudo crear el clip de vista previa.\n{error}",
    "msg.quit.title": "Salir",
    "msg.quit": "¿Quieres salir de APEX GIF MAKER?",
    "msg.quit.busy": "Se está creando un GIF. ¿Cancelarlo y salir?",
    "msg.dont_ask": "No volver a preguntar",
    "msg.update.title": "Actualización",
    "msg.update_latest": "Ya tienes la última versión. (v{version})",
    "msg.update_failed": "No se pudo buscar actualizaciones.\n{error}",

    # --- ventana de resultado ---
    "result.title": "GIF creado",
    "result.file": "Archivo",
    "result.size": "Tamaño",
    "result.dimensions": "Dimensiones",
    "result.frames": "Fotogramas",
    "result.duration": "Duración",
    "result.elapsed": "Tiempo empleado",
    "result.open_folder": "Mostrar en la carpeta",
    "result.open_file": "Abrir archivo",

    # --- acerca de ---
    "about.title": "Acerca de APEX GIF MAKER",
    "about.tagline": "Creador de GIF para las pantallas de los mandos Flydigi APEX",
    "about.description": "Elige un rango de cualquier video y conviértelo en un GIF de alta calidad con el tamaño "
                         "de la pantalla del mando. Funciona con APEX 4, 5, 6 y cualquier otro modelo que comparta "
                         "el mismo formato de pantalla.",
    "about.version": "Versión {version}",
    "about.ffmpeg": "FFmpeg {version}",
    "about.ffmpeg_missing": "FFmpeg no encontrado",
    "about.changelog": "Historial de cambios",
    "about.sponsor": "Patrocinar",
    "about.issues": "Informar de un problema",
    "about.credits": "Créditos",
    "about.credits_text": "Procesamiento de video: FFmpeg (LGPL/GPL)\n"
                          "Interfaz: Qt for Python / PySide6 (LGPL)\n"
                          "Iconos: Fluent UI System Icons © Microsoft (MIT)\n"
                          "Fuentes: Pretendard, Pretendard JP, JetBrains Mono (SIL OFL 1.1)",

    # --- botones de ventana ---
    "win.minimize": "Minimizar",
    "win.maximize": "Maximizar",
    "win.restore": "Restaurar",
    "win.close": "Cerrar",

    # --- actualización ---
    "update.heading": "Hay una nueva versión: {version}",
    "update.current": "Versión actual v{version}",
    "update.verified": "SHA-256 verificado",
    "update.now": "Actualizar ahora",
    "update.later": "Más tarde",
    "update.notes": "Notas de la versión",
    "update.open_page": "Abrir página de descarga",
    "update.retry": "Reintentar",
    "update.downloading": "Descargando… {done} / {total}",
    "update.extracting": "Descomprimiendo…",
    "update.ready": "Listo. Reiniciando para aplicar la actualización…",
    "update.failed": "No se pudo preparar la actualización.\n{error}",
    "update.source_mode": "La actualización automática solo está disponible en la versión publicada. "
                          "Descarga la nueva versión desde la página de lanzamientos.",
    "update.no_verified_asset": "Esta versión no incluye un archivo de actualización verificable con SHA-256. "
                                "Descárgala desde la página de lanzamientos.",
    "update.unwritable": "No se puede escribir en la carpeta de la aplicación, así que la actualización no puede "
                         "instalarse automáticamente. Descárgala desde la página de lanzamientos.",
    "update.launch_failed": "No se pudo abrir la ventana de actualización.",
    "update.rate_limited": "Se alcanzó el límite de solicitudes de GitHub. Inténtalo más tarde.",
    "msg.update_applied": "Actualizado a la v{version}.",
    "msg.update_rolled_back": "La actualización falló, así que se conservó la versión anterior.\n{error}",
    "log.update_applied": "Actualizado: v{from_version} → v{to_version}",

    # --- aplicar actualización (--apply-update) ---
    "apply.title": "Aplicando actualización",
    "apply.heading": "v{from_version} → v{to_version}",
    "apply.step.wait": "Esperando a que se cierre la aplicación",
    "apply.step.backup": "Copia de seguridad de los archivos actuales",
    "apply.step.install": "Instalando los archivos nuevos",
    "apply.step.launch": "Reiniciando",
    "apply.done": "Actualización completada.",
    "apply.rolled_back": "La actualización falló y se restauró la versión anterior.\n{error}",
    "apply.timeout": "La aplicación no se cerró, así que no se inició la actualización. Ciérrala e inténtalo de nuevo.",
    "apply.bad_arguments": "Las rutas de actualización no son válidas.",
    "apply.failed": "La actualización falló. La copia de seguridad de los archivos anteriores está aquí:\n{path}\n{error}",

    # --- preparación automática de ffmpeg ---
    "ffmpeg.unsupported_os": "La preparación automática de ffmpeg no es compatible con este sistema. "
                             "Instala ffmpeg y agrégalo al PATH.",
    "ffmpeg.downloading": "Descargando ffmpeg: {url}",
    "ffmpeg.no_checksum": "No se pudo obtener la suma SHA-256, así que se omitió la descarga.",
    "ffmpeg.verify_ok": "Suma SHA-256 verificada",
    "ffmpeg.verify_fail": "La suma SHA-256 no coincide; se descarta la descarga.",
    "ffmpeg.extracting": "Descomprimiendo…",
    "ffmpeg.download_failed": "Error de descarga: {error}",
    "ffmpeg.installed": "ffmpeg está listo: {path}",
    "ffmpeg.setup_failed": "No se pudo preparar ffmpeg.",

    # --- actualización de herramientas (ffmpeg) ---
    "menu.update_tools": "Actualizar herramientas (ffmpeg)",
    "menu.auto_update_tools": "Actualizar herramientas automáticamente",
    "tools.title": "Actualizar herramientas",
    "tools.checking": "Buscando una versión nueva de ffmpeg…",
    "tools.latest": "Ya tienes la última versión de ffmpeg. ({version})",
    "tools.updated": "ffmpeg se actualizó a {new}. (anterior: {old})",
    "tools.staged": "Se descargó ffmpeg {new}. Se aplicará la próxima vez que abras la aplicación.",
    "tools.failed": "No se pudo actualizar ffmpeg.\n{error}",
    "tools.unmanaged": "Se está usando un ffmpeg instalado en el sistema, así que no se actualiza automáticamente. "
                       "Elige «Actualizar herramientas» en el menú de configuración para usar la copia propia "
                       "de la aplicación.",
    "tools.applied_staged": "Se aplicó la actualización de ffmpeg descargada anteriormente.",
    "status.ffmpeg.updating": "Actualizando ffmpeg… {percent}%",
    "log.legacy_ffmpeg": "Se movió ffmpeg de la antigua carpeta ffmpeg-bin a bin.",
}
