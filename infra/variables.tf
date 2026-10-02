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

# banco, lido do repo g52-infra-rds-tech-challenge
variable "db_identifier" {
  type = string
}

variable "db_ssl" {
  type    = bool
  default = true
}
