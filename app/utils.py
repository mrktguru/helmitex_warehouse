from typing import Dict

def parse_key_value_lines(text: str) -> Dict[str, float]:
    """
    Parse lines like:
      Категория: 12.3
    Returns dict {category_name: value}
    """
    result = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip().replace(",", ".")
            try:
                result[k] = float(v)
            except ValueError:
                continue
    return result
