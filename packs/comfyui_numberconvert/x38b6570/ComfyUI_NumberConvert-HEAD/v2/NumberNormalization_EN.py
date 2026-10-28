import re
from datetime import datetime

# 数字到单词的映射
num_to_word = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven",
    12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen",
    17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty", 30: "thirty",
    40: "forty", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety"
}

def number_to_words(n):
    """Convert number to words"""
    if n < 10:
        return num_to_word[n]
    elif 10 <= n <= 20:
        return num_to_word[n]
    elif n < 100:
        tens, remainder = divmod(n, 10)
        return f"{num_to_word[tens * 10]}{'' if remainder == 0 else ' ' + num_to_word[remainder]}"
    elif n < 1000:
        hundreds, remainder = divmod(n, 100)
        return f"{num_to_word[hundreds]} hundred" + (f" {number_to_words(remainder)}" if remainder else "")
    else:
        # 为了安全，不随意拼更大的数，直接返回原字符串
        return str(n)

# 数字到序数的词典（用于日期日）
number_to_words_dict = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
    6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
    11: "eleventh", 12: "twelfth", 13: "thirteenth", 14: "fourteenth",
    15: "fifteenth", 16: "sixteenth", 17: "seventeenth", 18: "eighteenth",
    19: "nineteenth", 20: "twentieth", 21: "twenty-first", 22: "twenty-second",
    23: "twenty-third", 24: "twenty-fourth", 25: "twenty-fifth", 26: "twenty-sixth",
    27: "twenty-seventh", 28: "twenty-eighth", 29: "twenty-ninth", 30: "thirtieth",
    31: "thirty-first"
}

def ordinal_number(n):
    """Convert integer to ordinal number using a dictionary."""
    return number_to_words_dict.get(n, "Invalid number")

def process_decimal_part(decimal_part):
    """Process decimal part of a number"""
    if len(decimal_part) > 2:
        return ' '.join(number_to_words(int(digit)) for digit in decimal_part)
    else:
        return number_to_words(int(decimal_part))

def process_percentage(text):
    """Convert percentages"""
    return re.sub(
        r'(\d+(?:\.\d+)?)%',
        lambda m: (
            f"{number_to_words(int(m.group(1).split('.')[0]))}"
            + (f" point {process_decimal_part(m.group(1).split('.')[1])}" if '.' in m.group(1) else "")
            + " percent"
        ),
        text
    )

def year_to_words(year: int) -> str:
    """
    将 1000–2099 的数字按“年份读法”转成单词：
    2000      -> two thousand
    2001–2009 -> two thousand and X
    2010–2099 -> twenty XX
    1900–1999 -> nineteen XX
    1000–1899 -> <first two digits> hundred <last two digits>
    """
    if 2000 <= year <= 2009:
        last = year % 100
        return "two thousand" if last == 0 else f"two thousand and {number_to_words(last)}"
    elif 2010 <= year <= 2099:
        return f"twenty {number_to_words(year % 100)}"
    elif 1900 <= year <= 1999:
        return f"nineteen {number_to_words(year % 100)}"
    elif 1000 <= year <= 1899:
        first_two = year // 100
        last_two = year % 100
        return f"{number_to_words(first_two)} hundred{'' if last_two == 0 else ' ' + number_to_words(last_two)}"
    else:
        return str(year)

# 月份表，用于 "March 2025" 这类
MONTHS = (
    "January","February","March","April","May","June","July",
    "August","September","October","November","December"
)

def process_years_with_context(text):
    """
    只在“有年份语境”的情况下，将 1000–2099 转成年份读法。
    支持：
      - from Y to Z / between Y and Z（两个年份）
      - in/by/since/until/during/around/circa/on/after/before/within/from + YEAR
      - Month YEAR（如 March 2025）
    """
    # 先处理区间（from … to … / between … and …）
    def repl_range(m):
        y1 = int(m.group('y1'))
        y2 = int(m.group('y2'))
        return m.group(0).replace(m.group('y1'), year_to_words(y1)).replace(m.group('y2'), year_to_words(y2))

    text = re.sub(
        r'\bfrom\s+(?P<y1>(?:1\d{3}|20\d{2}))\s+(?:to|through|till|until|[-–—])\s+(?P<y2>(?:1\d{3}|20\d{2}))\b',
        repl_range, text, flags=re.IGNORECASE
    )
    text = re.sub(
        r'\bbetween\s+(?P<y1>(?:1\d{3}|20\d{2}))\s+and\s+(?P<y2>(?:1\d{3}|20\d{2}))\b',
        repl_range, text, flags=re.IGNORECASE
    )

    # 单词上下文 + YEAR（单词列表可按需扩展）
    def repl_ctx(m):
        y = int(m.group('year'))
        return f"{m.group('ctx')}{year_to_words(y)}"

    text = re.sub(
        r'\b(?P<ctx>(?:in|by|since|until|during|around|circa|on|after|before|through|till|within|from)\s+)'
        r'(?P<year>(?:1\d{3}|20\d{2}))\b',
        repl_ctx, text, flags=re.IGNORECASE
    )

    # 双词上下文（如 "as of 2025", "starting in 2025"）
    text = re.sub(
        r'\b(?P<ctx>(?:as\s+of|starting\s+in|starting\s+from|no\s+later\s+than|not\s+later\s+than|on\s+or\s+after|on\s+or\s+before|up\s+to)\s+)'
        r'(?P<year>(?:1\d{3}|20\d{2}))\b',
        repl_ctx, text, flags=re.IGNORECASE
    )

    # Month YEAR
    def repl_month_year(m):
        month = m.group('month')  # 保留原样大小写
        y = int(m.group('year'))
        return f"{month} {year_to_words(y)}"

    text = re.sub(
        r'\b(?P<month>' + '|'.join(MONTHS) + r')\s+(?P<year>(?:1\d{3}|20\d{2}))\b',
        repl_month_year, text, flags=re.IGNORECASE
    )

    return text

def process_date(text):
    """Convert date format YYYY-MM-DD（完整日期优先）"""
    def date_match(m):
        try:
            date_str = m.group(0)
            date = datetime.strptime(date_str, "%Y-%m-%d")
            month_name = date.strftime('%B')
            day = int(date.strftime('%d'))
            day_ordinal = ordinal_number(day)
            year = date.year

            # 年份按“世纪+年份”读法
            if year < 100:
                year_str = number_to_words(year)
            else:
                first_part = year // 100
                second_part = year % 100
                year_str = f"{number_to_words(first_part)} {number_to_words(second_part)}"

            return f"{month_name} {day_ordinal}, {year_str}"
        except ValueError:
            return m.group(0)
    return re.sub(r'\b\d{4}-\d{2}-\d{2}\b', date_match, text)

def process_number_with_unit(text):
    """Convert numbers (including decimals) with units or nouns"""
    return re.sub(
        r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)',
        lambda m: (
            f"{number_to_words(int(m.group(1).split('.')[0]))}"
            + (f" point {process_decimal_part(m.group(1).split('.')[1])}" if '.' in m.group(1) else "")
            + f" {m.group(2)}"
        ),
        text
    )

def process_decimal_large(text):
    """Convert decimal numbers with more than 2 digits after point"""
    return re.sub(
        r'(\d+)\.(\d{3,})',
        lambda m: f"{number_to_words(int(m.group(1)))} point {' '.join(number_to_words(int(digit)) for digit in m.group(2))}",
        text
    )

def process_decimal_numbers(text):
    """Convert decimal numbers without percentage or units"""
    return re.sub(
        r'(\d+)\.(\d+)',
        lambda m: f"{number_to_words(int(m.group(1)))} point {process_decimal_part(m.group(2))}",
        text
    )

def process_pure_number(text):
    """Convert pure numbers (no units or nouns) to word-by-word"""
    return re.sub(
        r'\b\d+\b',
        lambda m: ' '.join(number_to_words(int(d)) for d in m.group(0)),
        text
    )

def process_text(text):
    # 处理顺序很重要：先日期 -> 再“上下文年份” -> 其他数值
    text = process_date(text)
    text = process_years_with_context(text)  # 只在语境中把 1000–2099 当年份
    text = process_percentage(text)
    text = process_number_with_unit(text)
    text = process_decimal_large(text)
    text = process_decimal_numbers(text)
    text = process_pure_number(text)
    return text


class ConvertNumbersToWordsNode:
    """
    Node to convert numbers in text to words
    """

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {
                    "multiline": True,
                    "default": "输入需要转换的文本"
                })
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "convert_numbers_to_words"
    CATEGORY = "🔢NumberConvert"

    def convert_numbers_to_words(self, input_text):
        converted_text = process_text(input_text)
        return (converted_text,)


NODE_CLASS_MAPPINGS = {
    "ConvertNumbersToWords": ConvertNumbersToWordsNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ConvertNumbersToWords": "Convert Numbers to Words"
}

