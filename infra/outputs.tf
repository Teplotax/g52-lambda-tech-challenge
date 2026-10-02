output "function_name" {
  value = aws_lambda_function.auth.function_name
}

output "function_arn" {
  value = aws_lambda_function.auth.arn
}

# usado no contrato do gateway
output "invoke_arn" {
  value = aws_lambda_function.auth.invoke_arn
}

output "jwt_signing_key_secret_arn" {
  value = aws_secretsmanager_secret.jwt_signing_key.arn
}

# liberar 5432 no sg do rds
output "security_group_id" {
  value = local.in_vpc ? aws_security_group.lambda[0].id : null
}

output "authorizer_function_name" {
  value = aws_lambda_function.authorizer.function_name
}

output "authorizer_invoke_arn" {
  value = aws_lambda_function.authorizer.invoke_arn
}
