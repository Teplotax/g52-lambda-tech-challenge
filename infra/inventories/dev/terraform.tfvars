environment   = "dev"
function_name = "g52-lambda-auth"
aws_region    = "us-east-1"
destroy       = false

# JWT
jwt_issuer      = "g52-lambda-auth"
jwt_audience    = "tech-challenge-api"
jwt_ttl_seconds = 3600

# Banco de dados gerenciado: preencher com os outputs do repositório de infra do banco
db_host       = ""
db_port       = 5432
db_name       = "techchallenge"
db_secret_arn = ""
db_ssl        = true

# Rede: subnets privadas da VPC do RDS (vazio = Lambda fora da VPC)
vpc_id                         = "vpc-0c0fcb0a0221f6d85"
subnet_ids                     = []
create_secretsmanager_endpoint = false

log_retention_days = 7
