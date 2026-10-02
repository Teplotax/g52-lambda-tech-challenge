variable "function_name" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type = string
}

variable "destroy" {
  type    = bool
  default = false
}

# lambda
variable "memory_size" {
  type    = number
  default = 256
}

variable "timeout" {
  type    = number
  default = 10
}

variable "log_retention_days" {
  type    = number
  default = 7
}

# jwt
variable "jwt_issuer" {
  type    = string
  default = "g52-lambda-auth"
}

variable "jwt_audience" {
  type    = string
  default = "tech-challenge-api"
}

variable "jwt_ttl_seconds" {
  type    = number
  default = 3600
}

# banco
variable "db_host" {
  type        = string
  default     = ""
  description = "Endpoint do RDS. Vazio enquanto o banco gerenciado não existir (a função responde 503)."
}

variable "db_port" {
  type    = number
  default = 5432
}

variable "db_name" {
  type    = string
  default = "techchallenge"
}

variable "db_secret_arn" {
  type        = string
  default     = ""
  description = "ARN do segredo com as credenciais do banco no formato {\"username\", \"password\"} (padrão do RDS managed master password)."
}

variable "db_ssl" {
  type    = bool
  default = true
}

# rede
variable "vpc_id" {
  type    = string
  default = ""
}

variable "subnet_ids" {
  type    = list(string)
  default = []
}

variable "create_secretsmanager_endpoint" {
  type        = bool
  default     = false
  description = "Cria VPC endpoint do Secrets Manager. Necessário quando as subnets da Lambda não têm saída para a internet (NAT)."
}
