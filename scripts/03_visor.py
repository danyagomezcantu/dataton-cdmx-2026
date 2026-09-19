"""
Arma el visor en dos versiones a partir de app/plantilla.html.

  app/index.html    carga datos.js de la misma carpeta. Editable, mas comodo
                    para trabajar en equipo.
  app/aplicacion_interactiva.html
                    con los datos incrustados. UN SOLO ARCHIVO. Se manda por
                    correo, se abre con doble clic, funciona sin internet y sin
                    servidor. Esta es la version que se lleva al escenario.

Uso:  python scripts/03_visor.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config as cfg  # noqa: E402


def main():
    plantilla = (cfg.APP / "plantilla.html").read_text(encoding="utf-8")
    datos = (cfg.APP / "datos.js").read_text(encoding="utf-8")

    marca = "<script>/*DATOS*/</script>"
    if marca not in plantilla:
        raise SystemExit("La plantilla perdio la marca /*DATOS*/")

    # version con archivo aparte
    (cfg.APP / "index.html").write_text(
        plantilla.replace(marca, '<script src="datos.js"></script>'),
        encoding="utf-8")

    # version de un solo archivo
    unico = plantilla.replace(marca, "<script>\n" + datos + "\n</script>")
    (cfg.APP / "aplicacion_interactiva.html").write_text(unico, encoding="utf-8")
    # el nombre viejo ya no se genera; si quedo de una corrida anterior, se va
    viejo = cfg.APP / "visor.html"
    if viejo.exists():
        viejo.unlink()

    for f in ("index.html", "aplicacion_interactiva.html", "datos.js"):
        p = cfg.APP / f
        print(f"  {f:<14} {p.stat().st_size/1e6:6.2f} MB")
    print("\n  aplicacion_interactiva.html es la que se lleva a la "
          "presentacion: doble clic, sin internet, sin servidor.")


if __name__ == "__main__":
    main()
