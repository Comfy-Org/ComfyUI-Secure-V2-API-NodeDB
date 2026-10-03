# node_logger.py

# Словник ANSI кольорів
COLORS = {
  'BLACK': '\33[30m', 'RED': '\33[31m', 'GREEN': '\33[32m', 'YELLOW': '\33[33m',
  'BLUE': '\33[34m', 'MAGENTA': '\33[35m', 'CYAN': '\33[36m', 'WHITE': '\33[37m',
  'GREY': '\33[90m', 'BRIGHT_RED': '\33[91m', 'BRIGHT_GREEN': '\33[92m', 
  'BRIGHT_YELLOW': '\33[93m', 'BRIGHT_BLUE': '\33[94m', 'BRIGHT_MAGENTA': '\33[95m',
  'BRIGHT_CYAN': '\33[96m', 'BRIGHT_WHITE': '\33[97m',
  'RESET': '\33[00m', 'BOLD': '\33[01m', 'NORMAL': '\33[22m', 'ITALIC': '\33[03m',
  'UNDERLINE': '\33[04m', 'BLINK': '\33[05m', 'BLINK2': '\33[06m', 'SELECTED': '\33[07m',
  'BG_BLACK': '\33[40m', 'BG_RED': '\33[41m', 'BG_GREEN': '\33[42m', 'BG_YELLOW': '\33[43m',
  'BG_BLUE': '\33[44m', 'BG_MAGENTA': '\33[45m', 'BG_CYAN': '\33[46m', 'BG_WHITE': '\33[47m',
  'BG_GREY': '\33[100m', 'BG_BRIGHT_RED': '\33[101m', 'BG_BRIGHT_GREEN': '\33[102m',
  'BG_BRIGHT_YELLOW': '\33[103m', 'BG_BRIGHT_BLUE': '\33[104m', 'BG_BRIGHT_MAGENTA': '\33[105m',
  'BG_BRIGHT_CYAN': '\33[106m', 'BG_BRIGHT_WHITE': '\33[107m',
}

# Унікальний глобальний префікс
GLOBAL_PREFIX = "San4itos" # Замініть на бажаний


def log(message, color=None, msg_color=None, prefix=None):
  """Базова функція логування."""
  # Колір для [GLOBAL_PREFIX][prefix]
  color_code = COLORS.get(str(color).upper(), COLORS.get("BRIGHT_GREEN")) 
  # Колір для самого повідомлення
  msg_color_code = COLORS.get(str(msg_color).upper(), '') # Якщо msg_color не вказано, колір не змінюється
  
  prefix_str = f'[{prefix}]' if prefix is not None else ''
  
  
  # Збережемо логіку: color - це колір для всього блоку префіксів
  full_prefix_block = f"[{GLOBAL_PREFIX}]{prefix_str}"
  
  # Якщо msg_color не вказано (тобто порожній рядок), то повідомлення буде того ж кольору, що й префікс,
  # доки не зустрінеться COLORS["RESET"]. Якщо msg_color вказано, він перекриє колір префіксу для тексту повідомлення.
  print(f'{color_code}{full_prefix_block}{COLORS.get("RESET")} {msg_color_code}{message}{COLORS.get("RESET")}')
  # Невелика зміна: додав RESET після префіксу, щоб msg_color не "успадковував" колір префіксу, якщо msg_color не заданий.
  # Або, якщо хочемо поведінки, де msg_color='' означає "продовжити поточний колір":
  # print(f'{color_code}{full_prefix_block} {msg_color_code}{message}{COLORS.get("RESET")}')


def _log_node(prefix_block_color_name, node_specific_prefix, message, msg_color='RESET'):
  """Внутрішня функція логування для вузлів (адаптована з rgthree)."""
  log(message, color=prefix_block_color_name, prefix=node_specific_prefix, msg_color=msg_color)


def log_node_success(node_name, message, msg_color_override='BRIGHT_GREEN'):
  """Логує повідомлення про успіх."""
  _log_node("GREEN", node_name, message, msg_color=msg_color_override) 


def log_node_info(node_name, message, msg_color_override='YELLOW'):
  """Логує інформаційне повідомлення."""
  _log_node("CYAN", node_name, message, msg_color=msg_color_override) 


def log_node_warning(node_name, message, msg_color_override='BRIGHT_YELLOW'):
  """Логує попередження."""
  _log_node("YELLOW", node_name, message, msg_color=msg_color_override) 


def log_node_error(node_name, message, msg_color_override='BRIGHT_RED'):
  """Логує повідомлення про помилку."""
  _log_node("RED", node_name, message, msg_color=msg_color_override) 


# Якщо у вас є log_node_debug або log_node_message, їх також потрібно перевірити/виправити:
def log_node_debug(node_name, message, msg_color_override='GREY'):
    _log_node("MAGENTA", node_name, message, msg_color=msg_color_override) 
