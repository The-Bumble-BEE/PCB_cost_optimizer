import itertools
import re
import math
import csv

# =====================================================
# Einheiten-Konverter
# =====================================================

UNIT_PREFIXES = {
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "µ": 1e-6,
    "m": 1e-3,
    "": 1,
    "k": 1e3,
    "M": 1e6,
    "G": 1e9,
}


def parse_value(value_str):

    value_str = value_str.strip()

    match = re.match(r"^([\d.,]+)\s*([pnumkMGµ]?)[A-Za-z]*$", value_str)

    if not match:
        raise ValueError(f"Ungültiges Format: {value_str}")

    number = float(match.group(1).replace(",", "."))
    prefix = match.group(2)

    return number * UNIT_PREFIXES.get(prefix, 1)

# =====================================================
# CSV Import
# =====================================================

def load_components_from_csv(filename):

    loaded = []

    with open(filename, newline="", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        for row in reader:
            loaded.append({
                "type": row["type"],
                "raw": row["raw"],
                "value": float(row["value"]),
                "package": row["package"],
                "tolerance": row["tolerance"],
                "voltage": row["voltage"],
                "price": float(row["price"]),
                "supplier": row["supplier"]
            })

    return loaded


# =====================================================
# Netzwerktopologie
# =====================================================

def series_value(values):
    return sum(values)


def parallel_value(values):

    denom = sum(1.0 / v for v in values if v != 0)

    if denom == 0:
        return float("inf")

    return 1.0 / denom


# =====================================================
# Solver
# =====================================================

def calculate(target, kind="R", tolerance=0.01, max_parts=3, supplier_filter=None):

    best_solution = None
    best_price = float("inf")

    filtered = [
        c for c in components
        if c["type"] == kind and (supplier_filter is None or c["supplier"] == supplier_filter)
    ]

    for r in range(1, max_parts + 1):

        for combo in itertools.combinations_with_replacement(filtered, r):

            values = [c["value"] for c in combo]
            price = sum(c["price"] for c in combo)

            if kind in ["R", "L"]:

                val_series = series_value(values)

                if math.isclose(val_series, target, rel_tol=tolerance):

                    if price < best_price:
                        best_solution = ("Series", combo, val_series, price)
                        best_price = price

                if len(values) > 1:

                    val_parallel = parallel_value(values)

                    if math.isclose(val_parallel, target, rel_tol=tolerance):

                        if price < best_price:
                            best_solution = ("Parallel", combo, val_parallel, price)
                            best_price = price

            elif kind == "C":

                if len(values) > 1:

                    val_series = parallel_value(values)

                    if math.isclose(val_series, target, rel_tol=tolerance):

                        if price < best_price:
                            best_solution = ("Series", combo, val_series, price)
                            best_price = price

                val_parallel = series_value(values)

                if math.isclose(val_parallel, target, rel_tol=tolerance):

                    if price < best_price:
                        best_solution = ("Parallel", combo, val_parallel, price)
                        best_price = price

    return best_solution


# =====================================================
# Beispiel
# =====================================================

if __name__ == "__main__":

    # CSV laden
    print("loading part database")
    components = load_components_from_csv("components.csv")

    target_value = parse_value("240kOhm")

    result = calculate(
        target=target_value,
        kind="R",
        tolerance=0.01,
        max_parts=5,
        supplier_filter="reichelt"
    )

    if result:

        mode, combo, achieved, price = result

        print("\nBeste Lösung")
        print("Schaltung:", mode)
        print("Wert:", achieved)
        print("Preis:", price)
        print("\nBauteile:")

        for c in combo:
            print(c["raw"], c["price"], "€")

    else:
        print("Keine passende Kombination gefunden.")