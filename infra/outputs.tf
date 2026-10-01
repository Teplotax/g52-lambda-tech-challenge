output "function_name" {
  value = aws_lambda_function.auth.function_name
}

output "function_arn" {
  value = aws_lambda_function.auth.arn
}

# Usado pelo API Gateway na integração AWS_PROXY das rotas /auth e /.well-known/jwks.json
output "invoke_arn" {
  value = aws_lambda_function.auth.invoke_arn
}

output "jwt_signing_key_secret_arn" {
  value = aws_secretsmanager_secret.jwt_signing_key.arn
}

# Liberar no security group do RDS (ingress 5432 a partir deste SG)
output "security_group_id" {
  value = local.in_vpc ? aws_security_group.lambda[0].id : null
}
