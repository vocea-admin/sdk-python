"""El paquete se importa en todas las versiones de Python que promete.

`pyproject.toml` declara `requires-python = ">=3.10"` y el README anuncia lo
mismo, pero `models.py` usaba la sintaxis de genéricos del PEP 695
(`class PaginatedResponse[T]`), que exige Python 3.12. En 3.10 y 3.11 el
paquete ni siquiera se importaba: `pip install vocea-sdk` funcionaba y el
primer `import vocea_sdk` moría con un `SyntaxError`.

Ningún test lo vio porque todos corrían en el intérprete del `.venv` (3.12).
Este comprueba la sintaxis contra la versión mínima *declarada*, así que caza
el problema desde cualquier intérprete: `ast.parse(..., feature_version=...)`
rechaza lo que esa versión no sabría compilar.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest


RAIZ = pathlib.Path(__file__).resolve().parent.parent
PAQUETE = RAIZ / "vocea_sdk"


def _version_minima_declarada() -> tuple[int, int]:
    """Lee `requires-python` de pyproject.toml.

    A mano y no con `tomllib`, que es de 3.11: este test tiene que poder
    correr también en la versión más vieja que el paquete dice soportar.
    """
    pyproject = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^requires-python\s*=\s*"\s*>=\s*(\d+)\.(\d+)', pyproject, re.M)
    assert match, "pyproject.toml no declara un `requires-python = \">=X.Y\"`"
    return int(match.group(1)), int(match.group(2))


FUENTES = sorted(PAQUETE.rglob("*.py"))


def test_hay_fuentes_que_revisar():
    """Centinela: si el paquete se mueve de sitio, el resto no vale nada."""
    assert FUENTES, f"no se encontró ningún .py bajo {PAQUETE}"


@pytest.mark.parametrize("fuente", FUENTES, ids=lambda p: p.name)
def test_la_sintaxis_es_valida_en_la_version_minima_soportada(fuente: pathlib.Path):
    minima = _version_minima_declarada()

    try:
        ast.parse(fuente.read_text(encoding="utf-8"), feature_version=minima)
    except SyntaxError as e:  # pragma: no cover - el mensaje es el valor del test
        version = ".".join(str(n) for n in minima)
        pytest.fail(
            f"{fuente.relative_to(RAIZ)}:{e.lineno} usa sintaxis que Python "
            f"{version} no compila ({e.msg}). O se reescribe, o se sube "
            f"`requires-python` para no prometer lo que no se cumple."
        )


def test_el_readme_anuncia_la_misma_version_minima_que_pyproject():
    """Los dos sitios donde se promete una versión tienen que decir lo mismo."""
    mayor, menor = _version_minima_declarada()
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")

    anunciadas = set(re.findall(r"Python (\d+)\.(\d+)\+", readme))
    assert anunciadas == {(str(mayor), str(menor))}, (
        f"el README anuncia {sorted(anunciadas)} y pyproject.toml "
        f">={mayor}.{menor}"
    )
