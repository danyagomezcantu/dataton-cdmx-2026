"""
El modelo. Tres piezas, y cada una es un tipo de objeto distinto.

  1. DEMANDA  -> aritmetica de cohortes con control CONAPO + reparto shift-share.
                 NO es un modelo ajustado: no tiene R2 ni residuales. Es
                 contabilidad demografica.

  2. OFERTA   -> GLM de conteo (Poisson / binomial negativa, liga logaritmica)
                 sobre un panel de transiciones. Aqui SI hay estimacion y error.

  3. BRECHA   -> cociente interpretable entre las dos. No es regresion: es el
                 instrumento de decision.

La regresion lineal aparece UNICAMENTE como baseline a vencer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg


# ==========================================================================
# utilidades de tiempo
# ==========================================================================
def fecha_decimal(anio: int) -> float:
    """Anio decimal del corte, usando el mes real. 2023-11 -> 2023.83"""
    mes = cfg.MESES_DENUE.get(anio, 6)
    return anio + (mes - 1) / 12.0


def transiciones_validas() -> list[tuple[int, int]]:
    """Pares (origen, destino) de cortes consecutivos, sin las rupturas."""
    a = cfg.ANIOS_DENUE
    pares = list(zip(a[:-1], a[1:]))
    return [p for p in pares if p not in cfg.TRANSICIONES_EXCLUIDAS]


# ==========================================================================
# 1. DEMANDA
# ==========================================================================
def control_ciudad(tabla: pd.DataFrame, anio: int) -> float:
    """
    Total de personas de 60 y mas en la ciudad para el anio pedido.

    La BASE es dato observado: la suma del censo 2020 por AGEB.
    La TASA DE CRECIMIENTO viene de CONAPO: la CDMX pasa de 15.2% a 21.1% de
    poblacion de 60 y mas entre 2020 y 2030. Ese salto implica una razon de
    0.211/0.152 en diez anios sobre la proporcion, que aplicamos como
    crecimiento compuesto anual del grupo.

    Asi cada fuente aporta lo que sabe hacer: el nivel observado es del censo,
    la trayectoria es de CONAPO, y nosotros solo hacemos el reparto espacial.
    """
    base = float(tabla["p_60ymas_2020"].sum())
    r = (cfg.CONAPO_ANCLA[2030] / cfg.CONAPO_ANCLA[2020]) ** (1 / 10.0)
    return base * (r ** (anio - 2020))


def proyectar_demanda(tabla: pd.DataFrame, anio: int, escenario: str = "tendencial",
                      col: str = "demanda") -> pd.Series:
    """
    Reparto en dos pasos del total de control.

    Paso 1 - ciudad -> alcaldia:
        participacion de la alcaldia m en el total de 60+ de la ciudad,
        observada en 2010 y en 2020, extrapolada linealmente al anio t.

    Paso 2 - alcaldia -> AGEB:
        lo mismo, pero de cada AGEB dentro de su alcaldia.

    En ambos pasos la deriva se multiplica por factor_deriva, que es lo que
    distingue al escenario de recambio acelerado.

    Limitacion que hay que decir en voz alta: con dos censos hay UN solo
    incremento por AGEB. No es una tendencia ajustada, es una diferencia.
    Con dos puntos no se estima una recta: la recta ES la resta.
    """
    esc = cfg.ESCENARIOS[escenario]
    fd, fdrv = esc["factor_demanda"], esc["factor_deriva"]
    pasos = (anio - 2020) / 10.0

    df = tabla.copy()
    p10 = df["p_60ymas_2010"].fillna(df["p_60ymas_2020"])
    p20 = df["p_60ymas_2020"].fillna(0)

    # --- paso 1: participacion de cada alcaldia en la ciudad ---------------
    alc10 = p10.groupby(df["CVE_MUN"]).transform("sum")
    alc20 = p20.groupby(df["CVE_MUN"]).transform("sum")
    tot10, tot20 = float(p10.sum()), float(p20.sum())
    s_alc10 = alc10 / max(tot10, 1e-9)
    s_alc20 = alc20 / max(tot20, 1e-9)
    s_alc = (s_alc20 + fdrv * (s_alc20 - s_alc10) * pasos).clip(lower=0)

    # --- paso 2: participacion de cada AGEB dentro de su alcaldia ----------
    s_ageb10 = p10 / alc10.replace(0, np.nan)
    s_ageb20 = p20 / alc20.replace(0, np.nan)
    s_ageb10 = s_ageb10.fillna(s_ageb20).fillna(0)
    s_ageb20 = s_ageb20.fillna(0)
    s_ageb = (s_ageb20 + fdrv * (s_ageb20 - s_ageb10) * pasos).clip(lower=0)

    # renormalizar cada nivel para que las participaciones sumen 1
    s_ageb = s_ageb / s_ageb.groupby(df["CVE_MUN"]).transform("sum").replace(0, np.nan)
    s_ageb = s_ageb.fillna(0)
    uniq = s_alc.groupby(df["CVE_MUN"]).transform("first")
    suma_alc = uniq.groupby(df["CVE_MUN"]).first().sum()
    s_alc = s_alc / max(float(suma_alc), 1e-9)

    total = control_ciudad(df, anio) * fd
    return pd.Series(total * s_alc.values * s_ageb.values, index=df.index, name=col)


# ==========================================================================
# 2. OFERTA
# ==========================================================================
VARIABLES = ["log_n", "log_acc", "log_dens", "tasa_60", "crec_60", "grs_z"]


def construir_panel(tabla: pd.DataFrame, pares=None) -> pd.DataFrame:
    """
    Panel largo: una fila por (AGEB, transicion).

    Con once cortes del DENUE tenemos ocho transiciones utiles, o sea ~19,000
    observaciones en vez de las ~2,400 de una sola transicion. Eso es lo que
    permite que el GLM tenga algo que estimar de verdad.

    El offset incluye log(anios transcurridos) porque los cortes NO estan
    espaciados parejo: van de 6 a 18 meses.
    """
    pares = pares or transiciones_validas()
    filas = []
    for t0, t1 in pares:
        d = pd.DataFrame({
            "CVEGEO": tabla["CVEGEO"].values,
            "CVE_MUN": tabla["CVE_MUN"].values,
            "t0": t0, "t1": t1,
            "n0": tabla[f"n_{t0}"].astype(float).values,
            "n1": tabla[f"n_{t1}"].astype(float).values,
            "acc0": tabla[f"acc_{t0}"].astype(float).values,
            "pobtot": tabla["pobtot_2020"].fillna(0).clip(lower=1).values,
            "dens": tabla["dens_pob"].fillna(0).values,
            "tasa_60": tabla["tasa_60_2020"].fillna(0).values,
            "crec_60": tabla["crec_60_10_20"].fillna(0).values,
            "grs": tabla["grs"].fillna(3).values,
        })
        d["dt"] = fecha_decimal(t1) - fecha_decimal(t0)
        filas.append(d)

    p = pd.concat(filas, ignore_index=True)
    p["log_n"] = np.log1p(p["n0"])
    p["log_acc"] = np.log1p(p["acc0"])
    p["log_dens"] = np.log1p(p["dens"])
    p["grs_z"] = (p["grs"] - p["grs"].mean()) / max(p["grs"].std(), 1e-9)
    p["offset"] = np.log(p["pobtot"]) + np.log(p["dt"].clip(lower=0.1))
    return p


def ajustar(panel: pd.DataFrame, familia: str = "poisson"):
    """
    n1_i ~ Poisson( exp( offset_i + X_i beta ) )

    Por que NO minimos cuadrados: el numero de farmacias es un conteo entero,
    no negativo, cuya varianza crece con la media, y una fraccion grande de
    las AGEB tiene cero. Con OLS se predicen valores negativos justo en las
    zonas que mas nos importan. El GLM con liga logaritmica resuelve las tres
    cosas, y ademas sus coeficientes se leen como efectos multiplicativos:
    exp(beta) es el factor por el que cambia el conteo esperado.
    """
    import statsmodels.api as sm

    X = sm.add_constant(panel[VARIABLES].astype(float), has_constant="add")
    y = panel["n1"].astype(float)
    off = panel["offset"].astype(float)

    ok = np.isfinite(X.to_numpy()).all(axis=1) & np.isfinite(y) & np.isfinite(off)
    X, y, off = X[ok], y[ok], off[ok]

    if familia == "negbin":
        m_, v_ = float(y.mean()), float(y.var())
        alpha = max((v_ - m_) / max(m_ ** 2, 1e-9), 0.01)
        fam = sm.families.NegativeBinomial(alpha=alpha)
    else:
        fam = sm.families.Poisson()

    return sm.GLM(y, X, family=fam, offset=off.to_numpy()).fit()


def predecir(modelo, panel: pd.DataFrame) -> np.ndarray:
    import statsmodels.api as sm
    X = sm.add_constant(panel[VARIABLES].astype(float), has_constant="add")
    X = X[modelo.params.index]
    return np.asarray(modelo.predict(X, offset=panel["offset"].to_numpy()))


def dispersion(panel: pd.DataFrame) -> dict:
    y = panel["n1"].astype(float)
    m, v = float(y.mean()), float(y.var())
    return {"media": round(m, 3), "varianza": round(v, 3),
            "razon": round(v / max(m, 1e-9), 3),
            "recomendacion": "negbin" if v > 1.5 * m else "poisson"}


# ==========================================================================
# 3. INCERTIDUMBRE
# ==========================================================================
def ancho_conforme(y_cal, pred_cal, nivel: float = None) -> float:
    """
    Prediccion conforme dividida.

    En un conjunto de CALIBRACION que el modelo nunca vio, mide los errores
    absolutos y toma el cuantil (1-alfa). Ese ancho garantiza cobertura sin
    suponer ninguna distribucion, y se puede VERIFICAR midiendo que fraccion
    de los valores reales cae dentro.
    """
    nivel = nivel or cfg.NIVEL_CONFIANZA
    r = np.abs(np.asarray(y_cal, float) - np.asarray(pred_cal, float))
    r = r[np.isfinite(r)]
    if len(r) == 0:
        return 0.0
    q = min(1.0, np.ceil((len(r) + 1) * nivel) / len(r))
    return float(np.quantile(r, q))


# ==========================================================================
# 4. BRECHA
# ==========================================================================
def _normalizar(x: pd.Series, lo_q=0.05, hi_q=0.95) -> pd.Series:
    """
    Lleva una serie a 0-1 entre sus percentiles 5 y 95, recortando las colas.

    Se usan percentiles y no el minimo y maximo porque el archivo del CONEVAL
    tiene AGEB con 0% y con 100%, casi siempre de poblacion minuscula, y esos
    extremos aplastarian a las 2,400 zonas de en medio.
    """
    x = pd.to_numeric(x, errors="coerce")
    lo, hi = float(x.quantile(lo_q)), float(x.quantile(hi_q))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return pd.Series(0.5, index=x.index)
    return ((x - lo) / (hi - lo)).clip(0, 1).fillna(0.5)


def peso_dependencia(sin_salud: pd.Series) -> pd.Series:
    """
    Peso de NECESIDAD, y peso por omision del proyecto.

    Sale del porcentaje de poblacion SIN derechohabiencia a servicios de salud
    del CONEVAL, normalizado entre los percentiles 5 y 95 de la ciudad y
    llevado al rango 0.2 - 1.0.

        ~16% sin derechohabiencia -> 0.2   casi todos tienen IMSS o seguro
        ~38% sin derechohabiencia -> 1.0   la farmacia es la primera opcion

    POR QUE ESTA VARIABLE Y NO EL GRADO DE REZAGO. La retroalimentacion del
    Dr. Incera fue que quien entra a un consultorio de farmacia no es
    principalmente el adulto mayor sino quien no tiene otra opcion, y que la
    variable determinante es el ingreso. La primera version de este peso usaba
    el Grado de Rezago Social, que es ordinal de 1 a 5 y esta calibrado a
    escala NACIONAL: dentro de la CDMX deja 948 AGEB en 'Muy bajo' y 1,234 en
    'Bajo', o sea 90% de la ciudad en dos niveles. No discriminaba.

    El porcentaje sin derechohabiencia es continuo, es por AGEB, y mide
    directamente el mecanismo: quien no tiene IMSS, ISSSTE ni seguro privado
    es quien termina en el consultorio de la farmacia. No es un proxy de
    ingreso, es la consecuencia del ingreso que nos importa.

    Efecto medible: sin este peso la zona numero uno de la ciudad era Lomas de
    Chapultepec, con 766 personas de 60 y mas y cero comercio adentro por uso
    de suelo. La brecha fisica ahi es real, pero esa poblacion no depende de
    una farmacia del ahorro.
    """
    return (0.2 + 0.8 * _normalizar(sin_salud)).clip(0.2, 1.0)


def peso_gasto(sin_salud: pd.Series) -> pd.Series:
    """
    Peso COMERCIAL: el espejo exacto del de dependencia.

    Donde casi todos tienen derechohabiencia hay mas capacidad de pago, asi
    que este peso contesta la otra pregunta legitima: donde hay clientes que
    gastan. Es la pregunta de negocio pura, y en el visor es un selector.
    """
    return (1.2 - peso_dependencia(sin_salud)).clip(0.2, 1.0)


def brecha(demanda: pd.Series, oferta: pd.Series) -> pd.Series:
    """
    Personas de 60 y mas por unidad de servicio alcanzable.

        B = D / (A + 1)

    El +1 evita dividir entre cero y tiene lectura: equivale a suponer media
    unidad de respaldo en toda la ciudad.
    """
    return demanda / (oferta.clip(lower=0) + 1.0)


def categorizar(s: pd.Series) -> pd.Series:
    r = s.rank(pct=True)
    return pd.cut(r, [0, .5, .75, .9, 1.0],
                  labels=["baja", "media", "alta", "prioritaria"],
                  include_lowest=True)


# ==========================================================================
# 5. VALIDACION
# ==========================================================================
def precision_top_k(real, pred, k: int = None) -> float:
    """
    De las k zonas que el modelo puso arriba, cuantas estaban de verdad arriba.
    Esta es la metrica que importa: la decision real es donde abrir, no cual
    es el error promedio en 2,431 zonas.
    """
    k = k or cfg.TOP_K
    real, pred = np.asarray(real, float), np.asarray(pred, float)
    ok = np.isfinite(real) & np.isfinite(pred)
    real, pred = real[ok], pred[ok]
    k = min(k, len(real))
    if k == 0:
        return float("nan")
    return len(set(np.argsort(-real)[:k]) & set(np.argsort(-pred)[:k])) / k


def spearman(real, pred) -> float:
    from scipy.stats import spearmanr
    real, pred = np.asarray(real, float), np.asarray(pred, float)
    ok = np.isfinite(real) & np.isfinite(pred)
    if ok.sum() < 3:
        return float("nan")
    return float(spearmanr(real[ok], pred[ok]).statistic)


def cobertura(real, lo, hi) -> float:
    real, lo, hi = (np.asarray(v, float) for v in (real, lo, hi))
    ok = np.isfinite(real) & np.isfinite(lo) & np.isfinite(hi)
    if ok.sum() == 0:
        return float("nan")
    return float(((real >= lo) & (real <= hi))[ok].mean())


def baselines(tabla: pd.DataFrame, t_origen: int, t_prev: int) -> dict:
    """
    Los tres rivales a vencer. Si el modelo no le gana a alguno, se dice.

      sin_cambio       - el conteo se queda igual
      tendencia_lineal - extrapola el incremento del periodo anterior
      crecimiento_pob  - el conteo crece igual que la poblacion de 60+
    """
    n0 = tabla[f"n_{t_origen}"].astype(float).to_numpy()
    nprev = tabla[f"n_{t_prev}"].astype(float).to_numpy()
    crec = (tabla["p_60ymas_2020"] / tabla["p_60ymas_2010"].replace(0, np.nan)
            ).replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(0.2, 5).to_numpy()
    return {
        "sin_cambio": n0,
        "tendencia_lineal": np.maximum(n0 + (n0 - nprev), 0),
        "crecimiento_pob": n0 * crec,
    }


def backtest(tabla: pd.DataFrame, familia: str, corte_entrenamiento: int = 2023) -> dict:
    """
    Validacion retrospectiva.

    1. ENTRENAR solo con transiciones que terminan en <= corte_entrenamiento.
       El modelo no ve nada posterior.
    2. PREDECIR el ultimo corte a partir del penultimo.
    3. COMPARAR contra lo observado, con precision en el top-k, correlacion de
       rangos y cobertura del intervalo.
    4. CONTRASTAR contra los tres baselines.
    """
    pares = transiciones_validas()
    tren = [p for p in pares if p[1] <= corte_entrenamiento]
    prueba = [p for p in pares if p[1] > corte_entrenamiento]
    if not prueba:
        prueba = [pares[-1]]
        tren = pares[:-1]

    p_tren = construir_panel(tabla, tren)
    p_prueba = construir_panel(tabla, prueba)

    # particion de calibracion, para el intervalo conforme
    rng = np.random.default_rng(cfg.SEMILLA)
    idx = rng.permutation(len(p_tren))
    corte = int(len(idx) * 0.7)
    m_fit = ajustar(p_tren.iloc[idx[:corte]], familia)
    pred_cal = predecir(m_fit, p_tren.iloc[idx[corte:]])
    ancho = ancho_conforme(p_tren.iloc[idx[corte:]]["n1"].to_numpy(), pred_cal)

    modelo = ajustar(p_tren, familia)
    pred = predecir(modelo, p_prueba)
    real = p_prueba["n1"].to_numpy(float)
    lo, hi = np.maximum(pred - ancho, 0), pred + ancho

    ultimo = prueba[-1]
    prev_idx = cfg.ANIOS_DENUE.index(ultimo[0])
    t_prev = cfg.ANIOS_DENUE[max(prev_idx - 1, 0)]
    b = baselines(tabla, ultimo[0], t_prev)
    real_ult = tabla[f"n_{ultimo[1]}"].to_numpy(float)
    n0_ult = tabla[f"n_{ultimo[0]}"].to_numpy(float)
    sub = p_prueba[p_prueba["t1"] == ultimo[1]]
    pred_ult = predecir(modelo, sub)

    # ---- la evaluacion que importa: el CAMBIO, no el nivel ----------------
    # El conteo de farmacias por AGEB es extremadamente estable: entre dos
    # cortes consecutivos solo cambia en 0.3% a 14% de las AGEB. Por eso
    # cualquier metrica sobre el NIVEL la gana "suponer que nada cambia":
    # no porque ese baseline sea bueno prediciendo, sino porque el nivel casi
    # no se mueve. La pregunta del reto es donde va a CAMBIAR la demanda, asi
    # que la prueba honesta es sobre el delta.
    delta_real = real_ult - n0_ult
    delta_pred = pred_ult - n0_ult

    res = {
        "transiciones_entrenamiento": [f"{a}->{b_}" for a, b_ in tren],
        "transiciones_prueba": [f"{a}->{b_}" for a, b_ in prueba],
        "n_observaciones_entrenamiento": int(len(p_tren)),
        "n_observaciones_prueba": int(len(p_prueba)),
        "modelo": {
            "precision_top_k_nivel": round(precision_top_k(real_ult, pred_ult), 3),
            "precision_top_k_cambio": round(precision_top_k(delta_real, delta_pred), 3),
            "spearman_nivel": round(spearman(real, pred), 3),
            "spearman_cambio": round(spearman(delta_real, delta_pred), 3),
            "mae": round(float(np.nanmean(np.abs(real - pred))), 3),
        },
        "incertidumbre": {
            "nivel_nominal": cfg.NIVEL_CONFIANZA,
            "cobertura_observada": round(cobertura(real, lo, hi), 3),
            "ancho_intervalo": round(ancho, 3),
            "nota": ("La prediccion conforme garantiza cobertura bajo "
                     "intercambiabilidad. Dos periodos distintos no son "
                     "intercambiables: la ciudad cambia. La diferencia entre "
                     "el nivel nominal y la cobertura observada MIDE ese "
                     "desplazamiento. Se reporta la observada."),
        },
        "baselines": {},
        "coeficientes": {k: round(float(v), 4) for k, v in modelo.params.items()},
        "efectos_multiplicativos": {k: round(float(np.exp(v)), 4)
                                    for k, v in modelo.params.items()},
        "pseudo_r2_devianza": round(float(1 - modelo.deviance / modelo.null_deviance), 4),
    }
    for nombre, vals in b.items():
        res["baselines"][nombre] = {
            "precision_top_k_nivel": round(precision_top_k(real_ult, vals), 3),
            "precision_top_k_cambio": round(
                precision_top_k(delta_real, np.asarray(vals, float) - n0_ult), 3),
            "spearman_nivel": round(spearman(real_ult, vals), 3),
            "spearman_cambio": round(
                spearman(delta_real, np.asarray(vals, float) - n0_ult), 3),
        }

    mejor_nivel = max(v["precision_top_k_nivel"] for v in res["baselines"].values())
    mejor_cambio = max(v["precision_top_k_cambio"] for v in res["baselines"].values())
    res["mejor_baseline_nivel"] = mejor_nivel
    res["mejor_baseline_cambio"] = mejor_cambio
    res["vence_en_nivel"] = bool(res["modelo"]["precision_top_k_nivel"] > mejor_nivel)
    res["vence_en_cambio"] = bool(res["modelo"]["precision_top_k_cambio"] > mejor_cambio)
    res["lectura"] = (
        "En NIVEL, el baseline 'sin cambio' es casi imbatible porque el conteo de "
        "establecimientos por AGEB apenas se mueve entre cortes. Eso no dice que "
        "el baseline prediga bien: dice que la serie es estable. La prueba "
        "informativa es la de CAMBIO, que es lo que el reto pregunta.")
    return res, modelo, ancho


def validacion_espacial(tabla: pd.DataFrame, familia: str) -> pd.DataFrame:
    """
    Validacion cruzada dejando fuera ALCALDIAS COMPLETAS.

    Si se parte al azar, AGEB vecinas quedan a ambos lados de la particion y
    el modelo memoriza el vecindario: hay fuga espacial y el desempenio se
    infla. Dejar fuera alcaldias completas mide si generaliza a territorio
    que no vio.
    """
    panel = construir_panel(tabla)
    filas = []
    for alc in sorted(panel["CVE_MUN"].dropna().unique()):
        tr = panel[panel.CVE_MUN != alc]
        te = panel[panel.CVE_MUN == alc]
        if len(te) < 20 or len(tr) < 200:
            continue
        try:
            m = ajustar(tr, familia)
            p = predecir(m, te)
        except Exception:                                        # noqa: BLE001
            continue
        r = te["n1"].to_numpy(float)
        filas.append({
            "cve_mun": alc,
            "alcaldia": cfg.ALCALDIAS.get(alc, alc),
            "n": len(te),
            "spearman": round(spearman(r, p), 3),
            "mae": round(float(np.nanmean(np.abs(r - p))), 3),
        })
    return pd.DataFrame(filas)
