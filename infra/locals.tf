locals {
  project = "tech-challenge"
  squad   = "grupo-52"
  sigla   = "g52"

  common_tags = {
    environment = var.environment
    squad       = local.squad
    sigla       = local.sigla
    project     = local.project
  }

  function_tags = merge(local.common_tags, {
    resource = "lambda"
    service  = var.function_name
  })

  authorizer_name = "${var.function_name}-authorizer"

  db_credentials = jsondecode(data.aws_secretsmanager_secret_version.db.secret_string)
}
