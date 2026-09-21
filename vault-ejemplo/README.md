# Vault de ejemplo

Contenido de ejemplo para probar el pipeline de RAG, no para uso en producción.

`recursos.md` y `productos.md` describen el caso ficticio TechChip Systems S.A.
Sirven para ejercitar el indexador y la búsqueda semántica. AgentA no trae este
negocio precargado: cada despliegue escribe su propia base en `vault/`.

Este directorio no lo recorre el indexador por defecto ni el workflow de GitHub
(solo observan `vault/`). Para probarlo en un entorno de desarrollo:

```bash
cd backend
python scripts/index_vault.py --vault ../vault-ejemplo
```

Ese comando trata la carpeta como el corpus completo: escribe estos chunks en
`knowledge_chunks` y elimina las rutas que no estén en ella. No lo corras contra
la base de un despliegue que ya tenga su propio conocimiento.
