"""
Configuracion central del proyecto.
Todo lo ajustable vive aqui, no dentro de los otros modulos.
"""
from pathlib import Path

# ----------------------------------------------------------------- rutas
RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "datos" / "crudos"
PROCESADOS = RAIZ / "datos" / "procesados"
SALIDAS = RAIZ / "salidas"
APP = RAIZ / "app"

for _d in (CRUDOS, PROCESADOS, SALIDAS, APP):
    _d.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------- ambito
ENTIDAD = "09"                  # Ciudad de Mexico
CRS_GEO = "EPSG:4326"           # lat/lon del DENUE y del GeoJSON final
CRS_METRICO = "EPSG:6372"       # Mexico ITRF2008 / LCC. Distancias en metros.

ALCALDIAS = {
    "09002": "Azcapotzalco", "09003": "Coyoacán", "09004": "Cuajimalpa",
    "09005": "Gustavo A. Madero", "09006": "Iztacalco", "09007": "Iztapalapa",
    "09008": "Magdalena Contreras", "09009": "Milpa Alta", "09010": "Álvaro Obregón",
    "09011": "Tláhuac", "09012": "Tlalpan", "09013": "Xochimilco",
    "09014": "Benito Juárez", "09015": "Cuauhtémoc", "09016": "Miguel Hidalgo",
    "09017": "Venustiano Carranza",
}

# ----------------------------------------------------------------- categoria
SCIAN_OFERTA = {
    "464111": "Farmacias sin minisuper",
    "464112": "Farmacias con minisuper",
    "621111": "Consultorios de medicina general, sector privado",
    "621115": "Clinicas de consultorios medicos, sector privado",
}
SCIAN_CONTEXTO = {
    "464113": "Naturistas y homeopaticos",
    "462111": "Supermercados",
    "462112": "Minisupers",
    "461110": "Abarrotes y miscelaneas",
    "623311": "Asilos y residencias para personas adultas mayores",
    "621113": "Consultorios de medicina especializada, sector privado",
    "621511": "Laboratorios medicos y de diagnostico",
    "465111": "Perfumeria y cosmeticos",
    "464121": "Lentes",
    "464122": "Articulos ortopedicos",
}
SCIAN_TODAS = {**SCIAN_OFERTA, **SCIAN_CONTEXTO}

# ----------------------------------------------------------------- tiempo
# Mes real de cada corte del DENUE. No son todos del mismo mes, y el modelo
# usa el tiempo transcurrido REAL entre cortes, no 12 meses parejos.
MESES_DENUE = {
    2016: 1, 2017: 3, 2018: 3, 2019: 4, 2020: 4, 2021: 5,
    2022: 5, 2023: 11, 2024: 5, 2025: 5, 2026: 5,
}
ANIOS_DENUE = sorted(MESES_DENUE)

ANIO_BASE = 2026
HORIZONTES = [1, 3, 5]                              # lo que pide el reto
ANIOS_PROY = [ANIO_BASE + h for h in HORIZONTES]    # 2027, 2029, 2031

# Ruptura conocida de la serie: entre estos anios el DENUE cambia de version
# del catalogo SCIAN y varias clases saltan sin que haya aperturas reales.
# El modelo NO entrena sobre estas transiciones.
TRANSICIONES_EXCLUIDAS = [(2019, 2020), (2024, 2025)]

# ----------------------------------------------------------------- accesibilidad
# Ancho de banda del decaimiento gaussiano, en metros. ~10 min caminando.
# Es el supuesto mas discutible del modelo: se declara y se prueba su
# sensibilidad con los valores de ANCHOS_SENSIBILIDAD.
ANCHO_BANDA_M = 800.0
ANCHOS_SENSIBILIDAD = [500.0, 800.0, 1200.0]
RADIO_CORTE_M = 2500.0

# ----------------------------------------------------------------- escenarios
# Cada escenario es una objecion convertida en parametro.
ESCENARIOS = {
    "tendencial": {
        "nombre": "Tendencial",
        "descripcion": "La ciudad sigue la trayectoria observada entre censos.",
        "factor_demanda": 1.00,
        "factor_deriva": 1.00,
    },
    "digitalizacion": {
        "nombre": "Digitalización",
        "descripcion": ("Parte de la demanda de 60+ migra a teleconsulta y compra "
                        "en línea. Responde a la crítica de que el adulto mayor de "
                        "2031 tiene cultura digital."),
        "factor_demanda": 0.78,
        "factor_deriva": 1.00,
    },
    "recambio": {
        "nombre": "Envejecimiento acelerado",
        "descripcion": ("El desplazamiento barrial observado entre 2010 y 2020 se "
                        "acelera al doble. Responde a la hipótesis de barrios que "
                        "envejecen y barrios que rejuvenecen."),
        "factor_demanda": 1.00,
        "factor_deriva": 2.00,
    },
}

# ----------------------------------------------------------------- CONAPO
# El servidor de CONAPO estuvo caido durante la construccion del proyecto,
# asi que el total de control viene de la cifra publicada, no del archivo.
# Fuente: diagnostico INEGI-CONAPO-INAPAM, proyecciones CONAPO 2023.
# CDMX: 15.2% de poblacion de 60 y mas en 2020 -> 21.1% en 2030.
CONAPO_ANCLA = {2020: 0.152, 2030: 0.211}
CONAPO_FUENTE = ("CONAPO, proyecciones 2023, via diagnostico INEGI-CONAPO-INAPAM. "
                 "Cifra publicada: la CDMX pasa de 15.2% de poblacion de 60 y mas "
                 "en 2020 a 21.1% en 2030.")

# ----------------------------------------------------------------- incertidumbre
NIVEL_CONFIANZA = 0.80
SEMILLA = 42
TOP_K = 50

# ----------------------------------------------------------------- nombre
# El proyecto se llama por su indicador. Vive aqui para que el nombre no se
# escriba a mano en cinco lugares y se desincronice.
PROYECTO = {
    "sigla": "I.D.A.P.",
    "nombre": "Indice de Demanda de Atencion Primaria",
    "que_es": ("Un numero por zona: cuanta gente va a necesitar un consultorio "
               "de farmacia cerca, frente a los que puede alcanzar caminando."),
}

# ----------------------------------------------------------------- segmento
# NO es "adultos mayores". Es poblacion que depende de atencion primaria de
# bajo costo, y se define con DOS variables: edad y nivel socioeconomico.
#
# Viene de la retroalimentacion del Dr. Incera: quien entra a un consultorio
# de farmacia no es principalmente el adulto mayor, es quien no tiene otra
# opcion de atencion. Un profesor del ITAM de 65 anios con seguro de gastos
# medicos no es nuestro mercado; el personal de mantenimiento del mismo
# edificio, si.
SEGMENTO = {
    "nombre": "Población dependiente de atención primaria de bajo costo",
    "edad": "60 y más (censo INEGI por AGEB)",
    "socioeconomico": ("Población sin derechohabiencia a servicios de salud, "
                       "% por AGEB (CONEVAL 2020). Se prefiere al Grado de "
                       "Rezago Social porque ése es ordinal, está calibrado a "
                       "escala nacional y deja 90% de la CDMX en dos niveles."),
}

MODOS = {
    "necesidad": {
        "nombre": "Necesidad",
        "descripcion": ("Pondera por dependencia: quien no tiene otra opción de "
                        "atención. Es el modo por omisión."),
        "peso": "dependencia",
    },
    "comercial": {
        "nombre": "Comercial",
        "descripcion": ("Pondera por capacidad de pago: dónde hay clientes que "
                        "gastan. Es la pregunta de negocio pura."),
        "peso": "gasto",
    },
}
MODO_BASE = "necesidad"

# Saturacion: el otro extremo de la brecha. Una farmacia fracasa por dos
# razones, no una: sobreoferta (demasiada competencia) o ausencia de mercado
# (no hay gente). Las dos son recomendaciones utiles.
PCT_SATURACION = 0.15        # decil-y-medio inferior de la brecha
MIN_POB_MERCADO = 500        # poblacion total minima para que exista mercado

# ----------------------------------------------------------------- supuestos
# Supuestos de COMPORTAMIENTO DEL CONSUMIDOR. Son falsos y se asumen a
# proposito para esta primera version. Van en el visor y en la presentacion:
# un modelo que no declara sus supuestos no se puede criticar, y uno que no
# se puede criticar no sirve para decidir.
SUPUESTOS_MERCADO = [
    {
        "supuesto": "Mercado simplificado y distancias uniformes",
        "por_que_es_falso": ("El precio, las promociones y el surtido varían "
                             "entre cadenas."),
        "que_hariamos": "Incorporar precio relativo por cadena.",
    },
    {
        "supuesto": "Cliente perfecto: cada quien va a la farmacia más cercana",
        "por_que_es_falso": ("La gente va a la de su programa de lealtad, o a la "
                             "que más se anuncia."),
        "que_hariamos": "Ponderar por participación de mercado de cada cadena.",
    },
    {
        "supuesto": "Más oferta implica más atención",
        "por_que_es_falso": ("Dos farmacias a la misma distancia no atienden "
                             "igual: depende de estrategia comercial."),
        "que_hariamos": "Datos de tráfico o de consumo, que hoy no son públicos.",
    },
]

# ----------------------------------------------------------------- recomendaciones
# Piso de poblacion de 60 y mas para que una AGEB pueda aparecer en las
# recomendaciones. La brecha es un cociente: con 10 personas de 60 y mas y
# cero oferta, el cociente se dispara sin que haya ninguna decision que tomar.
# 200 personas deja fuera 293 de 2,431 AGEB (12%) pero solo 1.8% de la demanda
# de la ciudad: son zonas chicas, no zonas ignoradas.
MIN_P60_RECO = 200

# ----------------------------------------------------------------- paleta
# Primarios sobre crema, para el visor y los mapas.
PALETA = {
    "crema": "#FAF7F0",
    "crema_2": "#F2EDE3",
    "tinta": "#3A3226",
    "tinta_suave": "#6B6152",
    "amarillo": "#F2B705",
    "azul": "#1B5FA8",
    "rojo": "#C8322B",
    "negro": "#1A1712",
    "blanco": "#FFFFFF",
}
