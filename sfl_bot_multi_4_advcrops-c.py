import requests
import json
import time
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import logging
from logging.handlers import RotatingFileHandler

# ==============================================================================
# SUNFLOWER LAND BOT - MONITOR DE RECURSOS
# ==============================================================================
"""
Bot de Telegram para monitorear recursos en Sunflower Land.
Características principales:
- Monitoreo de cultivos y tiempo de cosecha
- Estado de colmenas y producción de miel
- Control de árboles y piedras
- Alertas automáticas de recursos listos
"""

# ==============================================================================
# 1. CONFIGURACIÓN INICIAL
# ==============================================================================

# ------------------------------------------------------------------------------
# 1.1 Importación de módulos
# ------------------------------------------------------------------------------
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json
import logging
import os
import requests
import time

# ------------------------------------------------------------------------------
# 1.2 Configuración de claves y tokens
# ------------------------------------------------------------------------------
API_KEY = os.getenv("SFL_API_KEY", "sfl.MjMyNzA.cBUzHowDpMK3WE8y3xX2Y3oBLyFgq44NAedYC-a578c")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8520207393:AAEfnm0T0cXoavKhlWCUTTPn2LUdGVphVOQ")

# ------------------------------------------------------------------------------
# 1.3 Intervalos y tiempos de espera
# ------------------------------------------------------------------------------
# Frecuencias de chequeo
LOOP_SLEEP_SECONDS = 5                 # Intervalo entre chequeos de comandos
FARM_CHECK_INTERVAL_SECONDS = 300      # Intervalo entre chequeos de granja (5 min)

# Tiempos base de recursos (en milisegundos)
LOVE_INTERVAL_MS = 8 * 60 * 60 * 1000  # Intervalo de amor para animales (8h)
PRE_ALERT_MS = 5 * 60 * 1000           # Alerta previa para eventos (5min)
TREE_GROWTH_BASE_MS = 2 * 60 * 60 * 1000  # Crecimiento de árboles (2h)
STONE_RESPAWN_BASE_MS = 4 * 60 * 60 * 1000  # Reaparición de piedras (4h)

# Tiempos de Floating Island
PRE_EVENT_ALERT_MS = 5 * 60 * 1000      # Alerta 5 minutos antes del evento

# ------------------------------------------------------------------------------
# 1.4 Configuración de archivos y logging
# ------------------------------------------------------------------------------
# Usar rutas absolutas basadas en la ubicación del script para que el código
# funcione aunque el working directory cambie o el proyecto se mueva.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_FILE = os.path.join(BASE_DIR, "sfl_users.json")
LOG_FILE = os.path.join(BASE_DIR, "sfl_bot.log")

# VARIABLE GLOBAL PARA LAST_UPDATE_ID
LAST_UPDATE_ID = None

# Configurar logging

# Rotating log file: 2MB per file, keep 3 backups, WARNING and above only
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.WARNING)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)

logger.handlers = [file_handler, stream_handler]

# ==============================================================================
# 2. DATOS DE JUEGO Y CONFIGURACIÓN
# ==============================================================================

# ------------------------------------------------------------------------------
# 2.1 Tablas de experiencia de animales
# ------------------------------------------------------------------------------
# Niveles y experiencia necesaria para cada tipo de animal
XP_UMBRALES_GALLINA = [
    0, 60, 120, 240, 360, 480, 660, 840, 1020, 1200,  # Niveles 0-9
    1440, 1680, 1920, 2160, 2400, 2720               # Niveles 10-15
]

XP_UMBRALES_VACA = [
    0, 180, 360, 720, 1080, 1440, 1980, 2520, 3060, 3600,  # Niveles 0-9
    4320, 5040, 5760, 6480, 7200, 8160                     # Niveles 10-15
]

XP_UMBRALES_OVEJA = [
    0, 120, 240, 480, 720, 960, 1320, 1680, 2040, 2400,  # Niveles 0-9
    2880, 3360, 3840, 4320, 4800, 5440                   # Niveles 10-15
]

# ------------------------------------------------------------------------------
# 2.2 Traducciones y nombres
# ------------------------------------------------------------------------------
# Nombres de animales en español para mensajes
ANIMAL_NAMES_ES = {
    "Chicken": "Gallina",
    "Cow": "Vaca",
    "Sheep": "Oveja",
    "Pig": "Cerdo",
    "Goat": "Cabra"
}

# ------------------------------------------------------------------------------
# 2.3 Tiempos de cultivos
# ------------------------------------------------------------------------------
# Tiempo base de crecimiento para cada cultivo (en milisegundos)
CROP_BASE_TIMES_MS = {
    "Sunflower": 60 * 1000,
    "Potato": 5 * 60 * 1000,
    "Rhubarb": 10 * 60 * 1000,
    "Pumpkin": 30 * 60 * 1000,
    "Zucchini": 30 * 60 * 1000,
    "Carrot": 1 * 3600 * 1000,
    "Yam": 1 * 3600 * 1000,
    "Cabbage": 2 * 3600 * 1000,
    "Broccoli": 2 * 3600 * 1000,
    "Soybean": 3 * 3600 * 1000,
    "Beetroot": 4 * 3600 * 1000,
    "Pepper": 4 * 3600 * 1000,
    "Cauliflower": 8 * 3600 * 1000,
    "Parsnip": 12 * 3600 * 1000,
    "Eggplant": 16 * 3600 * 1000,
    "Corn": 20 * 3600 * 1000,
    "Onion": 20 * 3600 * 1000,
    "Radish": 24 * 3600 * 1000,
    "Wheat": 24 * 3600 * 1000,
    "Turnip": 24 * 3600 * 1000,
    "Kale": 36 * 3600 * 1000,
    "Artichoke": 36 * 3600 * 1000,
    "Barley": 48 * 3600 * 1000,
}

# ==============================================================================
# 3. FUNCIONES DE UTILIDAD Y HELPERS
# ==============================================================================
"""
Esta sección contiene funciones auxiliares utilizadas en todo el bot:
- Manejo de archivos (carga/guardado de datos)
- Comunicación con Telegram
- Cálculos de tiempo y formateo
- Parsing y conversión de datos
"""

def load_user_data() -> Dict:
    """Carga los datos de los usuarios desde el archivo JSON."""
    if not os.path.exists(USER_DATA_FILE):
        return {}
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Archivo {USER_DATA_FILE} dañado o vacío. Reiniciando datos. Error: {e}")
        return {}

def save_user_data(data: Dict) -> None:
    """Guarda los datos de los usuarios en el archivo JSON."""
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        logger.error(f"No se pudo escribir en {USER_DATA_FILE}: {e}")

def send_telegram_message(chat_id: str, message: str) -> bool:
    """Envía un mensaje a Telegram. Retorna True si fue exitoso."""
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(telegram_url, data=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al enviar mensaje a Telegram ({chat_id}): {e}")
        return False

def calculate_animal_level(experience: int, xp_table: List[int]) -> int:
    """Calcula el nivel de un animal basándose en su XP."""
    level = 0
    for i, threshold in enumerate(xp_table):
        if experience >= threshold:
            level = i
        else:
            break
    return level

def get_time_remaining_ms(current_time_ms: float, future_time_ms: float) -> str:
    """Calcula el tiempo restante y lo formatea como [Xd] HHh MMm SSs."""
    remaining_ms = future_time_ms - current_time_ms
    
    if remaining_ms <= 0:
        return "**¡LISTO!**"
    
    remaining_seconds = int(remaining_ms // 1000)
    
    days = remaining_seconds // (24 * 3600)
    remaining_seconds %= (24 * 3600)
    hours = remaining_seconds // 3600
    remaining_seconds %= 3600
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    parts.append(f"{hours:02d}h")
    parts.append(f"{minutes:02d}m")
    parts.append(f"{seconds:02d}s")
    
    return " ".join(parts)

def get_time_since_ms(past_time_ms: float, current_time_ms: float) -> str:
    """Formatea cuánto tiempo ha pasado desde `past_time_ms` hasta `current_time_ms`.

    Devuelve una cadena como 'Xd HHh MMm SSs' o 'HHh MMm SSs' dependiendo de la duración.
    """
    delta_ms = current_time_ms - past_time_ms
    if delta_ms <= 0:
        return "0m"

    remaining_seconds = int(delta_ms // 1000)

    days = remaining_seconds // (24 * 3600)
    remaining_seconds %= (24 * 3600)
    hours = remaining_seconds // 3600
    remaining_seconds %= 3600
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    parts.append(f"{hours:02d}h")
    parts.append(f"{minutes:02d}m")
    parts.append(f"{seconds:02d}s")

    return " ".join(parts)


def parse_time_to_ms(value) -> Optional[float]:
    """Convierte distintos formatos de tiempo a milisegundos desde epoch.

    Acepta int/float (s o ms) o cadenas ISO. Devuelve None si no puede parsear.
    """
    if value is None:
        return None

    # Numérico: distinguir segundos vs milisegundos
    if isinstance(value, (int, float)):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        if v > 1e12:
            return v
        # tratar como segundos -> ms
        return v * 1000.0

    # Si es cadena, intentar parsear ISO 8601
    if isinstance(value, str):
        try:
            s = value.rstrip('Z')
            dt = datetime.fromisoformat(s)
            return dt.timestamp() * 1000.0
        except Exception:
            try:
                dt = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
                return dt.timestamp() * 1000.0
            except Exception:
                return None

    return None

def fetch_farm_data(farm_id: str) -> Optional[Dict]:
    """Obtiene los datos de la granja desde la API."""
    url = f"https://api.sunflower-land.com/community/farms/{farm_id}"
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.info(f"[DEBUG] API Response URL: {url}")
        logger.info(f"[DEBUG] API Response Headers: {headers}")
        logger.info(f"[DEBUG] API Response Data: {json.dumps(data, indent=2)}")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al obtener datos de Farm ID {farm_id}: {e}")
        return None

def calculate_crop_ready_time(crop_data: Dict) -> Optional[float]:
    """Calcula el tiempo de cosecha de un cultivo."""
    crop_name = crop_data.get("name")
    planted_at_raw = crop_data.get("plantedAt")
    base_growth_ms = CROP_BASE_TIMES_MS.get(crop_name)

    if planted_at_raw is None or base_growth_ms is None:
        return None

    # Usar helper de parseo existente (parse_time_to_ms) si está disponible,
    # si no, intentar interpretar como número de ms directamente.
    try:
        planted_at_ms = parse_time_to_ms(planted_at_raw)
    except Exception:
        # Fallback: si viene un número ya en ms
        try:
            planted_at_ms = float(planted_at_raw)
        except Exception:
            return None

    if planted_at_ms is None:
        return None

    # Nuevo comportamiento: IGNORAR boostedTime.
    try:
        base_ms = float(base_growth_ms)
    except (TypeError, ValueError):
        return None

    ready_at_ms = planted_at_ms + base_ms
    return ready_at_ms

# ==============================================================================
# 4. PROCESADORES DE RECURSOS
# ==============================================================================
"""
Módulos de procesamiento para cada tipo de recurso:
- Colmenas y producción de miel
- Cultivos y tiempos de cosecha
- Árboles y tiempos de tala
- Piedras y tiempos de minado

Cada módulo incluye:
1. Función process_X_alerts: Para notificaciones automáticas
2. Función para comando manual (/beehive, /crops, etc.)
"""

def process_beehives(data: Dict, user_info: Dict, current_time_ms: float) -> Tuple[List[str], List[str]]:
    """Procesa los datos de las colmenas."""
    beehives = data.get("farm", {}).get("beehives", {})
    last_status = user_info.get('last_notified_status', {})
    
    status_messages = []
    one_time_alerts = []
    
    if not beehives:
        return status_messages, one_time_alerts

    for beehive_id, hive_data in beehives.items():
        swarm_status = hive_data.get("swarm", False)
        flowers = hive_data.get("flowers", [])
        attached_until_ms = max((f.get("attachedUntil", 0) for f in flowers), default=0)

        swarm_text = "VERDADERO" if swarm_status else "FALSO"
        production_key = f"beehive_{beehive_id}_finished"

        message_lines = [f"🐝 *Colmena #{beehive_id}*"]
        
        if attached_until_ms > current_time_ms:
            time_remaining = get_time_remaining_ms(current_time_ms, attached_until_ms)
            message_lines.append(f" Producción: Finaliza en: **{time_remaining}**")
            last_status[production_key] = False
        else:
            message_lines.append(" Producción: **Finalizada!**")
            
            if not last_status.get(production_key, False):
                swarm_alert_text = f"Swarm: **{swarm_text}**"
                one_time_alerts.append(f"✅ ¡Producción de Colmena #{beehive_id} Finalizada! {swarm_alert_text}")
                last_status[production_key] = True

        message_lines.append(f" Swarm: **{swarm_text}**")
        status_messages.append("\n".join(message_lines))

    return status_messages, one_time_alerts

def process_crops_status(data: Dict, current_time_ms: float) -> List[str]:
    """Calcula el tiempo restante de los cultivos para el comando /crops."""
    plots = data.get("farm", {}).get("crops", {})
    logger.info(f"[DEBUG] Plots encontrados: {len(plots)}")
    status_messages = []
    
    if not plots:
        logger.info("[DEBUG] No hay plots en la respuesta")
        return ["No se encontraron parcelas plantadas activas."]
    
    crops_found = False
    
    for plot_id, plot_data in plots.items():
        crop_data = plot_data.get("crop", {})
        logger.info(f"[DEBUG] Procesando parcela {plot_id}: {json.dumps(crop_data)}")
        
        if not crop_data or not crop_data.get("name"):
            logger.info(f"[DEBUG] Parcela {plot_id} sin cultivo")
            continue
        
        crop_name = crop_data.get("name")
        ready_at_ms = calculate_crop_ready_time(crop_data)
        crops_found = True  # Si llegamos aquí, encontramos al menos un cultivo
        
        if ready_at_ms is not None:
            # Si el cultivo ya está listo, mostrar desde cuándo está listo
            logger.info(f"[DEBUG] Parcela {plot_id} - Crop: {crop_name} | plantedAt: {crop_data.get('plantedAt')} | boostedTime: {crop_data.get('boostedTime')} | base_ms: {CROP_BASE_TIMES_MS.get(crop_name)} | ready_at: {ready_at_ms} | now: {current_time_ms}")

            if ready_at_ms <= current_time_ms:
                since_str = get_time_since_ms(ready_at_ms, current_time_ms)
                status_messages.append(
                    f"**{crop_name}** (Parcela #{plot_id}): **¡LISTO!** — listo desde: {since_str}"
                )
            else:
                time_remaining_str = get_time_remaining_ms(current_time_ms, ready_at_ms)
                status_messages.append(
                    f"**{crop_name}** (Parcela #{plot_id}): **{time_remaining_str}**"
                )
    
    if not crops_found:
        logger.info("[DEBUG] No se encontraron cultivos válidos")
        return ["No hay cultivos plantados actualmente."]
    
    return status_messages

def process_stones_alerts(data: Dict, user_info: Dict, current_time_ms: float) -> List[str]:
    """Procesa las alertas de piedras listas para minar."""
    stones = data.get("farm", {}).get("stones", {})
    last_status = user_info.get('last_notified_status', {})
    stone_alert_key = "stones_ready"
    alerts = []
    
    ready_stones_count = 0
    logger.info(f"[DEBUG] Verificando {len(stones)} piedras...")
    
    if stones:
        for stone_id, stone_data in stones.items():
            stone_resource_data = stone_data.get("stone", {})
            mined_at_ms = stone_resource_data.get("minedAt")
            
            if mined_at_ms:
                ready_at_ms = mined_at_ms + STONE_RESPAWN_BASE_MS
                
                if ready_at_ms <= current_time_ms:
                    ready_stones_count += 1
                    logger.info(f"[DEBUG] Piedra #{stone_id} lista para minar!")
                else:
                    time_left = ready_at_ms - current_time_ms
                    minutes_left = time_left / (1000 * 60)
                    logger.info(f"[DEBUG] Piedra #{stone_id} estará lista en {minutes_left:.1f} minutos")
    
    if ready_stones_count > 0:
        if not last_status.get(stone_alert_key, False):
            if ready_stones_count == 1:
                alerts.append("🪨 ¡Mina Lista! Una piedra está lista para ser minada.")
            else:
                alerts.append(f"🪨 ¡Mina Lista! **{ready_stones_count}** piedras están listas para ser minadas.")
            last_status[stone_alert_key] = True
    else:
        last_status[stone_alert_key] = False
    
    return alerts

def process_trees_alerts(data: Dict, user_info: Dict, current_time_ms: float) -> List[str]:
    """Procesa las alertas de árboles listos para talar."""
    trees = data.get("farm", {}).get("trees", {})
    last_status = user_info.get('last_notified_status', {})
    tree_alert_key = "trees_ready"
    alerts = []
    
    ready_trees_count = 0
    logger.info(f"[DEBUG] Verificando {len(trees)} árboles...")
    
    if trees:
        for tree_id, tree_data in trees.items():
            wood_resource_data = tree_data.get("wood", {})
            chopped_at_ms = wood_resource_data.get("choppedAt")
            
            if chopped_at_ms:
                ready_at_ms = chopped_at_ms + TREE_GROWTH_BASE_MS
                
                if ready_at_ms <= current_time_ms:
                    ready_trees_count += 1
                    logger.info(f"[DEBUG] Árbol #{tree_id} listo para talar!")
                else:
                    time_left = ready_at_ms - current_time_ms
                    minutes_left = time_left / (1000 * 60)
                    logger.info(f"[DEBUG] Árbol #{tree_id} estará listo en {minutes_left:.1f} minutos")
    
    if ready_trees_count > 0:
        if not last_status.get(tree_alert_key, False):
            if ready_trees_count == 1:
                alerts.append("🌲 ¡Tala Lista! Un árbol está listo para ser talado.")
            else:
                alerts.append(f"🌲 ¡Tala Lista! **{ready_trees_count}** árboles están listos para ser talados.")
            last_status[tree_alert_key] = True
    else:
        last_status[tree_alert_key] = False
    
    return alerts

def process_floating_island_alerts(data: Dict, user_info: Dict, current_time_ms: float) -> List[str]:
    """Procesa alertas para eventos de Floating Island."""
    alerts = []
    last_status = user_info.get('last_notified_status', {})
    floating_island = data.get("farm", {}).get("floatingIsland", {}).get("schedule", [])

    if not floating_island:
        return alerts

    for event in floating_island:
        start_time_ms = event.get("startAt")
        end_time_ms = event.get("endAt")
        
        if not start_time_ms or not end_time_ms:
            continue
            
        # Generar alertas 5 minutos antes del inicio
        pre_start_key = f"floating_island_pre_start_{start_time_ms}"
        if (start_time_ms - current_time_ms <= PRE_EVENT_ALERT_MS and 
            start_time_ms > current_time_ms and 
            not last_status.get(pre_start_key, False)):
            
            start_time = datetime.fromtimestamp(start_time_ms / 1000).strftime('%H:%M')
            end_time = datetime.fromtimestamp(end_time_ms / 1000).strftime('%H:%M')
            alerts.append(f"🏝️ ¡Floating Island disponible en 5 minutos! ({start_time} - {end_time})")
            last_status[pre_start_key] = True
            
        # Generar alertas 5 minutos antes del fin
        pre_end_key = f"floating_island_pre_end_{end_time_ms}"
        if (end_time_ms - current_time_ms <= PRE_EVENT_ALERT_MS and 
            end_time_ms > current_time_ms and 
            not last_status.get(pre_end_key, False)):
            
            alerts.append(f"⚠️ ¡Floating Island termina en 5 minutos!")
            last_status[pre_end_key] = True

    return alerts

def process_crops_alerts(data: Dict, user_info: Dict, current_time_ms: float) -> List[str]:
    """Procesa alertas de cultivos listos para cosechar."""
    plots = data.get("farm", {}).get("crops", {})
    last_status = user_info.get('last_notified_status', {})
    crop_alert_key = "crops_ready"
    alerts = []
    
    ready_crops_count = 0
    
    if plots and isinstance(plots, dict):
        for plot_id, plot_data in plots.items():
            crop_data = plot_data.get("crop", {})
            
            if not crop_data or not crop_data.get("name"):
                continue
            
            ready_at_ms = calculate_crop_ready_time(crop_data)
            
            if ready_at_ms and ready_at_ms <= current_time_ms:
                ready_crops_count += 1
    
    if ready_crops_count > 0:
        if not last_status.get(crop_alert_key, False):
            if ready_crops_count == 1:
                alerts.append("🥕 ¡Cosecha Lista! Un cultivo está listo para ser cosechado.")
            else:
                alerts.append(f"🥕 ¡Cosecha Lista! **{ready_crops_count}** cultivos están listos.")
            last_status[crop_alert_key] = True
    else:
        last_status[crop_alert_key] = False
    
    return alerts

# ==============================================================================
# 5. INTERFAZ DE TELEGRAM
# ==============================================================================
"""
Sistema de manejo de comandos de Telegram:

Comandos básicos:
- /start: Inicio y bienvenida
- /help: Ayuda y lista de comandos
- /setfarm: Configuración de ID
- /getfarm: Consulta de ID actual

Comandos de recursos:
- /beehive: Estado de colmenas
- /crops: Estado de cultivos
- /trees: Estado de árboles
- /stones: Estado de piedras

Cada comando tiene su propia función handle_X_command para mantener
el código organizado y facilitar el mantenimiento.
"""

def handle_telegram_commands(user_data: Dict) -> Dict:
    """Obtiene y procesa nuevos mensajes de Telegram."""
    global LAST_UPDATE_ID
    
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    
    params = {'timeout': 25}
    if LAST_UPDATE_ID is not None:
        params['offset'] = LAST_UPDATE_ID + 1

    try:
        response = requests.get(telegram_url, params=params, timeout=30)
        response.raise_for_status()
        updates = response.json().get('result', [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al obtener actualizaciones de Telegram: {e}")
        return user_data

    if not updates:
        return user_data

    # Procesar todas las actualizaciones
    for update in updates:
        update_id = update['update_id']
        
        message = update.get('message')
        if not message:
            # Actualizar LAST_UPDATE_ID incluso si no hay mensaje
            if LAST_UPDATE_ID is None or update_id > LAST_UPDATE_ID:
                LAST_UPDATE_ID = update_id
            continue
        
        chat_id = str(message['chat']['id'])
        text = message.get('text', '').strip()
        
        logger.info(f"📬 Mensaje de {chat_id}: {text}")
        
        # Procesar comandos
        if text.lower().startswith('/setfarm '):
            handle_setfarm_command(chat_id, text, user_data)
        
        elif text.lower() == '/start':
            handle_start_command(chat_id)
        
        elif text.lower() == '/getfarm':
            handle_getfarm_command(chat_id, user_data)
        
        elif text.lower() == '/beehive':
            handle_beehive_command(chat_id, user_data)
        
        elif text.lower() == '/crops':
            handle_crops_command(chat_id, user_data)
        
        elif text.lower() == '/help':
            handle_help_command(chat_id)
            
        elif text.lower() == '/trees':
            logger.info("Comando /trees detectado")
            handle_trees_command(chat_id, user_data)
            
        elif text.lower() == '/stones':
            logger.info("Comando /stones detectado")
            handle_stones_command(chat_id, user_data)
            
        elif text.lower() == '/globe':
            logger.info("Comando /globe detectado")
            handle_globe_command(chat_id, user_data)
        
        # Actualizar LAST_UPDATE_ID después de procesar cada mensaje
        if LAST_UPDATE_ID is None or update_id > LAST_UPDATE_ID:
            LAST_UPDATE_ID = update_id

    return user_data

def handle_setfarm_command(chat_id: str, text: str, user_data: Dict) -> None:
    """Maneja el comando /setfarm."""
    parts = text.split()
    if len(parts) == 2 and parts[1].isdigit():
        farm_id = parts[1]
        if chat_id not in user_data:
            user_data[chat_id] = {}
        user_data[chat_id]['farm_id'] = farm_id
        user_data[chat_id]['last_notified_status'] = {}
        save_user_data(user_data)
        send_telegram_message(chat_id, f"✅ *ID de Granja registrado!*\nTu nuevo ID es: *{farm_id}*")
    else:
        send_telegram_message(chat_id, "❌ Formato incorrecto. Usa: `/setfarm [ID]` (ej: `/setfarm 23270`)")

def handle_start_command(chat_id: str) -> None:
    """Maneja el comando /start."""
    message = (
        "👋 ¡Hola! Soy tu bot de monitoreo de Sunflower Land.\n\n"
        "Para empezar, usa: `/setfarm [TU_FARM_ID]`\n"
        "Usa `/help` para ver todos los comandos."
    )
    send_telegram_message(chat_id, message)

def handle_getfarm_command(chat_id: str, user_data: Dict) -> None:
    """Maneja el comando /getfarm."""
    farm_id = user_data.get(chat_id, {}).get('farm_id')
    if farm_id:
        send_telegram_message(chat_id, f"Tu ID de Granja actual es: *{farm_id}*")
    else:
        send_telegram_message(chat_id, "Aún no has configurado tu ID. Usa `/setfarm [ID]`")

def handle_beehive_command(chat_id: str, user_data: Dict) -> None:
    """Maneja el comando /beehive."""
    farm_id = user_data.get(chat_id, {}).get('farm_id')
    if not farm_id:
        send_telegram_message(chat_id, "❌ Configura tu ID primero con `/setfarm [ID]`")
        return

    data = fetch_farm_data(farm_id)
    if not data:
        send_telegram_message(chat_id, "❌ Error al obtener datos de la granja.")
        return
    
    current_time_ms = time.time() * 1000
    user_info = user_data.get(chat_id, {})
    
    beehive_status_messages, _ = process_beehives(data, user_info, current_time_ms)

    if beehive_status_messages:
        header = f"🐝 *Estado de Colmenas - Granja {farm_id}* 🐝\n\n"
        full_message = header + "\n\n".join(beehive_status_messages)
        send_telegram_message(chat_id, full_message)
    else:
        send_telegram_message(chat_id, "No se encontraron colmenas en esta granja.")
    
    save_user_data(user_data)

def handle_crops_command(chat_id: str, user_data: Dict) -> None:
    """Maneja el comando /crops."""
    farm_id = user_data.get(chat_id, {}).get('farm_id')
    if not farm_id:
        send_telegram_message(chat_id, "❌ Configura tu ID primero con `/setfarm [ID]`")
        return

    data = fetch_farm_data(farm_id)
    if not data:
        send_telegram_message(chat_id, "❌ Error al obtener datos de la granja.")
        return
    
    current_time_ms = time.time() * 1000
    crop_status_messages = process_crops_status(data, current_time_ms)

    header = f"🥕 *Estado de Cultivos - Granja {farm_id}* 🥕\n\n"
    full_message = header + "\n".join(crop_status_messages)
    send_telegram_message(chat_id, full_message)

def handle_stones_command(chat_id: str, user_data: Dict) -> None:
    """Maneja el comando /stones."""
    logger.info(f"Procesando comando /stones para chat_id {chat_id}")
    farm_id = user_data.get(chat_id, {}).get('farm_id')
    logger.info(f"Farm ID encontrado: {farm_id}")
    
    if not farm_id:
        send_telegram_message(chat_id, "❌ Configura tu ID primero con `/setfarm [ID]`")
        return

    data = fetch_farm_data(farm_id)
    if not data:
        send_telegram_message(chat_id, "❌ Error al obtener datos de la granja.")
        return
    
    current_time_ms = time.time() * 1000
    stones = data.get("farm", {}).get("stones", {})
    logger.info(f"Piedras encontradas: {len(stones)}")
    stone_messages = []
    
    if not stones:
        logger.info("No se encontraron piedras en la respuesta de la API")
        send_telegram_message(chat_id, "No se encontraron piedras en esta granja.")
        return
    
    for stone_id, stone_data in stones.items():
        stone_resource = stone_data.get("stone", {})
        mined_at_ms = stone_resource.get("minedAt")
        
        if mined_at_ms:
            ready_at_ms = mined_at_ms + STONE_RESPAWN_BASE_MS
            if ready_at_ms <= current_time_ms:
                since_str = get_time_since_ms(ready_at_ms, current_time_ms)
                stone_messages.append(f"🪨 Piedra #{stone_id}: **¡LISTA!** (desde hace {since_str})")
            else:
                time_remaining = get_time_remaining_ms(current_time_ms, ready_at_ms)
                stone_messages.append(f"🪨 Piedra #{stone_id}: Lista en **{time_remaining}**")
    
    if stone_messages:
        header = f"⛰️ *Estado de las Piedras - Granja {farm_id}* ⛰️\n\n"
        full_message = header + "\n".join(stone_messages)
        logger.info(f"Enviando mensaje con {len(stone_messages)} piedras")
        send_telegram_message(chat_id, full_message)
    else:
        logger.info("No se encontró información de minado para ninguna piedra")
        send_telegram_message(chat_id, "No hay información de minado disponible.")

def handle_trees_command(chat_id: str, user_data: Dict) -> None:
    """Maneja el comando /trees."""
    logger.info(f"Procesando comando /trees para chat_id {chat_id}")
    farm_id = user_data.get(chat_id, {}).get('farm_id')
    logger.info(f"Farm ID encontrado: {farm_id}")
    if not farm_id:
        send_telegram_message(chat_id, "❌ Configura tu ID primero con `/setfarm [ID]`")
        return

    data = fetch_farm_data(farm_id)
    if not data:
        send_telegram_message(chat_id, "❌ Error al obtener datos de la granja.")
        return
    
    current_time_ms = time.time() * 1000
    trees = data.get("farm", {}).get("trees", {})
    logger.info(f"Árboles encontrados: {len(trees)}")
    tree_messages = []
    
    if not trees:
        logger.info("No se encontraron árboles en la respuesta de la API")
        send_telegram_message(chat_id, "No se encontraron árboles en esta granja.")
        return
    
    for tree_id, tree_data in trees.items():
        wood_data = tree_data.get("wood", {})
        chopped_at_ms = wood_data.get("choppedAt")
        
        if chopped_at_ms:
            ready_at_ms = chopped_at_ms + TREE_GROWTH_BASE_MS
            if ready_at_ms <= current_time_ms:
                since_str = get_time_since_ms(ready_at_ms, current_time_ms)
                tree_messages.append(f"🌲 Árbol #{tree_id}: **¡LISTO!** (desde hace {since_str})")
            else:
                time_remaining = get_time_remaining_ms(current_time_ms, ready_at_ms)
                tree_messages.append(f"🌲 Árbol #{tree_id}: Listo en **{time_remaining}**")
    
    if tree_messages:
        header = f"🌳 *Estado de los Árboles - Granja {farm_id}* 🌳\n\n"
        full_message = header + "\n".join(tree_messages)
        logger.info(f"Enviando mensaje con {len(tree_messages)} árboles")
        send_telegram_message(chat_id, full_message)
    else:
        logger.info("No se encontró información de tala para ningún árbol")
        send_telegram_message(chat_id, "No hay información de tala disponible.")

def format_floating_island_message(events: List[Dict], current_time_ms: float) -> str:
    """Formatea el mensaje de Floating Island con un diseño simple."""
    # Usar texto simple (sin emojis problemáticos) para compatibilidad con Telegram
    messages = ["*Horarios de Floating Island*\n"]
    
    active_events = []
    future_events = []
    past_events = []

    # Traducir días de la semana
    days_es = {
        'Monday': 'Lunes',
        'Tuesday': 'Martes',
        'Wednesday': 'Miércoles',
        'Thursday': 'Jueves',
        'Friday': 'Viernes',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }

    for event in events:
        start_time_ms = event.get("startAt")
        end_time_ms = event.get("endAt")
        
        if not start_time_ms or not end_time_ms:
            continue

        start_dt = datetime.fromtimestamp(start_time_ms / 1000)
        end_dt = datetime.fromtimestamp(end_time_ms / 1000)
        
        day_name = start_dt.strftime('%A')
        date = start_dt.strftime('%d/%m/%Y')
        start_time = start_dt.strftime('%H:%M')
        end_time = end_dt.strftime('%H:%M')
        day_name_es = days_es.get(day_name, day_name)

        event_info = {
            'day': day_name_es,
            'date': date,
            'start': start_time,
            'end': end_time,
            'start_ms': start_time_ms,
            'end_ms': end_time_ms
        }

        if current_time_ms < start_time_ms:
            future_events.append(event_info)
        elif current_time_ms < end_time_ms:
            active_events.append(event_info)
        else:
            past_events.append(event_info)

    # Eventos activos
    if active_events:
        messages.append("\n*Evento Actual:*")
        for event in active_events:
            time_left = get_time_remaining_ms(current_time_ms, event['end_ms'])
            messages.extend([
                f"• {event['day']} {event['date']}",
                f"  Horario: {event['start']} - {event['end']}",
                f"  **¡EN CURSO!** Termina en: {time_left}"
            ])

    # Próximos eventos
    if future_events:
        messages.append("\n*Próximos Eventos:*")
        for event in future_events:
            time_until = get_time_remaining_ms(current_time_ms, event['start_ms'])
            messages.extend([
                f"• {event['day']} {event['date']}",
                f"  Horario: {event['start']} - {event['end']}",
                f"  Comienza en: {time_until}"
            ])

    # No mostramos eventos pasados
    return "\n".join(messages)

def handle_globe_command(chat_id: str, user_data: Dict) -> None:
    """Maneja el comando /globe para mostrar horarios de Floating Island."""
    farm_id = user_data.get(chat_id, {}).get('farm_id')
    if not farm_id:
        send_telegram_message(chat_id, "❌ Configura tu ID primero con `/setfarm [ID]`")
        return

    data = fetch_farm_data(farm_id)
    if not data:
        send_telegram_message(chat_id, "❌ Error al obtener datos de la granja.")
        return
    
    logger.info(f"[DEBUG] Datos recibidos de la API: {json.dumps(data, indent=2)}")
    current_time_ms = time.time() * 1000
    floating_island = data.get("farm", {}).get("floatingIsland", {}).get("schedule", [])

    if not floating_island:
        send_telegram_message(chat_id, "No hay eventos de Floating Island programados.")
        return

    message = format_floating_island_message(floating_island, current_time_ms)
    send_telegram_message(chat_id, message)

def handle_help_command(chat_id: str) -> None:
    """Maneja el comando /help."""
    help_text = (
        "📖 *Comandos disponibles:*\n\n"
        "/start - Iniciar el bot\n"
        "/setfarm [ID] - Configurar tu granja\n"
        "/getfarm - Ver tu granja actual\n"
        "/crops - Ver estado de cultivos\n"
        "/beehive - Ver estado de colmenas\n"
        "/globe - Ver horarios de Floating Island\n"
        "/trees - Ver estado de árboles\n"
        "/stones - Ver estado de piedras\n"
        "/help - Mostrar esta ayuda"
    )
    send_telegram_message(chat_id, help_text)

# ==============================================================================
# 6. SISTEMA DE MONITOREO AUTOMÁTICO
# ==============================================================================
"""
Sistema principal de monitoreo automático:

Componentes:
1. check_all_farms_status: 
   - Chequea todas las granjas registradas
   - Ejecuta los procesadores de recursos
   - Consolida y envía notificaciones

2. Manejo de estado:
   - Tracking de notificaciones enviadas
   - Prevención de duplicados
   - Persistencia de datos

3. Gestión de errores:
   - Reintentos en caso de fallos
   - Logging de errores
   - Recuperación automática
"""

def check_all_farms_status(user_data: Dict) -> None:
    """Verifica el estado de todas las granjas registradas."""
    farms_to_check = [(chat_id, info) for chat_id, info in user_data.items() 
                      if not chat_id.startswith('_') and isinstance(info, dict) and info.get('farm_id')]
    
    if not farms_to_check:
        logger.info("No hay granjas registradas para monitorear.")
        return

    current_time_ms = time.time() * 1000
    
    for idx, (chat_id, user_info) in enumerate(farms_to_check):
        if idx > 0:
            logger.info(f"⏸️ Pausa de 10s antes de chequear siguiente granja...")
            time.sleep(10)
        
        farm_id = user_info.get('farm_id')
        logger.info(f"🔍 Chequeando Farm ID {farm_id}...")
        
        data = fetch_farm_data(farm_id)
        if not data:
            continue
        
        notifications = []
        
        # Procesar colmenas
        _, beehive_alerts = process_beehives(data, user_info, current_time_ms)
        notifications.extend(beehive_alerts)
        
        # Procesar cultivos
        crop_alerts = process_crops_alerts(data, user_info, current_time_ms)
        notifications.extend(crop_alerts)
        
        # Procesar árboles
        tree_alerts = process_trees_alerts(data, user_info, current_time_ms)
        notifications.extend(tree_alerts)
        
        # Procesar piedras
        stone_alerts = process_stones_alerts(data, user_info, current_time_ms)
        notifications.extend(stone_alerts)
        
        # Procesar Floating Island
        floating_island_alerts = process_floating_island_alerts(data, user_info, current_time_ms)
        notifications.extend(floating_island_alerts)
        
        # Aquí se pueden agregar más procesadores (animales, etc.)
        
        # Enviar notificaciones consolidadas
        if notifications:
            header = f"📢 *Eventos en Granja {farm_id}* 📢\n\n"
            full_message = header + "\n".join(notifications)
            send_telegram_message(chat_id, full_message)
            logger.info(f"✅ Notificación enviada a {chat_id} (Farm {farm_id})")
        
        save_user_data(user_data)

# ==============================================================================
# 7. BUCLE PRINCIPAL Y EJECUCIÓN
# ==============================================================================
"""
Sistema de ejecución principal del bot:

Componentes:
1. Inicialización:
   - Carga de configuración
   - Verificación de tokens
   - Preparación de logging

2. Bucle principal:
   - Manejo de comandos (rápido)
   - Chequeo de granjas (periódico)
   - Control de errores y recuperación

3. Mantenimiento:
   - Limpieza de recursos
   - Persistencia de datos
   - Gestión de memoria
"""

def initialize_bot() -> None:
    """Inicializa el bot obteniendo el último update_id."""
    global LAST_UPDATE_ID
    
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        response = requests.get(telegram_url, params={'timeout': 1}, timeout=5)
        updates = response.json().get('result', [])
        if updates:
            LAST_UPDATE_ID = updates[-1]['update_id']
            logger.info(f"🔄 Inicializado con update_id: {LAST_UPDATE_ID}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"No se pudo inicializar update_id: {e}")

def main_loop() -> None:
    """Bucle principal del bot."""
    initialize_bot()
    
    last_farm_check_time = time.time() - FARM_CHECK_INTERVAL_SECONDS
    
    initial_user_data = load_user_data()
    loaded_farms = [info.get('farm_id') for info in initial_user_data.values() 
                    if isinstance(info, dict) and info.get('farm_id')]
    
    logger.info("=" * 50)
    logger.info("🤖 Bot de Sunflower Land Multi-Usuario Iniciado")
    logger.info(f"⏱️ Intervalo de comandos: {LOOP_SLEEP_SECONDS}s")
    logger.info(f"⏱️ Intervalo de granja: {FARM_CHECK_INTERVAL_SECONDS}s")
    
    if loaded_farms:
        logger.info(f"✅ Granjas cargadas: {', '.join(loaded_farms)}")
    else:
        logger.info("⚠️ No se encontraron granjas guardadas")
    
    logger.info("=" * 50)

    while True:
        try:
            user_data = load_user_data()
            user_data = handle_telegram_commands(user_data)
            
            current_time = time.time()
            if current_time - last_farm_check_time >= FARM_CHECK_INTERVAL_SECONDS:
                logger.info("🔔 Iniciando chequeo programado de granjas...")
                check_all_farms_status(user_data)
                last_farm_check_time = current_time
            
        except Exception as e:
            logger.exception(f"🚨 ERROR CRÍTICO en el bucle principal: {e}")
        
        time.sleep(LOOP_SLEEP_SECONDS)

# ==============================================================================
# 8. INICIO DEL SCRIPT
# ==============================================================================

if __name__ == "__main__":
    main_loop()