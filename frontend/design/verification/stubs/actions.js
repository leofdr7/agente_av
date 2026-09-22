// No writes or API requests: these stubs only expose existing failure presentation.
export async function submitEstimation() {
  return { error: "Vista de verificación: el envío al agente está desactivado." };
}
export async function generateReport() {
  return { ok: false, error: "Vista de verificación: la generación de informes está desactivada." };
}
