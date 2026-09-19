"""
Lectura y limpieza de las fuentes. Una funcion por fuente.

Todas devuelven datos ya normalizados a la llave CVEGEO de 13 caracteres:
    ENTIDAD(2) + MUN(3) + LOC(4) + AGEB(4)
"""
from __future__ import annotations

import glob
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as cfg


# ==========================================================================
# utilidades
# ==========================================================================
def leer_csv(ruta, **kw) -> pd.DataFrame:
    """Los archivos del INEGI vienen en utf-8 con BOM, latin-1 o cp1252."""
    for enc in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            return pd.read_csv(ruta, encoding=enc, low_memory=False, dtype=str, **kw)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No pude leer {ruta} con ninguna codificacion conocida.")


def a_num(s: pd.Series) -> pd.Series:
    """
    Convierte una columna censal a numero.

    El INEGI marca con '*' los indicadores con menos de tres unidades
    (confidencialidad) y con 'N/D' los no disponibles. Ambos se vuelven NaN,
    nunca cero: ausencia de dato no es ausencia de poblacion.
    """
    return pd.to_numeric(
        s.astype(str).str.strip().replace({"*": np.nan, "N/D": np.nan,
                                           "": np.nan, "nan": np.nan}),
        errors="coerce")


def buscar(patron: str, base: Path = None) -> Path:
    base = base or cfg.CRUDOS
    hits = sorted(base.rglob(patron))
    if not hits:
        raise FileNotFoundError(f"No encontre '{patron}' dentro de {base}")
    return hits[0]


# ==========================================================================
# 1. geometrias
# ==========================================================================
def cargar_agebs(anio: int = 2020):
    """
    Capa de AGEB urbana de la annada pedida del Marco Geoestadistico.

    Todas las annadas ya vienen en EPSG:6372 (Mexico ITRF2008 / LCC), asi que
    no hay que reproyectar los poligonos: las distancias ya estan en metros.
    """
    import geopandas as gpd

    cands = sorted(cfg.CRUDOS.rglob("09a.shp"))
    if not cands:
        raise FileNotFoundError(f"No encontre ningun 09a.shp en {cfg.CRUDOS}")

    elegido = next((p for p in cands if str(anio) in str(p)), cands[0])
    g = gpd.read_file(elegido)
    g.columns = [c.upper() if c != "geometry" else c for c in g.columns]
    if "CVEGEO" not in g.columns:
        raise KeyError(f"{elegido} no trae CVEGEO. Columnas: {list(g.columns)}")

    g["CVEGEO"] = g["CVEGEO"].astype(str).str.strip()
    g["CVE_MUN"] = g["CVEGEO"].str[:5]
    if g.crs is None:
        g = g.set_crs(cfg.CRS_METRICO)
    else:
        g = g.to_crs(cfg.CRS_METRICO)
    g["area_km2"] = g.geometry.area / 1e6
    return g[["CVEGEO", "CVE_MUN", "area_km2", "geometry"]].copy(), elegido


def cargar_alcaldias(anio: int = 2020):
    """
    Capa de limites de alcaldia, para que quien no conoce la ciudad pueda
    ubicarse. Sin esto el mapa es una mancha de poligonos sin referencia.
    """
    import geopandas as gpd

    cands = sorted(cfg.CRUDOS.rglob("09mun.shp"))
    if not cands:
        return None
    elegido = next((p for p in cands if str(anio) in str(p)), cands[0])
    g = gpd.read_file(elegido)
    g.columns = [c.upper() if c != "geometry" else c for c in g.columns]
    llave = "CVEGEO" if "CVEGEO" in g.columns else "CVE_MUN"
    g["CVE_MUN"] = g[llave].astype(str).str.strip().str.zfill(5)
    g = g.to_crs(cfg.CRS_METRICO) if g.crs else g.set_crs(cfg.CRS_METRICO)
    return g[["CVE_MUN", "geometry"]].dissolve(by="CVE_MUN").reset_index()


def colonias_por_ageb(puntos) -> pd.DataFrame:
    """
    Nombres de colonia por AGEB, sacados del campo nomb_asent del DENUE.

    El censo no publica nombres de colonia, pero cada establecimiento del DENUE
    trae el asentamiento donde esta. Agregando por AGEB obtenemos con que nombre
    conoce la gente a cada zona, que es como un juez va a buscarla: nadie teclea
    '0901500011234', tecleen 'Roma Norte'.
    """
    if "nomb_asent" not in puntos.columns:
        return pd.DataFrame(columns=["CVEGEO", "colonias"])

    p = puntos.copy()
    p["_cve"] = (cfg.ENTIDAD
                 + p["cve_mun"].astype(str).str.strip().str.zfill(3)
                 + p["cve_loc"].astype(str).str.strip().str.zfill(4)
                 + p["ageb"].astype(str).str.strip().str.zfill(4))
    p["_col"] = (p["nomb_asent"].astype(str).str.strip().str.upper()
                 .replace({"NAN": None, "": None}))
    p = p.dropna(subset=["_col"])

    filas = []
    for cve, grp in p.groupby("_cve"):
        top = grp["_col"].value_counts().head(3).index.tolist()
        filas.append({"CVEGEO": cve, "colonias": " · ".join(top)})
    return pd.DataFrame(filas)


def completar_por_vecindad(agebs, colonias: pd.DataFrame) -> pd.DataFrame:
    """
    Nombra las AGEB que no tienen ningun establecimiento adentro.

    El nombre de cada zona sale del campo de asentamiento del DENUE, o sea de
    los negocios registrados dentro del poligono. Una AGEB estrictamente
    residencial -uso de suelo sin comercio- no tiene de donde sacarlo, y salia
    etiquetada con su clave: 'AGEB 0853'. Eran 102 de 2,431, y una de ellas
    era la recomendacion numero uno de la ciudad.

    Aqui se completan con las colonias de las AGEB que las TOCAN. El nombre
    queda marcado con '~' para no afirmar que la zona ES esa colonia: dice que
    esta junto a ella, que es lo unico que sabemos y lo unico que un juez
    necesita para ubicarla en el mapa.
    """
    import geopandas as gpd

    g = agebs[["CVEGEO", "geometry"]].merge(colonias, on="CVEGEO", how="left")
    vacias = g["colonias"].isna() | (g["colonias"].astype(str).str.strip() == "")
    if not vacias.any():
        return colonias

    con = g[~vacias]
    sin = g[vacias]

    # sjoin de tipo 'touches' via predicate; es barato con 102 poligonos
    pares = gpd.sjoin(sin[["CVEGEO", "geometry"]],
                      con[["CVEGEO", "colonias", "geometry"]].rename(
                          columns={"CVEGEO": "CVEGEO_vec"}),
                      how="left", predicate="touches")

    nuevas = []
    for cve, grp in pares.groupby("CVEGEO"):
        nombres = []
        for txt in grp["colonias"].dropna():
            for parte in str(txt).split(" · "):
                parte = parte.strip()
                if parte and parte not in nombres:
                    nombres.append(parte)
        if nombres:
            nuevas.append({"CVEGEO": cve, "colonias": "~ " + " · ".join(nombres[:2])})

    if not nuevas:
        return colonias
    return pd.concat([colonias, pd.DataFrame(nuevas)], ignore_index=True)


def inventario_agebs() -> pd.DataFrame:
    """Cuantas AGEB tiene cada annada del Marco Geoestadistico."""
    import geopandas as gpd

    filas = []
    for p in sorted(cfg.CRUDOS.rglob("09a.shp")):
        m = re.search(r"mg[_ ]?(\d{4})", str(p))
        anio = int(m.group(1)) if m else None
        g = gpd.read_file(p, columns=["CVEGEO"])
        filas.append({"annada": anio, "n_ageb": len(g), "ruta": p.name})
    return pd.DataFrame(filas).sort_values("annada").reset_index(drop=True)


# ==========================================================================
# 2. censos
# ==========================================================================
COLS_EDAD = ["POBTOT", "P_60YMAS", "POB65_MAS", "POB0_14", "POB15_64",
             "P_0A2", "P_3A5", "P_6A11", "P_15A17", "P_18A24"]


def cargar_censo(ruta, sufijo: str) -> pd.DataFrame:
    """
    Tabla por AGEB del censo.

    A nivel AGEB el censo NO publica grupos quinquenales: las unicas variables
    de edad son P_60YMAS, POB65_MAS, POB0_14, POB15_64 y las bandas de infancia
    y juventud. El detalle 40-44, 45-49, etc. solo existe a nivel alcaldia.
    Los mnemonicos son identicos entre 2010 y 2020, asi que la comparacion
    es directa.
    """
    df = leer_csv(ruta)
    df.columns = [c.strip().upper() for c in df.columns]

    # el archivo ya viene filtrado a nivel AGEB, pero por si acaso
    if "MZA" in df.columns:
        mza = df["MZA"].astype(str).str.strip().str.zfill(3)
        ageb = df["AGEB"].astype(str).str.strip().str.zfill(4)
        df = df[(mza == "000") & (ageb != "0000")]

    out = pd.DataFrame({
        "CVEGEO": (df["ENTIDAD"].astype(str).str.strip().str.zfill(2)
                   + df["MUN"].astype(str).str.strip().str.zfill(3)
                   + df["LOC"].astype(str).str.strip().str.zfill(4)
                   + df["AGEB"].astype(str).str.strip().str.zfill(4))
    })
    out["CVE_MUN"] = out["CVEGEO"].str[:5]

    for c in COLS_EDAD:
        out[f"{c.lower()}_{sufijo}"] = a_num(df[c]) if c in df.columns else np.nan

    # movilidad residencial: proxy de rotacion. El nombre cambia entre censos.
    for cand in ("PRES2015", "PRES2005"):
        if cand in df.columns:
            out[f"pres_{sufijo}"] = a_num(df[cand])
            break

    return out.drop_duplicates("CVEGEO").reset_index(drop=True)


def empatar_censos(c2020: pd.DataFrame, c2010: pd.DataFrame):
    """
    Une los dos censos por CVEGEO y reporta la cobertura del empate.

    Las AGEB cambian entre cortes porque se subdividen donde crece la poblacion.
    En la CDMX el cambio es minimo: la ciudad ya estaba amanzanada en 2010.
    """
    unida = c2020.merge(c2010, on=["CVEGEO", "CVE_MUN"], how="left")
    k20, k10 = set(c2020.CVEGEO), set(c2010.CVEGEO)
    n_emp = int(unida["p_60ymas_2010"].notna().sum())
    diag = {
        "agebs_censo_2020": len(k20),
        "agebs_censo_2010": len(k10),
        "agebs_empatadas": n_emp,
        "tasa_empate": round(n_emp / max(len(k20), 1), 4),
        "nuevas_en_2020": len(k20 - k10),
        "desaparecidas_desde_2010": len(k10 - k20),
    }
    return unida, diag


# ==========================================================================
# 3. DENUE
# ==========================================================================
def cargar_denue(ruta, clases=None):
    """Un corte del DENUE como GeoDataFrame de puntos, reproyectado a metros."""
    import geopandas as gpd

    df = leer_csv(ruta)
    df.columns = [c.strip().lower() for c in df.columns]

    faltan = [c for c in ("codigo_act", "latitud", "longitud")
              if c not in df.columns]
    if faltan:
        raise KeyError(f"{ruta} no trae {faltan}. Tiene: {list(df.columns)}")

    df["codigo_act"] = (df["codigo_act"].astype(str).str.strip()
                        .str.replace(r"\.0$", "", regex=True).str.zfill(6))
    if clases:
        df = df[df["codigo_act"].isin(clases)]

    df["lat"] = pd.to_numeric(df["latitud"], errors="coerce")
    df["lon"] = pd.to_numeric(df["longitud"], errors="coerce")
    antes = len(df)
    df = df.dropna(subset=["lat", "lon"])
    # descartar coordenadas fuera del bbox de la CDMX
    df = df[(df.lat.between(19.0, 19.95)) & (df.lon.between(-99.40, -98.90))]

    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat),
                         crs=cfg.CRS_GEO).to_crs(cfg.CRS_METRICO)
    g.attrs["descartados_por_coordenada"] = antes - len(g)
    return g


def cargar_todos_los_denue(clases=None) -> dict:
    """{anio: GeoDataFrame} para los 11 cortes."""
    salida = {}
    for p in sorted(cfg.CRUDOS.rglob("denue_09_*.csv")):
        m = re.search(r"(20\d{2})", p.name)
        if not m:
            continue
        salida[int(m.group(1))] = cargar_denue(p, clases)
    return dict(sorted(salida.items()))


# ==========================================================================
# 4. CONEVAL
# ==========================================================================
GRADOS = {"Muy bajo": 1, "Bajo": 2, "Medio": 3, "Alto": 4, "Muy alto": 5}


def cargar_coneval(ruta) -> pd.DataFrame:
    """
    Rezago social por AGEB urbana 2020.

    El archivo trae el encabezado en la fila 4, la clave de AGEB de 13
    caracteres en 'Clave de la AGEB', y en la fila siguiente los nombres de
    los 16 indicadores continuos que componen el indice.

    Ademas del GRADO ordinal (1-5) extraemos dos indicadores continuos:

      sin_salud   % de poblacion SIN derechohabiencia a servicios de salud.
                  Es la variable clave del proyecto. El grado ordinal esta
                  calibrado a escala nacional y dentro de la CDMX casi no
                  discrimina: 948 AGEB salen 'Muy bajo' y 1,234 'Bajo', o sea
                  90% de la ciudad en dos niveles. Este porcentaje, en cambio,
                  es continuo y mide exactamente el mecanismo: quien no tiene
                  IMSS, ISSSTE ni seguro privado es quien termina en el
                  consultorio de la farmacia porque no tiene a donde mas ir.

      sin_internet  % de viviendas sin internet. No entra en el peso; queda
                  disponible para diferenciar el escenario de digitalizacion
                  por zona en vez de aplicar un factor plano.
    """
    df = pd.read_excel(ruta, dtype=str, header=3)
    col_clave = next(c for c in df.columns if "Clave de la AGEB" in str(c))
    col_grado = next(c for c in df.columns if "Grado de Rezago" in str(c))

    # los nombres reales de los indicadores viven en la primera fila de datos
    sub = df.iloc[0]
    def col_indicador(fragmento):
        for c, v in zip(df.columns, sub):
            if isinstance(v, str) and fragmento.lower() in v.lower():
                return c
        return None
    col_salud = col_indicador("sin derechohabiencia")
    col_net = col_indicador("no disponen de internet")

    df = df.dropna(subset=[col_clave, col_grado])
    df["CVEGEO"] = df[col_clave].astype(str).str.strip()
    df = df[df["CVEGEO"].str[:2] == cfg.ENTIDAD]

    out = pd.DataFrame({
        "CVEGEO": df["CVEGEO"],
        "grs_texto": df[col_grado].astype(str).str.strip(),
    })
    out["grs"] = out["grs_texto"].map(GRADOS)
    out["sin_salud"] = a_num(df[col_salud]) if col_salud else np.nan
    out["sin_internet"] = a_num(df[col_net]) if col_net else np.nan
    return out.drop_duplicates("CVEGEO").reset_index(drop=True)
