# Reglas del proyecto

Estas reglas aplican a cualquier persona o agente que modifique este repositorio.

## Agentes

- Los agentes van en `src/{nombre_agente}/` y cada uno contiene `graph.py`, `prompts.py` y `tools.py`.
- Cada nodo del grafo tiene su propio prompt en `prompts.py`. No se escriben reglas ni instrucciones dentro de `graph.py`; ahí solo va la construcción del grafo y la lógica de orquestación.

## Ejecución

- Se ejecutan desde la raíz del proyecto:
  - `python main.py {nombre_agente} "mensaje"`
  - `python main.py {nombre_agente} "mensaje" --saltos` imprime los nodos por los que pasó el grafo.
  - `python main.py {nombre_agente} --diagrama` imprime el Mermaid del grafo sin ejecutarlo.

## API

- La API va en `api/app.py` (FastAPI) y se levanta con:
  - `uvicorn api.app:app --reload --port 8000`

## Scripts y pruebas

- Los scripts sueltos van en `scripts/`.
- Las pruebas van en `tests/` y se ejecutan con `pytest`.

## Despliegue

- `railway.toml` es la única configuración de despliegue.
- No se crean `Procfile`, `Dockerfile`, `nixpacks.toml` ni `railway.json`.
- El puerto se toma siempre de `$PORT`; no se usa un puerto fijo.
- `.python-version` debe contener `3.12` y `requirements.txt` debe estar actualizado.
- Las variables de entorno y secretos se configuran en la pestaña Variables de Railway, nunca en `railway.toml`.

## Secretos

- `.gitignore` debe incluir `.env`, `.venv`, `__pycache__` y `.langgraph_api`.
- Nunca se escriben valores reales de claves o tokens en el código. Las variables se leen del entorno y `.env.example` solo muestra los nombres.
