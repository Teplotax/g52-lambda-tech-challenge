environment   = "dev"
function_name = "g52-lambda-auth"
aws_region    = "us-east-1"
destroy       = true

# jwt
jwt_issuer      = "g52-lambda-auth"
jwt_audience    = "tech-challenge-api"
jwt_ttl_seconds = 3600

# banco (endpoint, credenciais, subnets e sg vêm do rds)
db_identifier = "g52-rds-tech-challenge"
db_ssl        = true

log_retention_days = 7
