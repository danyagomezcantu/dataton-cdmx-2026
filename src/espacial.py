"""
Cruces espaciales: de puntos del DENUE a metricas por AGEB.

Dos medidas distintas, y la diferencia entre ambas es el argumento
metodologico del proyecto:

  CONTENCION  - cuantos establecimientos caen DENTRO del poligono.
                Es la version ingenua. Una AGEB con cero farmacias que tiene
                tres cruzando la avenida aparece como desierto, y no lo es.

  COBERTURA   - cuanta oferta es ALCANZABLE desde la AGEB, con un peso que
                decae con la distancia. Es como funciona la ciudad de verdad.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg


def contar_por_ageb(agebs, puntos, nombre: str) -> pd.DataFrame:
    """Conteo por contencion (punto dentro de poligono)."""
    import geopandas as gpd

    if len(puntos) == 0:
        return pd.DataFrame({"CVEGEO": agebs.CVEGEO.values, nombre: 0})
    j = gpd.sjoin(puntos[["geometry"]], agebs[["CVEGEO", "geometry"]],
                  how="inner", predicate="within")
    c = j.groupby("CVEGEO").size().rename(nombre)
    out = agebs[["CVEGEO"]].merge(c, on="CVEGEO", how="left")
    out[nombre] = out[nombre].fillna(0).astype(int)
    return out


def accesibilidad(agebs, puntos, nombre: str, ancho: float = None,
                  radio: float = None) -> pd.DataFrame:
    """
    Accesibilidad gaussiana desde el centroide de cada AGEB:

        A_i = suma_j  exp( -d_ij^2 / (2 h^2) )

    donde d_ij es la distancia en metros al establecimiento j y h el ancho de
    banda. Un establecimiento a 200 m aporta casi 1; a 800 m aporta ~0.61;
    a 2 km aporta ~0.04.

    Esto ataca de frente la consideracion del reto de que la ausencia de datos
    no equivale a ausencia de demanda.
    """
    from scipy.spatial import cKDTree

    h = ancho or cfg.ANCHO_BANDA_M
    r = radio or cfg.RADIO_CORTE_M

    cent = agebs.geometry.centroid
    xy_a = np.c_[cent.x.values, cent.y.values]

    if len(puntos) == 0:
        return pd.DataFrame({"CVEGEO": agebs.CVEGEO.values, nombre: 0.0})

    xy_p = np.c_[puntos.geometry.x.values, puntos.geometry.y.values]
    arbol = cKDTree(xy_p)
    acc = np.zeros(len(xy_a))
    for i, idx in enumerate(arbol.query_ball_point(xy_a, r=r)):
        if idx:
            d = np.linalg.norm(xy_p[idx] - xy_a[i], axis=1)
            acc[i] = float(np.exp(-(d ** 2) / (2 * h ** 2)).sum())

    return pd.DataFrame({"CVEGEO": agebs.CVEGEO.values, nombre: acc})


def validar_ageb_declarada(agebs, puntos) -> dict:
    """
    Verificacion cruzada gratuita.

    El DENUE trae su propia columna 'ageb': el INEGI ya declaro a que AGEB
    pertenece cada establecimiento. La comparamos contra el resultado del
    cruce espacial. Si empatan en la gran mayoria, el cruce esta bien hecho.
    Si no, hay problema de proyeccion o de annada del Marco Geoestadistico.
    """
    import geopandas as gpd

    cols = [c for c in ("cve_mun", "cve_loc", "ageb") if c in puntos.columns]
    if len(cols) < 3:
        return {"disponible": False,
                "motivo": "el corte no trae cve_mun / cve_loc / ageb"}

    p = puntos.copy()
    p["_declarada"] = (
        cfg.ENTIDAD
        + p["cve_mun"].astype(str).str.strip().str.zfill(3)
        + p["cve_loc"].astype(str).str.strip().str.zfill(4)
        + p["ageb"].astype(str).str.strip().str.zfill(4))

    j = gpd.sjoin(p[["_declarada", "geometry"]], agebs[["CVEGEO", "geometry"]],
                  how="left", predicate="within")
    j = j[j["CVEGEO"].notna()]
    if len(j) == 0:
        return {"disponible": True, "n_comparados": 0, "coincidencia": None}

    coincide = (j["_declarada"] == j["CVEGEO"]).mean()
    return {
        "disponible": True,
        "n_comparados": int(len(j)),
        "n_fuera_de_poligono": int(len(p) - len(j)),
        "coincidencia": round(float(coincide), 4),
    }


def simplificar_para_web(agebs, tolerancia_m: float = 40.0, decimales: int = 5):
    """
    Geometria ligera para el visor: simplifica en metros y luego reproyecta
    a lat/lon. Sin esto, 2,431 poligonos a resolucion completa hacen un
    archivo de decenas de MB que el navegador tarda en dibujar.
    """
    g = agebs.copy()
    g["geometry"] = g.geometry.simplify(tolerancia_m, preserve_topology=True)
    g = g.to_crs(cfg.CRS_GEO)
    g["geometry"] = g.geometry.set_precision(10 ** (-decimales))
    return g
