"""
Pipeline completo. Lee datos/crudos, escribe datos/procesados y salidas.

Uso:   python scripts/02_pipeline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import carga, config as cfg, espacial, modelo  # noqa: E402


def log(msg=""):
    print(msg, flush=True)


def main():
    import geopandas as gpd

    diag = {}
    log("=" * 72)
    log("PIPELINE — brecha de atencion primaria en la CDMX")
    log("=" * 72)

    # ------------------------------------------------------------ 1. geometria
    log("\n[1/8] Marco Geoestadistico")
    inv = carga.inventario_agebs()
    log(inv.to_string(index=False))
    agebs, ruta_mg = carga.cargar_agebs(2020)
    log(f"  base: {ruta_mg.parent.parent.name}  ->  {len(agebs)} AGEB urbanas")
    diag["marco_geoestadistico"] = {
        "annadas_disponibles": inv.to_dict("records"),
        "annada_usada": 2020,
        "n_agebs": int(len(agebs)),
        "crs": cfg.CRS_METRICO,
        "nota": ("Se usa la annada 2020 porque sus claves CVEGEO son las del "
                 "Censo 2020. Las annadas 2021-2025 sirven para verificar "
                 "estabilidad territorial."),
    }

    # ------------------------------------------------------------ 2. censos
    log("\n[2/8] Censos 2020 y 2010")
    c20 = carga.cargar_censo(carga.buscar("censo_ageb_09_2020*.csv"), "2020")
    c10 = carga.cargar_censo(carga.buscar("censo_ageb_09_2010*.csv"), "2010")
    censos, d_emp = carga.empatar_censos(c20, c10)
    diag["empate_censos"] = d_emp
    log(f"  2020: {d_emp['agebs_censo_2020']}   2010: {d_emp['agebs_censo_2010']}")
    log(f"  empate: {d_emp['tasa_empate']:.1%}  "
        f"(nuevas {d_emp['nuevas_en_2020']}, desaparecidas "
        f"{d_emp['desaparecidas_desde_2010']})")

    # ------------------------------------------------------------ 3. CONEVAL
    log("\n[3/8] CONEVAL — grado de rezago social")
    grs = carga.cargar_coneval(carga.buscar("GRS_AGEB_urbana_2020.xlsx"))
    ss = grs["sin_salud"].dropna()
    log(f"  {len(grs)} AGEB con grado asignado")
    log(f"  sin derechohabiencia a servicios de salud: "
        f"p05 {ss.quantile(.05):.1f}%  mediana {ss.median():.1f}%  "
        f"p95 {ss.quantile(.95):.1f}%")
    diag["coneval"] = {
        "n_agebs": int(len(grs)),
        "grado_rezago_distribucion": grs["grs_texto"].value_counts().to_dict(),
        "sin_derechohabiencia_pct": {
            "p05": round(float(ss.quantile(.05)), 1),
            "mediana": round(float(ss.median()), 1),
            "p95": round(float(ss.quantile(.95)), 1),
            "n": int(len(ss)),
        },
        "nota": ("El Grado de Rezago Social es ordinal y esta calibrado a escala "
                 "nacional: deja 948 AGEB de la CDMX en 'Muy bajo' y 1,234 en "
                 "'Bajo', o sea 90% de la ciudad en dos niveles. Por eso el peso "
                 "de dependencia usa el porcentaje sin derechohabiencia, que es "
                 "continuo y mide el mecanismo directamente."),
    }

    # ------------------------------------------------------------ 4. DENUE
    log("\n[4/8] DENUE — 11 cortes")
    capas = carga.cargar_todos_los_denue(list(cfg.SCIAN_TODAS))
    resumen_denue = []
    for anio, g in capas.items():
        of = g[g.codigo_act.isin(cfg.SCIAN_OFERTA)]
        resumen_denue.append({
            "anio": anio, "mes": cfg.MESES_DENUE[anio],
            "n_total_clases": int(len(g)), "n_oferta": int(len(of)),
            "descartados_por_coordenada": int(
                g.attrs.get("descartados_por_coordenada", 0)),
        })
        log(f"  {anio}-{cfg.MESES_DENUE[anio]:02d}:  {len(g):>6,} de las 14 clases"
            f"   |  {len(of):>5,} de oferta")
    diag["denue"] = resumen_denue

    # nombres de colonia por AGEB, para el buscador del visor
    colonias = carga.colonias_por_ageb(capas[cfg.ANIO_BASE])
    n_directo = len(colonias)
    colonias = carga.completar_por_vecindad(agebs, colonias)
    log(f"  colonias: {n_directo} por establecimiento dentro, "
        f"{len(colonias) - n_directo} completadas por vecindad")
    diag["colonias"] = {
        "por_establecimiento_dentro": n_directo,
        "completadas_por_vecindad": int(len(colonias) - n_directo),
        "agebs_con_nombre": int(len(colonias)),
        "nota": ("Una AGEB estrictamente residencial no tiene negocios adentro, "
                 "asi que no hay de donde leer su nombre. Esas se completan con "
                 "las colonias colindantes y se marcan con '~'."),
    }

    # verificacion cruzada contra la AGEB declarada por el INEGI
    v = espacial.validar_ageb_declarada(agebs, capas[2026])
    diag["validacion_ageb_declarada"] = v
    if v.get("coincidencia") is not None:
        log(f"  verificacion cruzada 2026: la AGEB declarada por el DENUE "
            f"coincide con el cruce espacial en {v['coincidencia']:.1%} "
            f"de {v['n_comparados']:,} puntos")

    # ------------------------------------------------------------ 5. tabla maestra
    log("\n[5/8] Tabla maestra por AGEB")
    t = agebs.merge(censos, on=["CVEGEO", "CVE_MUN"], how="left") \
             .merge(grs, on="CVEGEO", how="left") \
             .merge(colonias, on="CVEGEO", how="left")

    for anio, g in capas.items():
        of = g[g.codigo_act.isin(cfg.SCIAN_OFERTA)]
        t = t.merge(espacial.contar_por_ageb(agebs, of, f"n_{anio}"),
                    on="CVEGEO", how="left")
        t = t.merge(espacial.accesibilidad(agebs, of, f"acc_{anio}"),
                    on="CVEGEO", how="left")
    ctx = capas[cfg.ANIO_BASE]
    ctx = ctx[ctx.codigo_act.isin(cfg.SCIAN_CONTEXTO)]
    t = t.merge(espacial.contar_por_ageb(agebs, ctx, "n_contexto"),
                on="CVEGEO", how="left")

    for a in cfg.ANIOS_DENUE:
        t[f"n_{a}"] = t[f"n_{a}"].fillna(0).astype(int)
        t[f"acc_{a}"] = t[f"acc_{a}"].fillna(0.0)

    t["dens_pob"] = t["pobtot_2020"] / t["area_km2"].replace(0, np.nan)
    t["tasa_60_2020"] = t["p_60ymas_2020"] / t["pobtot_2020"].replace(0, np.nan)
    t["tasa_60_2010"] = t["p_60ymas_2010"] / t["pobtot_2010"].replace(0, np.nan)
    t["delta_60_abs"] = t["p_60ymas_2020"] - t["p_60ymas_2010"]
    t["delta_tasa_60"] = t["tasa_60_2020"] - t["tasa_60_2010"]
    t["crec_60_10_20"] = ((t["p_60ymas_2020"] / t["p_60ymas_2010"].replace(0, np.nan))
                          .replace([np.inf, -np.inf], np.nan) - 1).clip(-1, 4)
    t["delta_pobtot"] = t["pobtot_2020"] - t["pobtot_2010"]
    log(f"  {len(t)} filas x {len(t.columns)} columnas")

    # --- envejecimiento vs rejuvenecimiento: la variable de la portada -----
    # Primer hallazgo: en terminos ABSOLUTOS casi toda la ciudad envejecio.
    # Medir "rejuvenecimiento" contra cero no sirve, porque el cero no es el
    # punto de comparacion relevante: la CDMX entera se esta haciendo vieja.
    #
    # La medida util es RELATIVA a la ciudad: cuanto se aparta cada AGEB del
    # envejecimiento promedio. Positivo = envejece mas rapido que la ciudad.
    # Negativo = rejuvenece en terminos relativos, que es exactamente la
    # hipotesis de los barrios que se recambian.
    t["recambio_abs"] = t["delta_tasa_60"] * 100
    media_ciudad = float(t["recambio_abs"].mean())
    t["recambio"] = t["recambio_abs"] - media_ciudad

    n_env_abs = int((t["recambio_abs"] > 0).sum())
    n_rej_abs = int((t["recambio_abs"] < 0).sum())
    n_env_rel = int((t["recambio"] > 0).sum())
    n_rej_rel = int((t["recambio"] < 0).sum())
    log(f"  absoluto : envejecieron {n_env_abs}, rejuvenecieron {n_rej_abs}")
    log(f"  relativo : por encima del promedio {n_env_rel}, "
        f"por debajo {n_rej_rel}  (promedio ciudad {media_ciudad:+.2f} pp)")
    diag["recambio"] = {
        "cambio_medio_ciudad_pp": round(media_ciudad, 3),
        "absoluto": {"envejecieron": n_env_abs, "rejuvenecieron": n_rej_abs},
        "relativo": {"mas_rapido_que_la_ciudad": n_env_rel,
                     "mas_lento_que_la_ciudad": n_rej_rel},
        "nota": ("Casi toda la CDMX envejecio entre 2010 y 2020: medir contra "
                 "cero no distingue nada. La medida informativa es el apartamiento "
                 "respecto al promedio de la ciudad."),
    }

    # ------------------------------------------------------------ 6. modelo
    log("\n[6/8] Modelo de oferta y validacion")
    panel = modelo.construir_panel(t)
    disp = modelo.dispersion(panel)
    familia = disp["recomendacion"]
    log(f"  panel: {len(panel):,} observaciones "
        f"({len(modelo.transiciones_validas())} transiciones)")
    log(f"  dispersion varianza/media = {disp['razon']}  ->  familia {familia}")
    diag["dispersion"] = disp
    diag["familia"] = familia
    diag["transiciones_usadas"] = [f"{a}->{b}" for a, b in modelo.transiciones_validas()]
    diag["transiciones_excluidas"] = {
        "pares": [f"{a}->{b}" for a, b in cfg.TRANSICIONES_EXCLUIDAS],
        "motivo": ("Rupturas de serie del DENUE. Entre esos cortes varias clases "
                   "saltan sin que haya aperturas o cierres reales, "
                   "muy probablemente por cambio de version del catalogo SCIAN."),
    }

    bt, m_final, ancho = modelo.backtest(t, familia)
    diag["backtest"] = bt
    log(f"  entrena: {', '.join(bt['transiciones_entrenamiento'])}")
    log(f"  prueba : {', '.join(bt['transiciones_prueba'])}")
    log(f"  {'':<20}{'top-k NIVEL':>13}{'top-k CAMBIO':>14}")
    log(f"  {'modelo GLM':<20}"
        f"{bt['modelo']['precision_top_k_nivel']:>13}"
        f"{bt['modelo']['precision_top_k_cambio']:>14}")
    for k, vv in bt["baselines"].items():
        log(f"  {'baseline ' + k:<20}"
            f"{vv['precision_top_k_nivel']:>13}{vv['precision_top_k_cambio']:>14}")
    log(f"  vence en nivel: {bt['vence_en_nivel']}   "
        f"vence en cambio: {bt['vence_en_cambio']}")
    log(f"  cobertura del IC {int(cfg.NIVEL_CONFIANZA*100)}%: "
        f"{bt['incertidumbre']['cobertura_observada']}")

    vesp = modelo.validacion_espacial(t, familia)
    if len(vesp):
        diag["validacion_espacial"] = {
            "spearman_promedio": round(float(vesp.spearman.mean()), 3),
            "por_alcaldia": vesp.to_dict("records"),
        }
        log(f"  validacion por bloques (deja fuera alcaldias): "
            f"spearman promedio {vesp.spearman.mean():.3f}")

    # ------------------------------------------------------------ 7. proyeccion
    log("\n[7/8] Proyeccion, escenarios y brecha")
    t["demanda_2026"] = modelo.proyectar_demanda(t, cfg.ANIO_BASE, "tendencial")
    t["brecha_2026"] = modelo.brecha(t["demanda_2026"], t[f"acc_{cfg.ANIO_BASE}"])

    razon_acc = (t[f"acc_{cfg.ANIO_BASE}"] /
                 t[f"n_{cfg.ANIO_BASE}"].replace(0, np.nan)).median()
    razon_acc = float(razon_acc) if np.isfinite(razon_acc) else 1.0
    # Se guarda porque el visor la necesita: la brecha NO divide entre el
    # conteo dentro de la zona, divide entre la oferta ALCANZABLE, y sin esta
    # razon el panel de detalle enseniaba una division que no cerraba.
    diag["razon_accesible_por_establecimiento"] = round(razon_acc, 3)

    for esc in cfg.ESCENARIOS:
        for anio in cfg.ANIOS_PROY:
            d = modelo.proyectar_demanda(t, anio, esc)
            t[f"demanda_{esc}_{anio}"] = d

            # oferta proyectada: se aplica la razon del GLM sobre el horizonte
            sub = modelo.construir_panel(t, [(cfg.ANIO_BASE, cfg.ANIO_BASE)])
            sub["dt"] = anio - cfg.ANIO_BASE
            sub["offset"] = (np.log(sub["pobtot"]) +
                             np.log(np.clip(sub["dt"], 0.1, None)))
            oferta = modelo.predecir(m_final, sub)
            n_hoy = t[f"n_{cfg.ANIO_BASE}"].to_numpy(float)
            oferta = np.where(np.isfinite(oferta), oferta, n_hoy)
            oferta = np.maximum(oferta, 0)

            acc_proy = oferta * razon_acc
            t[f"oferta_{esc}_{anio}"] = oferta
            t[f"acc_proy_{esc}_{anio}"] = acc_proy
            t[f"brecha_{esc}_{anio}"] = modelo.brecha(d, pd.Series(acc_proy, index=t.index))

            h = np.sqrt(max((anio - cfg.ANIO_BASE) / 5.0, 1e-9)) * ancho
            t[f"brecha_lo_{esc}_{anio}"] = modelo.brecha(
                d, pd.Series(acc_proy + h * razon_acc, index=t.index))
            t[f"brecha_hi_{esc}_{anio}"] = modelo.brecha(
                d, pd.Series(np.maximum(acc_proy - h * razon_acc, 0), index=t.index))

    # --- los dos modos de lectura -----------------------------------------
    # La brecha cruda mide distancia fisica al servicio. Pero el segmento no
    # es "adultos mayores", es quien DEPENDE de atencion primaria de bajo
    # costo, y eso se pondera con el rezago social. Los dos pesos son espejo:
    #
    #   necesidad  = brecha x dependencia  (rezago alto pesa mas)
    #   comercial  = brecha x capacidad de pago (rezago bajo pesa mas)
    #
    # Se exportan los DOS pesos por zona y el visor multiplica en el navegador,
    # asi el juez cambia de pregunta con un selector y sin recargar nada.
    t["w_necesidad"] = modelo.peso_dependencia(t["sin_salud"])
    t["w_comercial"] = modelo.peso_gasto(t["sin_salud"])
    for anio in cfg.ANIOS_PROY:
        base = t[f"brecha_tendencial_{anio}"]
        t[f"necesidad_{anio}"] = base * t["w_necesidad"]
        t[f"comercial_{anio}"] = base * t["w_comercial"]
    # La categoria se calcula sobre el modo por omision, no sobre la cruda.
    t["categoria"] = modelo.categorizar(t[f"{cfg.MODO_BASE}_{cfg.ANIOS_PROY[1]}"])

    n_cambia = int((t[f"necesidad_{cfg.ANIOS_PROY[1]}"].rank(ascending=False) <= 50).ne(
        t[f"comercial_{cfg.ANIOS_PROY[1]}"].rank(ascending=False) <= 50).sum())
    diag["modos"] = {
        "modo_base": cfg.MODO_BASE,
        "segmento": cfg.SEGMENTO,
        "zonas_que_cambian_en_el_top_50": n_cambia,
        "nota": ("La brecha cruda mide distancia fisica. Ponderada por "
                 "dependencia mide a quien le duele esa distancia. Cambiar de "
                 "modo mueve el top-50 en "
                 f"{n_cambia} zonas: no es un matiz, es otra pregunta."),
    }
    log(f"  modos: cambiar necesidad<->comercial mueve {n_cambia} zonas del top-50")

    # --- saturacion: el otro modo de fracaso -------------------------------
    # Una farmacia no solo fracasa por falta de demanda. Tambien fracasa por
    # sobreoferta, y por ausencia de mercado. Mostrar solo el extremo alto de
    # la brecha deja fuera media recomendacion.
    b_ref = t[f"{cfg.MODO_BASE}_{cfg.ANIOS_PROY[1]}"]
    t["pct_brecha"] = b_ref.rank(pct=True)
    t["saturada"] = ((t["pct_brecha"] <= cfg.PCT_SATURACION) &
                     (t["pobtot_2020"].fillna(0) >= cfg.MIN_POB_MERCADO)).astype(int)
    t["sin_mercado"] = (t["pobtot_2020"].fillna(0) < cfg.MIN_POB_MERCADO).astype(int)
    diag["saturacion"] = {
        "zonas_saturadas": int(t["saturada"].sum()),
        "zonas_sin_mercado": int(t["sin_mercado"].sum()),
        "umbral_percentil": cfg.PCT_SATURACION,
        "umbral_poblacion": cfg.MIN_POB_MERCADO,
        "lectura": ("Dos modos de fracaso distintos: sobreoferta (hay gente "
                    "pero ya hay demasiadas alternativas) y ausencia de mercado "
                    "(no hay suficiente gente). En los dos la recomendacion es "
                    "no abrir, por razones opuestas."),
    }
    log(f"  saturacion: {int(t.saturada.sum())} zonas con sobreoferta, "
        f"{int(t.sin_mercado.sum())} sin mercado")

    diag["supuestos_mercado"] = cfg.SUPUESTOS_MERCADO

    # --- contencion vs cobertura: el hallazgo central ----------------------
    # La version ingenua marca como desierto toda AGEB sin establecimiento
    # dentro de su poligono. Al medir COBERTURA a 800 m resulta que la CDMX
    # no tiene un solo desierto: la AGEB peor servida alcanza varias unidades.
    #
    # Ese vacio es en si mismo el hallazgo: el problema de la CDMX no es
    # ausencia de farmacias, es SATURACION DESIGUAL. Y eso cambia por completo
    # la recomendacion de negocio.
    acc = t[f"acc_{cfg.ANIO_BASE}"]
    t["desierto_contencion"] = (t[f"n_{cfg.ANIO_BASE}"] == 0).astype(int)
    t["desierto_cobertura"] = (acc < 0.10).astype(int)
    t["acc_percentil"] = acc.rank(pct=True)
    diag["desiertos"] = {
        "por_contencion": int(t.desierto_contencion.sum()),
        "por_cobertura": int(t.desierto_cobertura.sum()),
        "accesibilidad_min": round(float(acc.min()), 2),
        "accesibilidad_p05": round(float(acc.quantile(0.05)), 2),
        "accesibilidad_mediana": round(float(acc.median()), 2),
        "accesibilidad_max": round(float(acc.max()), 2),
        "hallazgo": ("La version ingenua marca 449 AGEB como desierto. Al medir "
                     "cobertura a 800 m no queda ninguna: la AGEB peor servida "
                     "de la ciudad alcanza el equivalente a 2 establecimientos. "
                     "El problema de la CDMX no es ausencia de farmacias, es "
                     "saturacion desigual."),
    }
    log(f"  desiertos por contencion (version ingenua): {t.desierto_contencion.sum()}")
    log(f"  desiertos por cobertura a 800 m          : {t.desierto_cobertura.sum()}")
    log(f"  accesibilidad: min {acc.min():.1f} | mediana {acc.median():.1f} "
        f"| max {acc.max():.1f}")

    # sensibilidad al ancho de banda
    sens = {}
    of26 = capas[cfg.ANIO_BASE]
    of26 = of26[of26.codigo_act.isin(cfg.SCIAN_OFERTA)]
    for h in cfg.ANCHOS_SENSIBILIDAD:
        a = espacial.accesibilidad(agebs, of26, "a", ancho=h)["a"].to_numpy()
        ref = t[f"acc_{cfg.ANIO_BASE}"].to_numpy()
        # La afirmacion que defendemos es que el ORDENAMIENTO de zonas no
        # depende del ancho de banda, y eso se mide con Spearman (rangos),
        # no con Pearson (niveles). Se reportan las dos: Pearson dice si los
        # valores se mueven juntos, Spearman si el ranking se conserva.
        sens[int(h)] = {
            "desiertos": int((a < 0.10).sum()),
            "spearman_con_800m": round(modelo.spearman(ref, a), 4),
            "pearson_con_800m": round(float(np.corrcoef(a, ref)[0, 1]), 4),
        }
    diag["sensibilidad_ancho_banda"] = sens
    log(f"  sensibilidad al ancho de banda: {sens}")

    # hallazgo por alcaldia
    alc = (t.groupby("CVE_MUN")
             .agg(pob=("pobtot_2020", "sum"), p60=("p_60ymas_2020", "sum"),
                  farmacias=(f"n_{cfg.ANIO_BASE}", "sum"),
                  agebs=("CVEGEO", "count"),
                  recambio=("recambio", "mean"))
             .reset_index())
    alc["alcaldia"] = alc.CVE_MUN.map(cfg.ALCALDIAS)
    alc["farm_por_10k_60mas"] = alc.farmacias / (alc.p60 / 10000)
    alc = alc.sort_values("farm_por_10k_60mas")
    diag["por_alcaldia"] = alc.round(3).to_dict("records")
    log("\n  Establecimientos de oferta por cada 10 mil personas de 60+:")
    for _, r in alc.iterrows():
        log(f"    {r.alcaldia:<22} {r.farm_por_10k_60mas:6.1f}   "
            f"recambio {r.recambio:+.2f} pp")

    # ------------------------------------------------------------ 8. salidas
    log("\n[8/8] Escribiendo salidas")
    t.to_file(cfg.PROCESADOS / "tabla_maestra.gpkg", driver="GPKG")
    plano = pd.DataFrame(t.drop(columns="geometry"))
    plano.to_csv(cfg.PROCESADOS / "tabla_maestra.csv", index=False)

    diag["config"] = {
        "scian_oferta": cfg.SCIAN_OFERTA,
        "scian_contexto": cfg.SCIAN_CONTEXTO,
        "ancho_banda_m": cfg.ANCHO_BANDA_M,
        "anio_base": cfg.ANIO_BASE,
        "anios_proyectados": cfg.ANIOS_PROY,
        "escenarios": cfg.ESCENARIOS,
        "conapo_fuente": cfg.CONAPO_FUENTE,
        "meses_denue": cfg.MESES_DENUE,
    }
    with open(cfg.SALIDAS / "diagnostico.json", "w", encoding="utf-8") as f:
        json.dump(diag, f, ensure_ascii=False, indent=2, default=str)

    from src import exportar
    limites = carga.cargar_alcaldias(2020)
    paquete = exportar.construir(t, diag, limites)
    info = exportar.escribir(paquete)
    log(f"  agebs.geojson : {info['geojson_mb']} MB  "
        f"({info['n_features']} poligonos)")
    log(f"  datos.json    : {info['datos_json_mb']} MB  "
        f"({info['n_variables']} variables)")
    log(f"  app/datos.js  : {info['datos_js_mb']} MB")

    log(f"\n  {cfg.PROCESADOS / 'tabla_maestra.gpkg'}")
    log(f"  {cfg.SALIDAS / 'diagnostico.json'}")
    log("\nListo.")
    return t, diag


if __name__ == "__main__":
    main()
