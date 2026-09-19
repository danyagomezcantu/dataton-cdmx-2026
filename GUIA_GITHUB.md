# Cómo subirlo a GitHub y trabajar en equipo

Guía pensada para que cualquiera del equipo pueda seguirla sin saber git.

---

## Parte 1 — Subirlo (lo haces tú, una vez)

### 1. Instala git

Descarga de [git-scm.com](https://git-scm.com/download/win). Instalador
siguiente-siguiente, los valores por defecto están bien.

### 2. Crea el repositorio en GitHub

En [github.com](https://github.com) → botón verde **New** arriba a la derecha.

- **Repository name:** `dataton-cdmx-2026`
- **Description:** Recambio demográfico y atención primaria en la CDMX · Datatón ITAM 2026
- **Private.** Hasta después de la competencia. Lo puedes volver público el 22.
- **NO marques** "Add a README", "Add .gitignore" ni "Choose a license". El
  proyecto ya los trae y si GitHub crea los suyos vas a tener que resolver un
  conflicto antes de empezar.

Dale a **Create repository**.

### 3. Sube el proyecto

Abre la terminal dentro de la carpeta del proyecto y corre esto línea por línea:

```bash
git init
git add .
git commit -m "Pipeline completo, visor interactivo y datos procesados"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/dataton-cdmx-2026.git
git push -u origin main
```

Cambia `TU_USUARIO` por tu usuario de GitHub.

La primera vez te va a pedir credenciales. GitHub ya no acepta contraseña: usa
un **personal access token**. Se saca en Settings → Developer settings →
Personal access tokens → Tokens (classic) → Generate new token, marcando el
permiso `repo`. Guárdalo, solo se muestra una vez.

### 4. Invita al equipo

En el repo → **Settings** → **Collaborators** → **Add people**. Con sus usuarios
de GitHub. Les llega correo.

---

## Parte 2 — Qué se sube y qué no

El `.gitignore` ya está configurado. Esto es lo que hace:

| Carpeta | ¿Se sube? | Por qué |
|---|---|---|
| `src/`, `scripts/` | Sí | Es el código |
| `app/` | Sí | Incluye `visor.html`, el entregable |
| `datos/procesados/` | Sí | ~12 MB. Permite regenerar el visor sin bajar nada |
| `datos/crudos/` | **No** | ~600 MB. GitHub rechaza archivos de más de 100 MB |
| `salidas/` | Sí | El diagnóstico, que es chico |

Para que alguien reproduzca desde cero tiene que bajar los crudos del INEGI. Las
instrucciones están en el README. Pero para **trabajar en el visor o en la
presentación no hace falta**: con lo versionado alcanza.

---

## Parte 3 — Cómo trabaja el equipo

### Primera vez, en cada computadora

```bash
git clone https://github.com/TU_USUARIO/dataton-cdmx-2026.git
cd dataton-cdmx-2026
pip install -r requirements.txt
```

Y abren `app/visor.html` con doble clic. Ya está: no necesitan correr nada más
para ver el resultado.

### El ciclo diario

Antes de empezar a trabajar, siempre:

```bash
git pull
```

Cuando terminaron algo:

```bash
git add .
git commit -m "describe qué cambiaste"
git push
```

### La regla que evita el 90% de los problemas

**Que dos personas no editen el mismo archivo el mismo día.** Con una semana no
hay tiempo para resolver conflictos de merge. Repártanse por archivo:

| Área | Archivos | Quién |
|---|---|---|
| Interfaz del visor | `app/plantilla.html` | |
| Modelo y parámetros | `src/config.py`, `src/modelo.py` | |
| Documentación | `README.md` | |
| Presentación | fuera del repo | |

Si de todas formas sale un conflicto, la salida rápida es:

```bash
git stash          # guarda tus cambios aparte
git pull           # trae lo de los demás
git stash pop      # vuelve a poner los tuyos encima
```

### Nunca hagan esto

- `git push --force` — borra el trabajo de los demás.
- Subir `datos/crudos/`. Si ya lo hicieron sin querer y GitHub rechazó el push,
  la salida es `git rm -r --cached datos/crudos` y volver a commitear.

---

## Parte 4 — Publicar el visor en línea (opcional)

Si quieren un enlace para mandar, GitHub Pages lo hace gratis:

1. Repo → **Settings** → **Pages**
2. Source: **Deploy from a branch**, rama `main`, carpeta `/ (root)`
3. Save. En un par de minutos queda en
   `https://TU_USUARIO.github.io/dataton-cdmx-2026/app/visor.html`

**Pero el repo tiene que ser público para eso.** No lo hagan antes del 21.

Y ojo: **el día de la competencia no dependan del enlace.** Abran el archivo
local. Si el wifi del auditorio falla, el archivo local funciona igual porque no
carga nada de internet.

---

## Parte 5 — Qué llevar el día de la presentación

1. `app/visor.html` **en el escritorio de la laptop**, no en Descargas ni en la
   nube. Un solo archivo, 1.6 MB.
2. El mismo archivo en una **memoria USB**.
3. El mismo archivo **enviado por correo a ustedes mismos**, como tercer respaldo.
4. Ábranlo una vez **antes** de subir al escenario, para que el navegador ya lo
   tenga en caché.

El visor no hace ninguna llamada a internet: ni mapas base, ni fuentes tipográficas,
ni librerías externas. Todo está adentro del archivo. Es a prueba de wifi caído.

---

## Comandos de emergencia

**"Hice un desastre y quiero volver a como estaba"**

```bash
git checkout -- .          # descarta cambios no commiteados
```

**"Quiero ver qué cambié"**

```bash
git status                 # qué archivos tocaste
git diff                   # exactamente qué líneas
```

**"Alguien rompió algo y quiero volver a la versión de ayer"**

```bash
git log --oneline          # lista de commits, copia el código del que quieras
git checkout CODIGO -- .   # trae esa versión
```

**"El push me rechaza"**

Casi siempre es que alguien subió algo antes que tú:

```bash
git pull
git push
```
