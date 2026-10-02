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

  in_vpc = length(var.subnet_ids) > 0

  readable_secret_arns = compact([
    aws_secretsmanager_secret.jwt_signing_key.arn,
    var.db_secret_arn,
  ])
}
