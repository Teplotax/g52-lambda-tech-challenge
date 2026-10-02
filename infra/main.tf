data "aws_caller_identity" "current" {}

# chave do jwt, vai pra lambda por env (só fica no state)
resource "tls_private_key" "jwt" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

# banco vem do repo g52-infra-rds-tech-challenge
data "aws_db_instance" "this" {
  db_instance_identifier = var.db_identifier
}

data "aws_secretsmanager_secret_version" "db" {
  secret_id = "${var.db_identifier}/credentials"
}

data "aws_db_subnet_group" "this" {
  name = data.aws_db_instance.this.db_subnet_group
}

data "aws_security_group" "rds_clients" {
  name   = "${var.db_identifier}-clients"
  vpc_id = data.aws_db_subnet_group.this.vpc_id
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
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_security_group" "lambda" {
  name        = "${var.function_name}-sg"
  description = "Lambda de autenticacao por CPF"
  vpc_id      = data.aws_db_subnet_group.this.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
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

  # sem nat na vpc, então os segredos vão por env em vez de buscar no secrets manager
  environment {
    variables = {
      SERVICE_NAME        = var.function_name
      DB_HOST             = data.aws_db_instance.this.address
      DB_PORT             = tostring(data.aws_db_instance.this.port)
      DB_NAME             = local.db_credentials.dbname
      DB_USERNAME         = local.db_credentials.username
      DB_PASSWORD         = local.db_credentials.password
      DB_SSL              = tostring(var.db_ssl)
      JWT_PRIVATE_KEY_PEM = tls_private_key.jwt.private_key_pem
      JWT_ISSUER          = var.jwt_issuer
      JWT_AUDIENCE        = var.jwt_audience
      JWT_TTL_SECONDS     = tostring(var.jwt_ttl_seconds)
    }
  }

  vpc_config {
    subnet_ids         = data.aws_db_subnet_group.this.subnet_ids
    security_group_ids = [aws_security_group.lambda.id, data.aws_security_group.rds_clients.id]
  }

  tags = local.function_tags

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy_attachment.basic_execution,
    aws_iam_role_policy_attachment.vpc_access,
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
