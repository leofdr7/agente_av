# Identidades para el despliegue AWS

Cuenta `964862484349`, región `us-east-2`.

La cuenta root tiene MFA activo y no tiene access keys. Su sesión CLI local se
cerró después de validar el perfil IAM; las siguientes operaciones deben usar
`--profile agenta-operator` o el rol OIDC de GitHub Actions.

## GitHub Actions

`agenta-deploy-role` confía solo en el proveedor IAM
`token.actions.githubusercontent.com` con audiencia `sts.amazonaws.com`. Su
[trust policy](agenta-deploy-trust.json) exige el repositorio
`leofdr7/agente_av` (owner ID `261961715`, repository ID `1372394791`),
`refs/heads/main` y el entorno `production`. El repositorio fue creado después
del cambio de formato de `sub` de GitHub en julio de 2026; por eso el valor
incluye los IDs inmutables. El entorno de GitHub también limita despliegues a
`main`.

La [política de despliegue](agenta-deploy-permissions.json) permite publicar en
`agenta-backend` de ECR y registrar revisiones de la familia
`default-agenta-backend-smoke`. ECS Express Mode se despliega con
`UpdateExpressGatewayService`, limitado a
`service/default/agenta-backend-smoke` y a esa familia de task definitions.
`iam:PassRole` solo acepta `ecsTaskExecutionRole` hacia `ecs-tasks.amazonaws.com`.

## Secretos previstos

Los permisos de Secrets Manager se limitan a estos nombres bajo
`agenta/production/`:

- `ANTHROPIC_API_KEY`
- `SUPABASE_SERVICE_KEY`
- `CLERK_SECRET_KEY`
- `OPENAI_API_KEY`

IAM añade un sufijo aleatorio de seis caracteres al ARN de cada secreto. Las
políticas de despliegue y alta usan seis `?` para ese sufijo antes de conocerlo;
la [política de ejecución](agenta-task-execution-secrets.json) contiene los
cuatro ARN exactos creados en AWS-3. OpenAI se confirmó como proveedor de
embeddings antes de crear secretos. Ninguna política contiene valores de
secreto. La política de ejecución concede lectura a `ecsTaskExecutionRole`
para que ECS pueda resolver futuras referencias `valueFrom`; no cambia la task
definition actual.

## Operación manual

El usuario IAM personal `leofdr7` usa el perfil local `agenta-operator`, ya
cambió su contraseña inicial y registró MFA. Tiene adjunta la política
administrada `agenta-deploy-limited`, la misma que el rol OIDC. Su
[política de autoservicio](agenta-operator-self-service.json) solo permite
cambiar su contraseña y configurar su MFA. No se usan access keys permanentes.
La [política de inicio de sesión de CLI](agenta-operator-cli-signin.json)
autoriza los dos permisos OAuth requeridos por `aws login`, solo para el cliente
local en esta cuenta y región.

La [política propuesta para dar de alta secretos](agenta-operator-secrets-bootstrap.json)
no se adjuntó en AWS-1. La revisión automática rechazó conceder permisos
persistentes para crear y cargar secretos de producción; esa necesidad se
resuelve en AWS-3 con permisos temporales.

## AWS-3: carga interactiva de secretos

Tras confirmar OpenAI como proveedor de embeddings de producción, se adjunta
temporalmente al usuario IAM `leofdr7` la
[política de AWS-3](agenta-operator-aws3-temporary.json). En esta cuenta no hay
otra identidad administradora; el usuario autorizó una excepción para que root
solo adjunte y retire esta política. La carga de secretos y la política de
`ecsTaskExecutionRole` siguen usando `agenta-operator`. Esta política concede alta
solo para los cuatro nombres previstos, `ListSecrets` para la validación y
`PutRolePolicy`/`GetRolePolicy` solo sobre `ecsTaskExecutionRole`. `ListSecrets`
requiere `Resource: "*"` en IAM. La política temporal debe retirarse después de
validar la fase.

En una terminal local interactiva, ejecutar desde la raíz del repositorio:

```bash
python3 infra/aws/create-production-secrets.py
```

El programa comprueba que `agenta-operator` es `user/leofdr7`, solicita las
cuatro claves con entrada oculta y envía cada valor al AWS CLI por stdin. No
coloca claves en argumentos, variables de entorno, archivos del repositorio ni
salida de consola. Exige que `SUPABASE_SERVICE_KEY` sea un JWT con rol
`service_role`; rechaza el placeholder. Si una ejecución se interrumpe, conserva
los secretos ya creados y pide solo los faltantes al reiniciar.

Después crea la política inline `agenta-production-secrets` en
`ecsTaskExecutionRole` con `secretsmanager:GetSecretValue` sobre los cuatro ARN
**exactos** devueltos por AWS. Verifica el resultado con `list-secrets` y
`get-role-policy`. `ListSecrets` puede tardar hasta cinco minutos en mostrar
altas recientes, por lo que el programa espera y reintenta. No actualiza la
task definition ni su `SUPABASE_URL`; eso
requiere cambiar las referencias `valueFrom` y la URL pública en la fase de
despliegue posterior.

La validación de AWS-3 confirmó cuatro secretos y una sola acción
`secretsmanager:GetSecretValue` sobre sus ARN exactos. Después se retiró la
política temporal `agenta-aws3-temporary` de `leofdr7` y se cerró la sesión
CLI root. Las únicas políticas inline restantes del usuario son la de
autoservicio y la de inicio de sesión CLI.

## Corrección de valores existentes

Para sustituir las cuatro claves sin cambiar sus ARN, se adjunta de forma
temporal la [política de rotación](agenta-operator-aws3-rotate-temporary.json) a
`leofdr7`. Esta concede solo `secretsmanager:PutSecretValue` sobre los cuatro
ARN exactos. En la terminal local se ejecuta:

```bash
python3 infra/aws/create-production-secrets.py --rotate
```

Cada valor se pide dos veces con entrada oculta y se envía al AWS CLI por stdin.
El programa comprueba por metadatos que cada nueva versión tenga la etiqueta
`AWSCURRENT`; no lee ni imprime valores existentes. Al terminar se retira la
política temporal y se cierra la sesión CLI root usada para concederla.

La corrección de las cuatro claves terminó con versiones nuevas `AWSCURRENT`.
Se confirmó que `agenta-aws3-rotate-temporary` ya no está adjunta a `leofdr7` y
se cerró la sesión CLI root.

Para validar la identidad en la terminal, tras `aws login --profile
agenta-operator` ejecuta:

```bash
aws sts get-caller-identity --profile agenta-operator --region us-east-2
```

El ARN verificado es `arn:aws:iam::964862484349:user/leofdr7`. El rol OIDC
requiere un token emitido por un job de GitHub Actions en `main` con el entorno
`production`; su prueba positiva de `AssumeRoleWithWebIdentity` se hará cuando
el workflow apunte a ECS y pueda probarse sin publicar aún a producción.
