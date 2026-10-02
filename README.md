# g52-lambda-tech-challenge

Function Serverless (AWS Lambda, Python 3.12) de **autenticação por CPF** do Tech Challenge — Grupo 52.

A função:

1. **Valida o CPF** informado (formato e dígitos verificadores);
2. **Consulta o cliente** na tabela `clientes` do PostgreSQL gerenciado (existência e status);
3. **Gera e devolve um JWT** (RS256) para consumo das APIs protegidas da aplicação principal.

A chave pública de validação do token é publicada em formato **JWKS**. Assim, a aplicação Spring Boot valida os tokens sem compartilhar segredos.

O mesmo pacote também traz o **Lambda Authorizer** (`authorizer.lambda_handler`). É uma segunda função, do tipo TOKEN, que o API Gateway chama antes de encaminhar as rotas protegidas: ela valida a assinatura, a expiração, o emissor e a audiência do JWT e responde `401` quando o token for inválido.

## Arquitetura

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant GW as API Gateway
    participant L as Lambda g52-lambda-auth
    participant DB as RDS PostgreSQL
    participant APP as App (EKS)

    C->>GW: POST /auth {"cpf": "..."}
    GW->>L: AWS_PROXY
    L->>L: valida CPF
    L->>DB: SELECT ... FROM clientes WHERE documento = :cpf
    DB-->>L: cliente
    L-->>GW: 200 {access_token, token_type, expires_in}
    GW-->>C: JWT

    participant AZ as Lambda Authorizer
    C->>GW: GET /ordensDeServico (Authorization: Bearer JWT)
    GW->>AZ: valida JWT (resultado em cache por 5 min)
    AZ-->>GW: policy Allow (ou 401)
    GW->>APP: encaminha
    APP->>GW: GET /.well-known/jwks.json (cacheado)
    APP-->>C: resposta da API protegida
```

```
                      ┌──────────────── VPC (subnets do RDS) ────────────────┐
API Gateway ──invoke──▶ Lambda (python3.12) ──5432/TLS──▶ RDS PostgreSQL     │
                      │   SG lambda + SG g52-rds-tech-challenge-clients      │
                      └──────────────────────────────────────────────────────┘
                             └─────────▶ CloudWatch Logs (JSON estruturado)
```

A função roda na VPC do RDS para alcançar o banco privado. Essas subnets não têm NAT, então a função não consegue chamar o Secrets Manager em runtime. Por isso a chave privada do JWT e as credenciais do banco chegam por variável de ambiente, que a Lambda guarda criptografada em repouso com KMS. O Terraform lê as credenciais do secret `g52-rds-tech-challenge/credentials` no deploy.

## Contrato

### `POST /auth`

```json
{ "cpf": "555.632.710-64" }
```

| Status | Quando | Corpo |
|---|---|---|
| `200` | Cliente encontrado e habilitado | `{"access_token": "<jwt>", "token_type": "Bearer", "expires_in": 3600}` |
| `400` | Corpo inválido ou CPF inválido | `{"message": "CPF inválido", "exceptionType": "BadRequest"}` |
| `401` | CPF não cadastrado | `{"message": "Cliente não encontrado", "exceptionType": "Unauthorized"}` |
| `403` | Cliente não habilitado para autenticar por CPF (`tipo_documento` ≠ `CPF`) | `{"message": "...", "exceptionType": "Forbidden"}` |
| `503` | Banco indisponível ou não configurado | `{"message": "...", "exceptionType": "ServiceUnavailable"}` |

Os erros seguem o `ErrorMessage` do contrato da API (`g52-api-tech-challenge-v1-ext`).

Claims do token:

| Claim | Valor |
|---|---|
| `sub` | id do cliente |
| `cpf` | CPF (somente dígitos) |
| `name` | nome social (ou nome) |
| `email` | e-mail do cliente |
| `roles` | `["CLIENTE"]` |
| `iss` / `aud` | `g52-lambda-auth` / `tech-challenge-api` (configuráveis) |
| `iat` / `nbf` / `exp` | emissão e expiração (padrão: 1h) |

O header do token traz o `kid` (thumbprint RFC 7638 da chave pública).

### `GET /.well-known/jwks.json`

Retorna a chave pública RS256 (`{"keys": [{"kty": "RSA", "kid": "...", "n": "...", "e": "AQAB", ...}]}`).

### Correlation ID

Se o header `x-correlationid` vier na requisição, ele é propagado. Caso contrário, a função gera um. O valor volta no header de resposta e aparece em todos os logs, que são JSON estruturado com o CPF mascarado.

## Tecnologias

- Python 3.12 (AWS Lambda), `pg8000` (driver PostgreSQL puro Python), `PyJWT` + `cryptography`
- AWS Lambda, RDS PostgreSQL, CloudWatch Logs, IAM, VPC
- Terraform (state no S3 `g52-terraform-state-dev-<account>`)
- GitHub Actions com OIDC (role `github-actions-terraform-dev`)

## Estrutura

```
src/
  handler.py          # entrypoint (handler.lambda_handler) e roteamento
  authorizer.py       # Lambda Authorizer (authorizer.lambda_handler)
  auth/
    cpf.py            # validação de CPF
    service.py        # regras de autenticação
    repository.py     # consulta de clientes no PostgreSQL
    tokens.py         # JWT RS256 + JWKS
    logger.py         # logs JSON
    http.py           # utilitários de evento/resposta do API Gateway
    config.py         # variáveis de ambiente
tests/                # pytest
scripts/build.sh      # gera ./build (código + dependências linux x86_64)
infra/                # Terraform
```

## Execução local

```bash
python -m venv .venv
. .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -v
```

Para gerar o pacote da Lambda (o mesmo usado pelo pipeline), rode `sh scripts/build.sh`.

## Infraestrutura (Terraform)

| Recurso | Descrição |
|---|---|
| `aws_lambda_function.auth` | Função `python3.12`, handler `handler.lambda_handler` |
| `tls_private_key.jwt` | Chave RSA 2048 de assinatura do JWT (fica só no state do Terraform e na env da função) |
| `data.aws_db_instance` / `data.aws_secretsmanager_secret_version` / `data.aws_db_subnet_group` | Endpoint, credenciais e subnets do RDS (repositório `g52-infra-rds-tech-challenge`) |
| `aws_iam_role.lambda` | Execução básica e acesso à VPC |
| `aws_cloudwatch_log_group.lambda` | Logs com retenção configurável |
| `aws_security_group.lambda` | SG da função (saída liberada). A função também anexa o SG `g52-rds-tech-challenge-clients`, o único aceito pelo RDS |
| `aws_lambda_permission.api_gateway` | Permite que o API Gateway invoque a função |
| `aws_lambda_function.authorizer` | `g52-lambda-auth-authorizer`, handler `authorizer.lambda_handler`, recebe a chave pública por variável de ambiente (sem acesso a segredos ou ao banco, fora da VPC) |
| `aws_iam_role.authorizer` | Somente execução básica (logs) |

### Variáveis (`infra/inventories/dev/terraform.tfvars`)

| Variável | Descrição |
|---|---|
| `function_name` | Nome da função; também compõe a key do state |
| `db_identifier` | Identificador do RDS. A partir dele o Terraform encontra o endpoint, o secret `<id>/credentials`, as subnets e o SG `<id>-clients` |
| `db_ssl` | Conexão TLS verificada com o CA bundle do RDS (incluído no pacote pelo build) |
| `jwt_issuer`, `jwt_audience`, `jwt_ttl_seconds` | Parâmetros do token |
| `destroy` | `true` faz o pipeline executar `terraform destroy` |

O RDS precisa existir antes do deploy desta função, porque o `terraform plan` lê os dados dele.

### Outputs

| Output | Uso |
|---|---|
| `invoke_arn` | Integração `AWS_PROXY` no API Gateway (`POST /auth`, `GET /.well-known/jwks.json`) |
| `function_name` / `function_arn` | Referência da função |
| `security_group_id` | SG da função |
| `authorizer_function_name` / `authorizer_invoke_arn` | Authorizer referenciado no `securitySchemes` do contrato OpenAPI |

## Pipeline CI/CD

```
feature/** -> develop -> release/vX.X.X -> main
```

| Workflow | Gatilho | Ação |
|---|---|---|
| `1-feature-to-dev.yml` | Push em `feature/**` | Abre PR automático para `develop` |
| `2-dev-to-release.yml` | Push/PR em `develop` | Testes (pytest), build do pacote, `terraform plan` (PR) ou `apply/destroy` (push), smoke test do JWKS; cria branch e PR `release/vX.X.X` |
| `4-release-to-main.yml` | PR fechado em `release/**` | Abre PR automático da release para `main` |

A autenticação com a AWS é feita via **OIDC** com o role `github-actions-terraform-dev`. A única configuração do repositório é a variável `AWS_ACCOUNT_ID`.

## Testando o deploy

```bash
aws lambda invoke --function-name g52-lambda-auth \
  --cli-binary-format raw-in-base64-out \
  --payload '{"httpMethod":"POST","path":"/auth","headers":{},"body":"{\"cpf\":\"55563271064\"}"}' \
  response.json && cat response.json
```
