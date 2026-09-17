"""
filtrar_denue.py  —  filtra los 11 cortes del DENUE de una sola pasada.

QUE HACE
  1. Recorre las carpetas denue_09_YYYY y lee el CSV que haya dentro.
  2. Se queda solo con las 14 clases SCIAN del proyecto.
  3. Se queda solo con las columnas que usa el pipeline.
  4. Escribe un CSV limpio por anio en la carpeta  _filtrado/
  5. Imprime un reporte: filas antes y despues, y conteo por clase.
  6. Empaqueta todo en  denue_filtrado.zip

COMO SE USA (Windows)
  1. Instala Python de python.org  -> marca "Add Python to PATH" al instalar.
  2. Abre la terminal (tecla Windows, escribe cmd, Enter).
  3. Instala pandas:      pip install pandas
  4. Pon este archivo en la carpeta que CONTIENE a las carpetas denue_09_*
  5. Muevete a esa carpeta:   cd C:\\ruta\\a\\esa\\carpeta
  6. Corre:                   python filtrar_denue.py

No modifica ni borra tus archivos originales.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("Falta pandas.  Corre primero:   pip install pandas")

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "_filtrado"
ZIP = AQUI / "denue_filtrado.zip"

# --- las 14 clases del proyecto ---------------------------------------------
OFERTA = {
    "464111": "Farmacias sin minisuper",
    "464112": "Farmacias con minisuper",
    "621111": "Consultorios medicina general, privado",
    "621115": "Clinicas de consultorios medicos, privado",
}
CONTEXTO = {
    "464113": "Naturistas y homeopaticos",
    "462111": "Supermercados",
    "462112": "Minisupers",
    "461110": "Abarrotes y miscelaneas",
    "623311": "Asilos y residencias",
}
AMPLIADAS = {
    "621113": "Consultorios medicina especializada, privado",
    "621511": "Laboratorios medicos y de diagnostico",
    "465111": "Perfumeria y cosmeticos",
    "464121": "Lentes",
    "464122": "Articulos ortopedicos",
}
TODAS = {**OFERTA, **CONTEXTO, **AMPLIADAS}

COLS = ["id", "nom_estab", "razon_social", "codigo_act", "nombre_act",
        "per_ocu", "cve_ent", "cve_mun", "cve_loc", "ageb", "manzana",
        "latitud", "longitud", "fecha_alta", "tipo_asent", "nomb_asent",
        "cp", "municipio", "localidad"]


def leer(ruta: Path) -> pd.DataFrame:
    """Los CSV del DENUE vienen en latin-1 casi siempre, a veces en utf-8."""
    ultimo = None
    for enc in ("latin-1", "utf-8", "cp1252"):
        try:
            return pd.read_csv(ruta, encoding=enc, low_memory=False, dtype=str)
        except UnicodeDecodeError as e:
            ultimo = e
            continue
        except Exception as e:                                   # noqa: BLE001
            print(f"      ERROR al leer: {e}")
            return pd.DataFrame()
    print(f"      ERROR de codificacion: {ultimo}")
    return pd.DataFrame()


def main() -> int:
    SALIDA.mkdir(exist_ok=True)

    carpetas = sorted(p for p in AQUI.iterdir()
                      if p.is_dir() and p.name.lower().startswith("denue_09_"))
    if not carpetas:
        print("No encontre ninguna carpeta que empiece con denue_09_")
        print(f"Estoy parada en: {AQUI}")
        print("Mueve este script a la carpeta que contiene esas carpetas.")
        return 1

    print("=" * 70)
    print(f"FILTRANDO {len(carpetas)} CORTES DEL DENUE")
    print("=" * 70)

    resumen = []
    por_clase = {}

    for carpeta in carpetas:
        m = re.search(r"(20\d{2})", carpeta.name)
        anio = m.group(1) if m else carpeta.name

        csvs = list(carpeta.glob("*.csv"))
        if not csvs:
            print(f"\n{anio}: no hay CSV dentro de {carpeta.name}")
            continue
        origen = csvs[0]

        print(f"\n{anio}  <-  {origen.name}")
        df = leer(origen)
        if df.empty:
            continue

        df.columns = [c.strip().lower() for c in df.columns]
        antes = len(df)

        if "codigo_act" not in df.columns:
            print("      NO trae columna codigo_act. Columnas encontradas:")
            print(f"      {list(df.columns)[:20]}")
            continue

        # normalizar la clave a texto de 6 digitos antes de comparar
        df["codigo_act"] = (df["codigo_act"].astype(str).str.strip()
                            .str.replace(r"\.0$", "", regex=True).str.zfill(6))
        df = df[df["codigo_act"].isin(TODAS)].copy()

        cuenta = df["codigo_act"].value_counts().to_dict()
        por_clase[anio] = cuenta

        presentes = [c for c in COLS if c in df.columns]
        faltantes = [c for c in ("codigo_act", "latitud", "longitud")
                     if c not in df.columns]
        df = df[presentes]

        destino = SALIDA / f"denue_09_{anio}.csv"
        df.to_csv(destino, index=False, encoding="utf-8")

        print(f"      {antes:>8,} filas  ->  {len(df):>6,}  "
              f"({len(presentes)} columnas)")
        if faltantes:
            print(f"      OJO, faltan columnas clave: {faltantes}")

        resumen.append({"anio": anio, "antes": antes, "despues": len(df),
                        "archivo": destino.name})

    if not resumen:
        print("\nNo se proceso ningun archivo.")
        return 1

    # ---- reporte por clase, anio por anio ----------------------------------
    print("\n" + "=" * 70)
    print("ESTABLECIMIENTOS POR CLASE Y ANIO")
    print("=" * 70)
    anios = [r["anio"] for r in resumen]
    enc = "clase   " + "".join(f"{a:>7}" for a in anios) + "   descripcion"
    print(enc)
    print("-" * len(enc))
    for clave, nombre in TODAS.items():
        fila = f"{clave}" + "".join(
            f"{por_clase.get(a, {}).get(clave, 0):>7,}" for a in anios)
        marca = " *" if clave in OFERTA else "  "
        print(f"{fila}{marca} {nombre}")
    print("\n* = clase que cuenta como oferta en el modelo")

    # ---- totales -----------------------------------------------------------
    print("\n" + "=" * 70)
    print("TOTALES")
    print("=" * 70)
    for r in resumen:
        print(f"  {r['anio']}:  {r['antes']:>8,}  ->  {r['despues']:>6,}")

    # ---- plantilla de meses ------------------------------------------------
    # Los cortes del DENUE no son todos del mismo mes. El modelo necesita el
    # tiempo transcurrido REAL entre cortes, no asumir 12 meses parejos.
    meses = SALIDA / "meses.txt"
    if not meses.exists():
        lineas = ["# Escribe el mes de cada corte (numero del 1 al 12) despues del '='",
                  "# Ejemplo:  2016=5   si ese corte es de mayo",
                  ""]
        lineas += [f"{r['anio']}=" for r in resumen]
        meses.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        print(f"\n  >> LLENA EL ARCHIVO:  {meses}")
        print("     Un numero de mes por anio. Tarda un minuto y evita que el")
        print("     modelo asuma que todos los cortes estan a 12 meses de distancia.")

    # ---- empaquetar --------------------------------------------------------
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(SALIDA.glob("*.csv")):
            z.write(f, f.name)
        if meses.exists():
            z.write(meses, meses.name)
    mb = ZIP.stat().st_size / 1e6

    print("\n" + "=" * 70)
    print(f"LISTO:  {ZIP.name}   ({mb:.1f} MB)")
    print(f"        CSV limpios en:  {SALIDA}")
    print("=" * 70)
    print("\nCopia el reporte de arriba y mandamelo junto con el zip.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
