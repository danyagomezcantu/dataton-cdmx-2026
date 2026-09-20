# Roadmap — I.D.A.P.

**I.D.A.P.** es el Índice de Demanda de Atención Primaria: el número que esta aplicación calcula para cada zona de la CDMX.

Lo que haríamos con un mes y medio más, en este orden. No es lo que *se puede*
hacer: es lo que *vamos a* hacer.

---

## 1 · Perfeccionar los datos

**Umbral de viabilidad comercial de una farmacia.** Hoy la brecha se lee en
"personas por unidad de servicio alcanzable". Falta el dato que la convierte en
decisión de negocio: cuántas visitas o cuántos clientes al año necesita un
establecimiento para sostenerse. Con eso, la cadena es directa:

```
visitas anuales de la zona   = población × visitas por persona al año
farmacias que soporta la zona = visitas anuales / umbral de viabilidad
```

y la brecha pasa a decir **faltan N farmacias aquí**.

**Nombres de colonia completos.** Hoy 102 de 2,431 zonas se nombran por
vecindad porque no tienen ningún negocio adentro. Con el catálogo oficial de
asentamientos de la CDMX quedarían todas con nombre propio.

**Densidad de población como señal de demanda.** Hoy la densidad entra como
covariable del modelo de oferta, pero su *evolución* 2010→2020 no se usa como
señal de demanda futura. Una zona que gana población gana demanda.

## 2 · La brecha en unidades de negocio

Consecuencia directa del punto 1. Cambia la unidad de todo el entregable, de un
índice a un número de establecimientos, que es como decide un socio de ANTAD.

## 3 · Dos perfiles en el portal

La aplicación está pensada para colgarse en un portal público, y por eso no usa
un solo término técnico. Falta la otra vista: un perfil técnico con el panel de
diagnóstico, los coeficientes del modelo y las métricas de validación sin
traducir.

En el mismo paso, **migración del mapa a Leaflet con mapa base**, para zoom,
arrastre y calles de referencia. Ver la nota de decisión abajo.

## 4 · Capa de saturación, ampliada

Ya existe como capa ("dónde NO abrir"), pero es binaria. Falta graduarla: cuánta
sobreoferta hay, y a qué distancia está la competencia relevante.

## 5 · Ida, el conector a un LLM

Consulta en lenguaje natural sobre el mapa, y redacción automática de las
tarjetas de recomendación. **Va al final a propósito:** es deseable, no
indispensable, y preferimos que los datos estén bien antes de ponerle una capa
de conversación encima.

**Se llamará Ida**, por el nombre del proyecto. La idea es que en lugar de
aprender a usar los selectores, cualquiera pueda escribir *"¿dónde conviene
abrir en Iztapalapa en tres años?"* y obtener la respuesta con su justificación.

Ida no aparece todavía en la aplicación, y aparece aquí a propósito: es un
compromiso del siguiente mes, no una función que ya exista.

> **Para que no se confundan los dos nombres:** *I.D.A.P.* es el índice, o sea
> el número que la aplicación calcula para cada zona. *Ida* será el asistente
> con el que se le va a poder preguntar por ese número en voz normal.

---

## Decisión registrada: por qué no Leaflet todavía

Leaflet es el estándar para mapas interactivos en web y es a donde vamos. No se
usó en esta versión por una razón concreta: la aplicación es **un archivo que
abre con doble clic y no hace una sola llamada a la red**, para que funcione
aunque no haya wifi el día de la presentación.

| Opción | Qué gana | Qué cuesta |
|---|---|---|
| **SVG propio, sin red** ← esta versión | Cero dependencias, cero riesgo en el escenario | Zoom menos fluido, sin calles de referencia |
| Leaflet sin mapa base | Zoom y arrastre nativos, sigue sin red | Se pierde el contexto de calles |
| **Leaflet con mapa base** ← paso 3 | La experiencia que la gente espera | Depende de conexión |

El zoom propio del mapa (rueda del ratón y botones) ya está implementado sobre
el SVG, así que la carencia real que queda es el mapa base.
