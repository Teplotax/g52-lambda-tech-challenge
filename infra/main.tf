data "aws_caller_identity" "current" {}

# chave do jwt, a privada fica no secrets manager
resource "tls_private_key" "jwt" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "aws_secretsmanager_secret" "jwt_signing_key" {
  name                    = "${var.function_name}/jwt-signing-key"
  description             = "Chave privada RS256 usada pela ${var.function_name} para assinar os JWT"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "jwt_signing_key" {
  secret_id     = aws_secretsmanager_secret.jwt_signing_key.id
  secret_string = tls_private_key.jwt.private_key_pem
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.function_name}-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

resource "aws_iam_role_policy_attachment" "basic_execution" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "vpc_access" {
  count      = local.in_vpc ? 1 : 0
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

data "aws_iam_policy_document" "secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = local.readable_secret_arns
  }
}

resource "aws_iam_role_policy" "secrets" {
  name   = "${var.function_name}-secrets"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.secrets.json
}

# só cria se tiver subnet (lambda na vpc do rds)
resource "aws_security_group" "lambda" {
  count       = local.in_vpc ? 1 : 0
  name        = "${var.function_name}-sg"
  description = "Lambda de autenticacao por CPF"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "secretsmanager_endpoint" {
  count       = local.in_vpc && var.create_secretsmanager_endpoint ? 1 : 0
  name        = "${var.function_name}-secretsmanager-endpoint-sg"
  description = "HTTPS da Lambda para o endpoint do Secrets Manager"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda[0].id]
  }
}

resource "aws_vpc_endpoint" "secretsmanager" {
  count               = local.in_vpc && var.create_secretsmanager_endpoint ? 1 : 0
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.subnet_ids
  security_group_ids  = [aws_security_group.secretsmanager_endpoint[0].id]
  private_dns_enabled = true
}

# ../build é gerado pelo scripts/build.sh
data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../build"
  output_path = "${path.module}/../dist/lambda.zip"
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "auth" {
  function_name    = var.function_name
  description      = "Autenticacao por CPF: valida o CPF, consulta o cliente e emite JWT"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  architectures    = ["x86_64"]
  handler          = "handler.lambda_handler"
  memory_size      = var.memory_size
  timeout          = var.timeout
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  environment {
    variables = {
      SERVICE_NAME    = var.function_name
      DB_HOST         = var.db_host
      DB_PORT         = tostring(var.db_port)
      DB_NAME         = var.db_name
      DB_SECRET_ARN   = var.db_secret_arn
      DB_SSL          = tostring(var.db_ssl)
      JWT_SECRET_ARN  = aws_secretsmanager_secret.jwt_signing_key.arn
      JWT_ISSUER      = var.jwt_issuer
      JWT_AUDIENCE    = var.jwt_audience
      JWT_TTL_SECONDS = tostring(var.jwt_ttl_seconds)
    }
  }

  dynamic "vpc_config" {
    for_each = local.in_vpc ? [1] : []
    content {
      subnet_ids         = var.subnet_ids
      security_group_ids = [aws_security_group.lambda[0].id]
    }
  }

  tags = local.function_tags

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy_attachment.basic_execution,
    aws_iam_role_policy_attachment.vpc_access,
    aws_secretsmanager_secret_version.jwt_signing_key,
  ]
}

# integração fica no repo do gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*/*/*"
}

# authorizer, mesmo zip, só precisa da chave pública
resource "aws_iam_role" "authorizer" {
  name               = "${local.authorizer_name}-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

resource "aws_iam_role_policy_attachment" "authorizer_basic_execution" {
  role       = aws_iam_role.authorizer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "authorizer" {
  name              = "/aws/lambda/${local.authorizer_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "authorizer" {
  function_name    = local.authorizer_name
  description      = "Lambda Authorizer: valida o JWT emitido pela ${var.function_name}"
  role             = aws_iam_role.authorizer.arn
  runtime          = "python3.12"
  architectures    = ["x86_64"]
  handler          = "authorizer.lambda_handler"
  memory_size      = 128
  timeout          = 5
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  environment {
    variables = {
      SERVICE_NAME       = local.authorizer_name
      JWT_PUBLIC_KEY_PEM = tls_private_key.jwt.public_key_pem
      JWT_ISSUER         = var.jwt_issuer
      JWT_AUDIENCE       = var.jwt_audience
    }
  }

  tags = merge(local.function_tags, { service = local.authorizer_name })

  depends_on = [
    aws_cloudwatch_log_group.authorizer,
    aws_iam_role_policy_attachment.authorizer_basic_execution,
  ]
}

resource "aws_lambda_permission" "authorizer_api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*/*"
}
