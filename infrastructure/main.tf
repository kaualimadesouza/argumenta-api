data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "argumenta-api-${var.stage}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "api_basic_execution" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "api" {
  function_name = "argumenta-api-${var.stage}"
  role          = aws_iam_role.api.arn

  package_type  = "Image"
  image_uri     = var.image_uri
  architectures = ["x86_64"]
  memory_size   = 512
  # budget for the async evaluation leg (self-invoke, issue #68); the HTTP leg
  # answers in <2s and API Gateway's hard 30s cap no longer constrains anything
  timeout       = 120

  environment {
    variables = {
      ENVIRONMENT                    = var.stage
      ARGUMENTA_ANTHROPIC_API_KEY    = var.argumenta_anthropic_api_key
      ARGUMENTA_GOOGLE_CLIENT_ID     = var.argumenta_google_client_id
      ARGUMENTA_GOOGLE_CLIENT_SECRET = var.argumenta_google_client_secret
      ARGUMENTA_DATABASE_URL         = var.argumenta_database_url
      ARGUMENTA_JWT_SECRET           = var.argumenta_jwt_secret
      ARGUMENTA_GOOGLE_API_KEY       = var.argumenta_google_api_key
      ARGUMENTA_LLM_VENDOR           = var.argumenta_llm_vendor
      ARGUMENTA_EVALUATION_MODEL     = var.argumenta_evaluation_model
      ARGUMENTA_REACTION_MODEL       = var.argumenta_reaction_model
    }
  }
}

# the evaluation runs as an async self-invoke of this same function (issue #68)
data "aws_iam_policy_document" "self_invoke" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.api.arn]
  }
}

resource "aws_iam_role_policy" "api_self_invoke" {
  name   = "argumenta-api-${var.stage}-self-invoke"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.self_invoke.json
}

resource "aws_apigatewayv2_api" "api" {
  name          = "argumenta-api-${var.stage}"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "api" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
