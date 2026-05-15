terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.40" }
  }
}

provider "aws" { region = var.region }

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = { Name = "${var.project}-vpc", Environment = var.environment }
}

resource "aws_vpn_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project}-vgw" }
}

resource "aws_customer_gateway" "main" {
  bgp_asn    = 65000
  ip_address = var.customer_gateway_ip
  type       = "ipsec.1"
  tags       = { Name = "${var.project}-cgw" }
}

resource "aws_vpn_connection" "main" {
  vpn_gateway_id      = aws_vpn_gateway.main.id
  customer_gateway_id = aws_customer_gateway.main.id
  type                = "ipsec.1"
  static_routes_only  = true
  tags                = { Name = "${var.project}-vpn" }
}

resource "aws_vpn_connection_route" "main" {
  destination_cidr_block = var.on_prem_cidr
  vpn_connection_id      = aws_vpn_connection.main.id
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone = "${var.region}${count.index == 0 ? "a" : "b"}"
  tags = { Name = "${var.project}-private-${count.index + 1}" }
}

resource "aws_security_group" "private" {
  name   = "${var.project}-private-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.on_prem_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-private-sg" }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = var.on_prem_cidr
    gateway_id = aws_vpn_gateway.main.id
  }
  tags = { Name = "${var.project}-rt-private" }
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "research-net"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "customer_gateway_ip" {
  type    = string
  default = "203.0.113.1"
}

variable "on_prem_cidr" {
  type    = string
  default = "192.168.0.0/16"
}
