"""
Fixtures para tests de integración con base de datos real.

Requiere testcontainers:
  pip install testcontainers[postgres,redis]

Para correr solo tests de integración:
  pytest tests/integration/ -v
"""
import pytest

# Estos tests solo corren si testcontainers está instalado
pytest.importorskip("testcontainers", reason="testcontainers no instalado — omitiendo tests de integración")
