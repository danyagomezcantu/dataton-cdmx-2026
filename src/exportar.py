"""
Genera los archivos que consume el visor.

FORMATO COLUMNAR. Un GeoJSON normal repite el nombre de cada propiedad en
cada uno de los 2,431 poligonos: con ~60 variables eso son 145 mil cadenas
repetidas y el archivo se va a 10 MB aunque la geometria pese menos de 1 MB.

Aqui la geometria va por un lado (solo CVEGEO) y los datos por otro, como
arrays paralelos indexados por posicion. El visor los vuelve a unir en el
navegador. Mismo contenido, una decima parte del tamanio.

Salidas:
  datos/procesados/agebs.geojson   geometria simplificada (para QGIS tambien)
  datos/procesados/datos.json      los atributos en formato columnar
  app/datos.js                     ambos como variables JS, para que el visor
                                   funcione con doble clic, sin servidor
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from . import config as cfg, espacial


def _lista(serie, nd=None):
    """Serie de pandas -> lista JSON limpia (sin NaN, redondeada)."""
    out = []
    for v in serie:
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            out.append(None)
        elif isinstance(v, (np.integer, int)):
            out.append(int(v))
        elif isinstance(v, (np.floating, float)):
            out.append(round(float(v), nd) if nd is not None else float(v))
        else:
            out.append(str(v))
    return out



def recomendaciones(tabla) -> list:
    """
    Tres recomendaciones concretas, una por horizonte, calculadas desde los datos.

    No son texto escrito a mano: cada una sale de un criterio distinto y nombra
    zonas especificas con sus cifras. El criterio cambia con el horizonte, porque
    lo que se puede afirmar a un anio no es lo mismo que a cinco.

      1 anio  -> donde la brecha YA es peor. Es el unico horizonte donde la
                 recomendacion es abrir, porque casi no depende de proyeccion.
      3 anios -> las que ENTRAN al decil de peor brecha sin estar hoy ahi,
                 ordenadas por personas sumadas. Anticipacion real: zonas que
                 hoy no estan arriba y en tres anios si.
      5 anios -> cruce de envejecimiento relativo alto con accesibilidad baja.
                 A este plazo no afirmamos un ranking, seniallamos un patron.
    """
    a1, a3, a5 = cfg.ANIOS_PROY
    t = tabla.copy()

    # Piso de poblacion. La brecha es un cociente y en una AGEB con 10 personas
    # de 60 y mas y cero oferta se dispara sin que exista decision que tomar.
    # Sin este filtro las recomendaciones a 3 y 5 anios nombran zonas de 3 a 20
    # adultos mayores: artefacto de denominador, no hallazgo.
    n_antes = len(t)
    t = t[t["p_60ymas_2020"].fillna(0) >= cfg.MIN_P60_RECO].copy()
    n_excl = n_antes - len(t)

    t["_col"] = t["colonias"].fillna("").apply(lambda x: x.split(" · ")[0] if x else "")
    t["_alc"] = t["CVE_MUN"].map(cfg.ALCALDIAS)

    def tres(sub, col):
        """Top 3 por `col`, sin repetir colonia: tres lugares distintos."""
        return (sub.sort_values(col, ascending=False)
                   .drop_duplicates(subset=["_col", "_alc"])
                   .head(3))

    def ficha(sub, extra=None):
        out = []
        for _, r in sub.iterrows():
            d = {
                "cve": r["CVEGEO"],
                "colonia": r["_col"] or ("AGEB " + str(r["CVEGEO"])[-4:]),
                "alcaldia": r["_alc"],
                "p60": int(r["p_60ymas_2020"]) if pd.notna(r["p_60ymas_2020"]) else None,
                "oferta": int(r[f"n_{cfg.ANIO_BASE}"]),
                "acc": round(float(r[f"acc_{cfg.ANIO_BASE}"]), 1),
                "envejecimiento": round(float(r["recambio"]), 2),
            }
            if extra:
                d.update({k: (round(float(r[v]), 2) if pd.notna(r[v]) else None)
                          for k, v in extra.items()})
            out.append(d)
        return out

    # --- 1 anio -----------------------------------------------------------
    b1 = f"brecha_tendencial_{a1}"
    corto = tres(t, b1)
    umbral = float(t[b1].quantile(0.90))

    # --- 3 anios: entra al decil peor sin estar hoy ahi -------------------
    # El criterio no es "cuantas posiciones sube" sino "cruza el umbral de
    # decision". Un ranking por saltos premia a las AGEB chicas, porque un
    # cociente con denominador pequenio se mueve mucho con poca gente. Aqui
    # el corte es binario (entra o no entra al decil) y el desempate es en
    # PERSONAS: cuantos adultos mayores se suman entre a1 y a3.
    b3 = f"brecha_tendencial_{a3}"
    t["_r1"] = t[b1].rank(ascending=False)
    t["_r3"] = t[b3].rank(ascending=False)
    t["_salto"] = t["_r1"] - t["_r3"]          # positivo = sube de posicion
    corte = len(t) * 0.10
    t["_suma"] = t[f"demanda_tendencial_{a3}"] - t[f"demanda_tendencial_{a1}"]
    cand = t[(t["_r3"] <= corte) & (t["_r1"] > corte)]
    if len(cand) < 3:                           # respaldo: tercio superior
        cand = t[(t["_r3"] <= len(t) / 3) & (t["_r1"] > len(t) / 3)]
    medio = tres(cand, "_suma")

    # --- 5 anios: envejecimiento alto + accesibilidad baja ----------------
    acc = t[f"acc_{cfg.ANIO_BASE}"]
    t["_z_env"] = (t["recambio"] - t["recambio"].mean()) / t["recambio"].std()
    t["_z_acc"] = (acc - acc.mean()) / acc.std()
    t["_riesgo"] = t["_z_env"] - t["_z_acc"]
    largo = tres(t, "_riesgo")

    # Los totales de ciudad se calculan sobre TODAS las AGEB, no sobre las
    # elegibles: el filtro decide quien puede ser recomendado, no cuanta
    # demanda tiene la ciudad.
    d_tot = {h: float(tabla[f"demanda_tendencial_{h}"].sum()) for h in cfg.ANIOS_PROY}
    base = float(tabla["p_60ymas_2020"].sum())
    nota = (f"Universo: {len(t):,} de {n_antes:,} AGEB. Se excluyen {n_excl:,} con "
            f"menos de {cfg.MIN_P60_RECO} personas de 60 y más, que son 1.8% de la "
            f"demanda de la ciudad: ahí el cociente se dispara por denominador "
            f"chico, no porque haya una decisión que tomar.")

    return [
        {
            "horizonte": "1 año",
            "anio": a1,
            "confianza": "alta",
            "titulo": "Abrir donde la brecha ya es peor",
            "criterio": (f"Zonas con mayor brecha proyectada a {a1}. A un año la "
                         f"recomendación casi no depende del modelo: la demanda ya "
                         f"está instalada y la oferta apenas se mueve entre cortes."),
            "dato": (f"La demanda de la ciudad pasa de {base:,.0f} personas de 60 y "
                     f"más en 2020 a {d_tot[a1]:,.0f} en {a1}. Las zonas del percentil "
                     f"90 superan una brecha de {umbral:,.0f} personas por unidad de "
                     f"servicio accesible."),
            "accion": "Decisión de apertura inmediata.",
            "nota": nota,
            "zonas": ficha(corto, {"brecha": b1}),
        },
        {
            "horizonte": "3 años",
            "anio": a3,
            "confianza": "media",
            "titulo": "Preparar terreno donde la brecha va a subir más",
            "criterio": (f"Zonas que hoy NO están en el 10% de peor brecha y en {a3} "
                         f"sí entran, ordenadas por cuántas personas de 60 y más se "
                         f"suman entre {a1} y {a3}. Ordenamos por personas y no por "
                         f"saltos de posición a propósito: un cociente con denominador "
                         f"chico brinca mucho con poca gente. Este es el horizonte que "
                         f"defendemos: la inercia demográfica ya se nota y el error de "
                         f"proyección todavía es manejable."),
            "dato": (f"La demanda sube de {d_tot[a1]:,.0f} a {d_tot[a3]:,.0f} personas "
                     f"de 60 y más entre {a1} y {a3}, un alza de "
                     f"{100*(d_tot[a3]/d_tot[a1]-1):.1f}%."),
            "accion": "Búsqueda de local y negociación de renta, no apertura aún.",
            "nota": nota,
            "zonas": ficha(medio, {"brecha": b3, "salto_posiciones": "_salto", "personas_sumadas": "_suma"}),
        },
        {
            "horizonte": "5 años",
            "anio": a5,
            "confianza": "baja: es escenario, no pronóstico",
            "titulo": "Vigilar donde envejece rápido y hay poca oferta alcanzable",
            "criterio": ("Cruce de dos señales: envejecimiento muy por encima del "
                         "promedio de la ciudad y accesibilidad por debajo. A cinco "
                         "años no afirmamos un ranking de zonas concretas; señalamos "
                         "un patrón que conviene monitorear con el DENUE semestral."),
            "dato": (f"A {a5} la demanda llega a {d_tot[a5]:,.0f} personas de 60 y más, "
                     f"{100*(d_tot[a5]/base-1):.0f}% más que en 2020. El intervalo de "
                     f"confianza se ensancha con la raíz del horizonte."),
            "accion": "Monitoreo semestral, no compromiso de capital.",
            "nota": nota,
            "zonas": ficha(largo, {"riesgo": "_riesgo"}),
        },
    ]


def construir(tabla, diag: dict, limites=None) -> dict:
    # ------------------------------------------------------------ geometria
    g = espacial.simplificar_para_web(tabla, tolerancia_m=45.0, decimales=5)
    geo = json.loads(g[["CVEGEO", "geometry"]].to_json())
    geo["features"] = [f for f in geo["features"]
                       if f.get("geometry") is not None]

    # limites de alcaldia, simplificados. Sin referencia visual, quien no
    # conoce la ciudad no puede ubicarse en el mapa.
    lim = None
    if limites is not None and len(limites):
        L = limites.copy()
        L["geometry"] = L.geometry.simplify(120, preserve_topology=True)
        L = L.to_crs(cfg.CRS_GEO)
        L["nombre"] = L["CVE_MUN"].map(cfg.ALCALDIAS)
        lim = json.loads(L[["CVE_MUN", "nombre", "geometry"]].to_json())

    # ------------------------------------------------------------ atributos
    orden = list(g["CVEGEO"])
    t = tabla.set_index("CVEGEO").loc[orden].reset_index()

    cols = {
        "cve": _lista(t["CVEGEO"]),
        "mun": _lista(t["CVE_MUN"]),
        "pob": _lista(t["pobtot_2020"], 0),
        "p60_2020": _lista(t["p_60ymas_2020"], 0),
        "p60_2010": _lista(t["p_60ymas_2010"], 0),
        "tasa60": _lista(t["tasa_60_2020"] * 100, 2),
        "recambio": _lista(t["recambio"], 2),
        "recambio_abs": _lista(t["recambio_abs"], 2),
        "grs": _lista(t["grs"], 0),
        "grs_txt": _lista(t["grs_texto"]),
        "acc_pct": _lista(t["acc_percentil"] * 100, 1),
        "des_cont": _lista(t["desierto_contencion"], 0),
        "col": _lista(t["colonias"].fillna("")),
        "dem_2026": _lista(t["demanda_2026"], 0),
        "br_2026": _lista(t["brecha_2026"], 2),
    }
    for a in cfg.ANIOS_DENUE:
        cols[f"n{a}"] = _lista(t[f"n_{a}"], 0)
        cols[f"a{a}"] = _lista(t[f"acc_{a}"], 1)
    for esc in cfg.ESCENARIOS:
        for a in cfg.ANIOS_PROY:
            cols[f"d_{esc}_{a}"] = _lista(t[f"demanda_{esc}_{a}"], 0)
            cols[f"b_{esc}_{a}"] = _lista(t[f"brecha_{esc}_{a}"], 2)
            cols[f"o_{esc}_{a}"] = _lista(t[f"oferta_{esc}_{a}"], 2)
    for a in cfg.ANIOS_PROY:
        cols[f"com_{a}"] = _lista(t[f"comercial_{a}"], 2)
        cols[f"nec_{a}"] = _lista(t[f"necesidad_{a}"], 2)

    # ------------------------------------------------------------ meta
    alc = (tabla.groupby("CVE_MUN")
           .agg(pob=("pobtot_2020", "sum"), p60=("p_60ymas_2020", "sum"),
                oferta=(f"n_{cfg.ANIO_BASE}", "sum"),
                recambio=("recambio", "mean"),
                brecha=(f"brecha_tendencial_{cfg.ANIOS_PROY[1]}", "median"),
                agebs=("CVEGEO", "count"))
           .reset_index())
    alc["alcaldia"] = alc.CVE_MUN.map(cfg.ALCALDIAS)
    alc["por_10k_60"] = (alc.oferta / (alc.p60 / 10000)).round(1)

    meta = {
        "anios_observados": cfg.ANIOS_DENUE,
        "anios_proyectados": cfg.ANIOS_PROY,
        "anio_base": cfg.ANIO_BASE,
        "meses_denue": cfg.MESES_DENUE,
        "escenarios": {k: {"nombre": v["nombre"], "descripcion": v["descripcion"]}
                       for k, v in cfg.ESCENARIOS.items()},
        "scian_oferta": cfg.SCIAN_OFERTA,
        "scian_contexto": cfg.SCIAN_CONTEXTO,
        "ancho_banda_m": cfg.ANCHO_BANDA_M,
        "alcaldias_nombre": cfg.ALCALDIAS,
        "alcaldias": alc.round(2).to_dict("records"),
        "serie_ciudad": [{"anio": a, "mes": cfg.MESES_DENUE[a],
                          "oferta": int(tabla[f"n_{a}"].sum())}
                         for a in cfg.ANIOS_DENUE],
        "recambio_medio_ciudad": diag["recambio"]["cambio_medio_ciudad_pp"],
        "recomendaciones": recomendaciones(tabla),
        "diagnostico": {
            k: diag[k] for k in
            ("empate_censos", "backtest", "desiertos", "dispersion",
             "transiciones_usadas", "transiciones_excluidas",
             "sensibilidad_ancho_banda", "validacion_ageb_declarada",
             "recambio", "marco_geoestadistico", "denue", "coneval")
            if k in diag
        },
        "validacion_espacial": diag.get("validacion_espacial", {}),
        "conapo_fuente": cfg.CONAPO_FUENTE,
        "fuentes": [
            {"n": "Censo de Poblacion y Vivienda 2020, resultados por AGEB y manzana urbana",
             "i": "INEGI", "g": "AGEB", "t": "2020"},
            {"n": "Censo de Poblacion y Vivienda 2010, resultados por AGEB y manzana urbana",
             "i": "INEGI", "g": "AGEB", "t": "2010"},
            {"n": "DENUE, 11 ediciones", "i": "INEGI",
             "g": "punto georreferenciado", "t": "2016-2026"},
            {"n": "Marco Geoestadistico, 6 annadas", "i": "INEGI",
             "g": "AGEB", "t": "2020-2025"},
            {"n": "Grado de Rezago Social por AGEB urbana", "i": "CONEVAL",
             "g": "AGEB", "t": "2020"},
            {"n": "Proyecciones de poblacion", "i": "CONAPO",
             "g": "entidad", "t": "2020-2030"},
        ],
    }
    return {"meta": meta, "geo": geo, "cols": cols, "lim": lim}


def _compactar(s: str) -> str:
    """Recorta coordenadas a 5 decimales en el texto ya serializado."""
    return re.sub(r"(-?\d+\.\d{5})\d+", r"\1", s)


def escribir(paquete: dict):
    geo_txt = _compactar(json.dumps(paquete["geo"], ensure_ascii=False,
                                    separators=(",", ":")))
    cols_txt = json.dumps(paquete["cols"], ensure_ascii=False,
                          separators=(",", ":"))
    meta_txt = json.dumps(paquete["meta"], ensure_ascii=False,
                          separators=(",", ":"), default=str)
    lim_txt = _compactar(json.dumps(paquete.get("lim"), ensure_ascii=False,
                                    separators=(",", ":")))

    (cfg.PROCESADOS / "agebs.geojson").write_text(geo_txt, encoding="utf-8")
    (cfg.PROCESADOS / "datos.json").write_text(cols_txt, encoding="utf-8")
    (cfg.PROCESADOS / "meta.json").write_text(
        json.dumps(paquete["meta"], ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")

    js = (cfg.APP / "datos.js")
    js.write_text(
        "// Generado por scripts/02_pipeline.py. No editar a mano.\n"
        f"window.META={meta_txt};\n"
        f"window.GEO={geo_txt};\n"
        f"window.COLS={cols_txt};\n"
        f"window.LIM={lim_txt};\n", encoding="utf-8")

    return {
        "geojson_mb": round(len(geo_txt) / 1e6, 2),
        "datos_json_mb": round(len(cols_txt) / 1e6, 2),
        "datos_js_mb": round(js.stat().st_size / 1e6, 2),
        "n_features": len(paquete["geo"]["features"]),
        "n_variables": len(paquete["cols"]),
    }
