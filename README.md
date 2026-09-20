# I.D.A.P. — Índice de Demanda de Atención Primaria

**¿Dónde va a faltar un consultorio de farmacia en la CDMX, y a quién?**

Datatón ITAM 2026 · reto ANTAD · datos de INEGI, CONEVAL y CONAPO

> No buscamos dónde viven los adultos mayores. Buscamos **quién va a necesitar
> atención primaria y no va a tener otra opción**. La edad dice cuánta demanda
> habrá; la falta de derechohabiencia a servicios de salud dice a quién le toca
> resolverla en el consultorio de la farmacia. Medimos la brecha entre esa
> demanda y lo que se alcanza caminando, a 1, 3 y 5 años.

---

## El segmento, y por qué no es "adultos mayores"

Quien entra a un consultorio de farmacia no es principalmente el adulto mayor:
es **quien no tiene otra opción de atención**. Alguien de 70 años con seguro de
gastos médicos no es este mercado. El personal de mantenimiento del mismo
edificio, sí.

Por eso el segmento se define con **dos** variables, no una:

| Variable | Fuente | Qué aporta |
|---|---|---|
| Población de 60 y más | Censo INEGI 2010 y 2020, por AGEB | Cuánta demanda habrá |
| % sin derechohabiencia a servicios de salud | CONEVAL 2020, por AGEB | A quién le toca resolverla en la farmacia |

**Por qué esa variable y no el Grado de Rezago Social.** El grado es ordinal de
1 a 5 y está calibrado a escala nacional: dentro de la CDMX deja 948 AGEB en
"Muy bajo" y 1,234 en "Bajo", o sea 90% de la ciudad en dos niveles. No
discrimina. El porcentaje sin derechohabiencia es continuo, va de 16% a 38%
entre los percentiles 5 y 95, y mide el mecanismo directamente: quien no tiene
IMSS, ISSSTE ni seguro privado es quien termina en el consultorio de la
farmacia, porque ahí la consulta cuesta veinte pesos y la privada cuesta mil.

### Los dos modos, y por qué son un selector y no una decisión nuestra

```
necesidad  = brecha × dependencia         ← modo por omisión
comercial  = brecha × capacidad de pago
```

Son espejo exacto, salen de la misma variable medida, y el visor deja cambiar
entre ellos. **Cambiar de modo mueve 76 zonas del top-50**: no es un matiz, es
otra pregunta.

El efecto más claro: sin ponderar, la zona número uno de la ciudad era Lomas de
Chapultepec, con 766 personas de 60 y más y cero comercio adentro por uso de
suelo. La brecha física ahí es real, pero esa población no depende de una
farmacia del ahorro. En modo necesidad baja; en modo comercial sigue primera, y
eso es correcto: son dos preguntas distintas y las dos son legítimas.

---

## Cómo editar la aplicación

**Edita `app/plantilla.html`**, no `aplicacion_interactiva.html` ni
`index.html`: esos dos se generan y cualquier cambio directo se pierde al
regenerar.

```bash
# editas app/plantilla.html en VS Code
python scripts/03_visor.py     # 2 segundos, regenera las dos versiones
```

Para probar cambios rápido, abre `app/index.html`: carga `datos.js` aparte, así
que basta recargar el navegador sin regenerar nada.

---

## El entregable

`app/aplicacion_interactiva.html` — **un solo archivo**, con los datos
incrustados. Doble clic y abre. Sin internet, sin servidor, sin instalar nada.
Esa es la versión que se lleva a la presentación.

`app/index.html` — la misma aplicación pero cargando `datos.js` de la carpeta.
Más cómoda para trabajar en equipo porque el HTML se edita sin volver a generar
1.6 MB.

Incluye buscador por colonia que fija la alcaldía y acerca el mapa a la zona,
botón de limpiar, tres recomendaciones calculadas (1, 3 y 5 años), límites y
nombres de alcaldía, explicación contextual de cada capa, glosario y las
secciones de validación, hallazgos, método, fuentes y límites.

### Las tres recomendaciones

No son texto escrito a mano: `src/exportar.py::recomendaciones()` las calcula
con un criterio distinto por horizonte y el visor solo las dibuja. Cada zona
nombrada es clicable y lleva el mapa a ella.

| Horizonte | Criterio | Confianza |
|---|---|---|
| 1 año | Mayor brecha proyectada a 2027 | Alta: la demanda ya está instalada |
| 3 años | Entra al 10% de peor brecha sin estar hoy ahí, ordenado por personas sumadas | Media |
| 5 años | Envejecimiento muy sobre el promedio + accesibilidad bajo el promedio | Baja: es escenario |

**Piso de población.** Solo pueden ser recomendadas las AGEB con al menos
`cfg.MIN_P60_RECO` = 200 **personas de 60 y más** (no población total): 2,138 de
2,431. La brecha es un
cociente, y con 10 adultos mayores y cero oferta se dispara sin que exista
decisión que tomar. Las 293 excluidas son 1.8% de la demanda de la ciudad.

El desempate a 3 años es en **personas**, no en saltos de posición, por la
misma razón: un cociente con denominador chico brinca mucho con poca gente.

---

## Arranque rápido

```bash
pip install -r requirements.txt

python scripts/01_filtrar_denue.py    # solo si vuelves a bajar el DENUE crudo
python scripts/02_pipeline.py         # ~3 min: lee crudos, modela, exporta
python scripts/03_visor.py            # arma las dos versiones del visor
```

Después, abre `app/aplicacion_interactiva.html`.

---

## Estructura

```
.
├── app/
│   ├── plantilla.html      la app, sin datos. AQUI se edita la interfaz.
│   ├── index.html          generado: carga datos.js aparte
│   ├── aplicacion_interactiva.html
│   │                       generado: todo en un archivo  <- el entregable
│   └── datos.js            generado: los datos como variables JS
├── src/
│   ├── config.py           TODO lo ajustable vive aquí
│   ├── carga.py            lectura y limpieza de cada fuente
│   ├── espacial.py         cruces espaciales y accesibilidad
│   ├── modelo.py           demanda, oferta, brecha, validación
│   └── exportar.py         genera los JSON del visor
├── scripts/
│   ├── 01_filtrar_denue.py filtra los cortes crudos del DENUE
│   ├── 02_pipeline.py      corre todo
│   └── 03_visor.py         arma el visor
├── datos/
│   ├── crudos/             NO se versiona (ver .gitignore)
│   └── procesados/         sí se versiona: geojson, datos.json, meta.json
└── salidas/
    └── diagnostico.json    backtest, coeficientes, métricas
```

**Regla:** si algo truena por nombres de columna, se ajusta `src/config.py`, no
el código.

---

## Las tres piezas del método

Esto es lo que más se pregunta, así que va primero.

| Pieza | Qué es | Qué NO es |
|---|---|---|
| Demanda | Aritmética de cohortes + reparto shift-share | No es un modelo ajustado. No tiene R² ni residuales. |
| Oferta | GLM de conteo, binomial negativa, liga logarítmica | No es mínimos cuadrados. |
| Brecha | Cociente interpretable | No es regresión. Es el instrumento de decisión. |
| Regresión lineal | Uno de los tres baselines a vencer | No es el método. |

### 1. Demanda

La gente de 55 a 59 años hoy es la de 60 a 64 en cinco años. Eso no es una
predicción, es cumplir años. Y nadie que vaya a tener 65 años en 2031 está por
nacer: ya lo contó el censo. Por eso toda la incertidumbre sobre natalidad, que
es la más grande de la demografía, no nos toca.

El nivel de control lo pone CONAPO. Nosotros solo repartimos en el espacio, en
dos pasos: de ciudad a alcaldía y de alcaldía a AGEB, usando la trayectoria
observada entre los censos de 2010 y 2020.

### 2. Oferta

```
n_destino ~ BinomialNegativa( exp( offset + X·β ) )
offset = log(población) + log(años transcurridos)
```

Por qué no mínimos cuadrados: el conteo de establecimientos es entero, no
negativo, con varianza que crece con la media (aquí es **10.9 veces** la media),
y 449 de 2,431 AGEB tienen cero. Con OLS se predicen farmacias negativas justo
en las zonas que más importan.

El panel tiene ~19,400 observaciones: 8 transiciones útiles entre los 11 cortes
del DENUE. Los cortes no están espaciados parejo (van de 6 a 18 meses), así que
el offset incluye el tiempo transcurrido real.

### 3. Brecha

```
B = demanda / (oferta accesible + 1)
```

Personas de 60 y más por unidad de servicio alcanzable.

### Accesibilidad, no contención

```
A_i = Σ_j exp( −d_ij² / (2·800²) )
```

Una zona sin farmacia dentro de su polígono pero con tres cruzando la avenida no
está desatendida.

---

## Los cinco hallazgos

**1. La CDMX no tiene desiertos de farmacias.** La versión ingenua marca 449
AGEB sin ningún establecimiento dentro. Midiendo cobertura a 800 metros no queda
ninguna: la zona peor servida alcanza el equivalente a 2 establecimientos y la
mediana ronda 60. El problema no es ausencia, es **saturación desigual**.

**2. Medir el rejuvenecimiento contra cero no distingue nada.** 2,358 de 2,431
AGEB envejecieron entre 2010 y 2020; solo 30 rejuvenecieron. La ciudad entera se
está haciendo vieja, con un promedio de +5.18 puntos porcentuales. La medida
informativa es el apartamiento respecto a ese promedio, y ahí sí aparece el
envejecimiento desigual: 1,300 zonas envejecieron más lento que la ciudad.

**3. La periferia está mejor servida por persona mayor que el centro-poniente.**
Coyoacán tiene 47.8 establecimientos por cada 10 mil personas de 60 y más;
Milpa Alta tiene 137.0 y Tláhuac 116.0. Miguel Hidalgo, 61.6.

**4. Quién decide qué es "prioritario" cambia el mapa entero.** Ponderar la
brecha por dependencia en vez de dejarla cruda mueve **76 zonas del top-50**. La
brecha cruda mide distancia física al servicio; ponderada mide a quién le duele
esa distancia. Son dos preguntas, no dos precisiones de la misma, y por eso el
visor las deja cambiar con un selector en vez de que la decidamos nosotros.

**5. Predecir dónde abrirá una farmacia es genuinamente difícil.** El modelo
acierta 10% del top-50 en cambio. Es 5 veces el azar y le gana a los tres
baselines, pero está lejos de ser preciso. Lo decimos porque el valor del
trabajo no está ahí: está en la proyección de demanda, que es aritmética de
cohortes y sí es confiable.

---

## Validación

Entrenamos solo con las transiciones que terminan en 2023 o antes. El modelo no
vio nada posterior. Después predijo 2024 y 2026.

| | Top-50 en nivel | Top-50 en cambio |
|---|---|---|
| **Modelo GLM** | 0.68 | **0.10** |
| Baseline sin cambio | **0.92** | 0.08 |
| Baseline tendencia lineal | 0.72 | 0.04 |
| Baseline crecimiento poblacional | 0.68 | 0.02 |

**Por qué se reportan las dos columnas.** En nivel nos gana el baseline de
suponer que nada cambia. Eso no significa que ese baseline prediga bien:
significa que el conteo casi no se mueve entre cortes. La pregunta del reto es
dónde va a *cambiar* la demanda, y en esa columna el modelo le gana a los tres.
Preferimos enseñar ambas y decir en cuál perdemos.

Otras verificaciones:

- **Validación cruzada espacial:** dejando fuera alcaldías completas (no zonas al
  azar, que produciría fuga espacial), Spearman promedio fuera de muestra 0.919.
- **Incertidumbre:** intervalo conforme al 80% nominal, cobertura observada
  75.8%. La diferencia no es un error: la predicción conforme garantiza cobertura
  bajo intercambiabilidad y dos periodos distintos no lo son. Esa brecha **mide**
  el desplazamiento temporal. Reportamos la observada.
- **Empate entre censos:** 99.4% de las AGEB de 2020 tienen par utilizable en 2010.
- **Verificación cruzada del cruce espacial:** la AGEB que el propio DENUE declara
  coincide con nuestro punto-en-polígono en 99.8% de 65,842 establecimientos.
- **Sensibilidad al ancho de banda:** con 500 m y 1,200 m la correlación con el
  resultado a 800 m es 0.935 y 0.968. El ordenamiento de zonas es estable.

---

## Fuentes

| Fuente | Institución | Nivel | Años |
|---|---|---|---|
| Censo de Población y Vivienda, resultados por AGEB y manzana urbana | INEGI | AGEB | 2010, 2020 |
| DENUE, 11 ediciones | INEGI | punto georreferenciado | 2016–2026 |
| Marco Geoestadístico, 6 añadas | INEGI | AGEB | 2020–2025 |
| Grado de Rezago Social por AGEB urbana | CONEVAL | AGEB | 2020 |
| Proyecciones de población | CONAPO | entidad | 2020–2030 |

**Diferencias que hay que tener presentes.** La demografía por AGEB solo existe
para 2010 y 2020: las encuestas intercensales de 2015 y 2025 son municipales. El
detalle por grupos quinquenales de edad no existe a nivel AGEB, solo a nivel
alcaldía. Los once cortes del DENUE no están espaciados parejo.

**Transiciones excluidas del entrenamiento:** `2019→2020` y `2024→2025`. Entre
esos cortes varias clases saltan sin que haya aperturas o cierres reales, muy
probablemente por cambio de versión del catálogo SCIAN.

---

## Clases SCIAN

**Oferta** (lo que cuenta como capacidad instalada):

| Clave | Nombre |
|---|---|
| 464111 | Farmacias sin minisúper |
| 464112 | Farmacias con minisúper |
| 621111 | Consultorios de medicina general, sector privado |
| 621115 | Clínicas de consultorios médicos, sector privado |

Los consultorios adyacentes a farmacia **no** se clasifican en 464 sino en la
rama 6211. Contar solo 464 mide venta de medicamento, no capacidad de atención.

**Contexto** (covariables, no oferta): 464113, 462111, 462112, 461110, 623311,
621113, 621511, 465111, 464121, 464122.

---

## Supuestos de mercado

Los límites de abajo son de **datos y método**. Éstos son de **comportamiento
del consumidor**, que es distinto: no se arreglan con mejores datos del INEGI,
se arreglan con datos de mercado que hoy no son públicos. Los tres son falsos y
se asumen a propósito para esta primera versión.

| Supuesto | Por qué es falso | Qué haríamos |
|---|---|---|
| Mercado simplificado y distancias uniformes | El precio, las promociones y el surtido varían entre cadenas | Incorporar precio relativo por cadena |
| Cliente perfecto: cada quien va a la farmacia más cercana | La gente va a la de su programa de lealtad, o a la que más se anuncia | Ponderar por participación de mercado |
| Más oferta implica más atención | Dos farmacias a la misma distancia no atienden igual | Datos de tráfico o de consumo |

Un modelo que no declara sus supuestos no se puede criticar, y uno que no se
puede criticar no sirve para decidir.

---

## Sobre la cobertura del mercado

Farmacias Similares es de Fundación Best y **no** pertenece a la ANTAD, que
agrupa a Ahorro, Guadalajara y Benavides. Aun así se cuenta, porque compite por
el mismo cliente: lo que medimos es **capacidad instalada del mercado**, no
participación de ANTAD.

---

## Límites

- Con dos censos hay un solo incremento por zona. No es una tendencia ajustada,
  es una diferencia. Con dos puntos no se estima una recta.
- El ancho de banda de 800 m usa distancia en línea recta, no rutas caminando.
- El DENUE no cubre la informalidad.
- **El censo 2020 se levantó durante la pandemia y no corregimos ese sesgo.**
  Afecta menos de lo que parece por dos razones: del censo no usamos el nivel
  absoluto sino la *estructura de edad relativa* de cada zona, y un subconteo
  parejo dentro de una AGEB casi no mueve esa proporción; y el total de control
  de la ciudad no viene del censo sino de CONAPO, así que un error de nivel no
  se propaga a la proyección. El Marco Geoestadístico 2020–2025 nos da geometría,
  no demografía: no corrige esto y no lo presentamos como si lo hiciera.
- El archivo municipal de CONAPO no estuvo disponible (servidor caído). Se usó la
  cifra publicada a nivel entidad, repartida en dos pasos.
- La proyección supone permanencia residencial.

---

## Reproducibilidad

Los datos crudos (~600 MB) no se versionan. Para reproducir desde cero, baja:

- Censo 2020 y 2010 por AGEB, entidad 09 → `datos/crudos/`
- DENUE, ediciones 2016–2026 de CDMX → filtrar con `scripts/01_filtrar_denue.py`
- Marco Geoestadístico, entidad 09 → `datos/crudos/mg/`
- CONEVAL, Grado de Rezago Social por AGEB urbana 2020

Lo que sí se versiona es `datos/procesados/`, así que el visor se puede
regenerar sin volver a bajar nada.

---

## Roadmap

Lo que haríamos con más tiempo, priorizado, está en [`ROADMAP.md`](ROADMAP.md).
