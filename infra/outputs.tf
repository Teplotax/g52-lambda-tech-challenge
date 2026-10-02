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

output "security_group_id" {
  value = aws_security_group.lambda.id
}

output "authorizer_function_name" {
  value = aws_lambda_function.authorizer.function_name
}

output "authorizer_invoke_arn" {
  value = aws_lambda_function.authorizer.invoke_arn
}

# client_secret do token admin fica nesse secret
output "admin_client_secret_name" {
  value = aws_secretsmanager_secret.admin_client.name
}
