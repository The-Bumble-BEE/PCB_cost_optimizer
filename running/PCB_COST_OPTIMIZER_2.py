import itertools
import re
import math
import csv
from collections import defaultdict

# =====================================================
# Einheiten
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

    value_str = value_str.strip().replace(",", ".")

    match = re.match(
        r"^([\d.]+(?:e[-+]?\d+)?)\s*([pnumkMGµ]?)[A-Za-z]*$",
        value_str,
        re.IGNORECASE
    )

    if not match:
        raise ValueError(f"Ungültiges Format: {value_str}")

    number = float(match.group(1))
    prefix = match.group(2)

    return number * UNIT_PREFIXES.get(prefix, 1)


# =====================================================
# Typ-Erkennung
# =====================================================

def detect_type(value_str):

    s = value_str.lower()

    if "r" in s or "k" in s or "ohm" in s:
        return "R"

    if "f" in s:
        return "C"

    if "h" in s:
        return "L"

    return None


# =====================================================
# CSV Bauteildatenbank
# =====================================================

def load_components_from_csv(filename):

    components = []

    with open(filename, newline="", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        for row in reader:

            components.append({
                "type": row["type"],
                "raw": row["raw"],
                "value": parse_value(row["value"]),
                "package": row["package"],
                "tolerance": row["tolerance"],
                "voltage": row["voltage"],
                "price": float(row["price"]),
                "supplier": row["supplier"]
            })

    return components


# =====================================================
# KiCad Pick&Place Import
# =====================================================

def load_kicad_file(filename):

    parts = []

    with open(filename, encoding="utf-8") as f:

        reader = csv.reader(f)

        header = next(reader, None)  # erste Zeile überspringen

        for row in reader:
            
            if len(row) < 3:
                continue

            ref = row[0].strip()
            value = row[1].strip()
            footprint = row[2].strip()
            try:
                parts.append({
                    "ref": ref,
                    "raw": value,
                    "value": parse_value(value),
                    "package": footprint,
                    "type": detect_type(value)
                })

            except:
                continue

    return parts


# =====================================================
# BOM Gruppierung
# =====================================================

def group_parts(parts):

    grouped = defaultdict(int)

    for p in parts:

        key = (p["raw"], p["type"])

        grouped[key] += 1

    result = []

    for (value, typ), qty in grouped.items():

        result.append({
            "raw": value,
            "type": typ,
            "quantity": qty,
            "value": parse_value(value)
        })

    return result


# =====================================================
# Netzwerk Berechnung
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

def calculate(target, components, kind="R", tolerance=0.01, max_parts=3):

    best_solution = None
    best_price = float("inf")

    filtered = [c for c in components if c["type"] == kind]

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
# Board Analyse
# =====================================================
def find_original_price(part, components):

    candidates = [
        c for c in components
        if c["type"] == part["type"]
        and math.isclose(c["value"], part["value"], rel_tol=1e-6)
    ]

    if not candidates:
        return None

    # günstigstes passendes Bauteil nehmen
    return min(c["price"] for c in candidates)

def analyze_board(parts, components):

    grouped = group_parts(parts)

    report = []

    for p in grouped:

        if not p["type"]:
            continue

        result = calculate(
            target=p["value"],
            components=components,
            kind=p["type"],
            tolerance=0.02,
            max_parts=3
        )
        
        original_price = find_original_price(p, components)
        
        if result:
        
            mode, combo, achieved, new_price = result
        
            # 👉 nur echte Ersatzlösungen
            if len(combo) == 1:
                continue
        
            report.append({
                "target": p["raw"],
                "quantity": p["quantity"],
                "solution": combo,
                "mode": mode,
                "original_price": original_price,
                "new_price": new_price
            })

    return report


# =====================================================
# UI
# =====================================================

def main_menu():

    print()
    print("====================================")
    print(" PCB Cost Optimizer ")
    print("====================================")
    print("1) KiCad Board analysieren")
    print("2) Einzelwert berechnen")
    print("3) Beenden")

    return input("Auswahl: ")


def run_kicad_analysis(components):

    filename = input("KiCad Pick&Place Datei: ")

    print("Lade Datei...")

    parts = load_kicad_file(filename)

    print("Bauteile gefunden:", len(parts))

    report = analyze_board(parts, components)

    print()
    print("Optimierungsvorschläge")
    print("----------------------")

    for r in report:

        print()
        print("Zielwert:", r["target"])
        print("Anzahl:", r["quantity"])
        print("Schaltung:", r["mode"])
        print("Preis vorher:", 
              f"{r['original_price']} €" if r["original_price"] is not None else "nicht vorhanden")
        
        print("Preis nachher:", r["new_price"], "€")
        
        if r["original_price"] is not None:
            diff = r["original_price"] - r["new_price"]
            print("Ersparnis:", round(diff, 6), "€")

        print("Bauteile:")

        for c in r["solution"]:
            print(" ", c["raw"], "-", c["price"], "€")


def run_single_solver(components):

    target = input("Zielwert: ")
    typ = input("Typ (R/C/L): ")

    result = calculate(
        target=parse_value(target),
        components=components,
        kind=typ,
        tolerance=0.01,
        max_parts=5
    )

    if result:

        mode, combo, achieved, price = result

        print()
        print("Beste Lösung")
        print("Schaltung:", mode)
        print("Wert:", achieved)
        print("Preis:", price)

        print("Bauteile:")

        for c in combo:
            print(" ", c["raw"], c["price"], "€")

    else:

        print("Keine Lösung gefunden")


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    print("Lade Bauteildatenbank...")

    components = load_components_from_csv("components.csv")

    print("Bauteile geladen:", len(components))

    while True:

        choice = main_menu()

        if choice == "1":
            run_kicad_analysis(components)

        elif choice == "2":
            run_single_solver(components)

        elif choice == "3":
            break

        else:
            print("Ungültige Auswahl")