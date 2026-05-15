terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }
}

provider "aws" {
  region = var.region
}

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "${var.project}-vpc-main"
    Environment = var.environment
  }
}

resource "aws_vpc" "peer" {
  cidr_block           = "10.1.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "${var.project}-vpc-peer"
    Environment = var.environment
  }
}

resource "aws_vpc_peering_connection" "main" {
  vpc_id      = aws_vpc.main.id
  peer_vpc_id = aws_vpc.peer.id
  auto_accept = true

  tags = {
    Name = "${var.project}-peering"
  }
}

resource "aws_subnet" "main" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "${var.region}a"

  tags = {
    Name = "${var.project}-main-subnet"
  }
}

resource "aws_subnet" "peer" {
  vpc_id            = aws_vpc.peer.id
  cidr_block        = "10.1.1.0/24"
  availability_zone = "${var.region}a"

  tags = {
    Name = "${var.project}-peer-subnet"
  }
}

resource "aws_route_table" "main" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block                = "10.1.0.0/16"
    vpc_peering_connection_id = aws_vpc_peering_connection.main.id
  }

  tags = {
    Name = "${var.project}-rt-main"
  }
}

resource "aws_route_table" "peer" {
  vpc_id = aws_vpc.peer.id

  route {
    cidr_block                = "10.0.0.0/16"
    vpc_peering_connection_id = aws_vpc_peering_connection.main.id
  }

  tags = {
    Name = "${var.project}-rt-peer"
  }
}

resource "aws_route_table_association" "main" {
  subnet_id      = aws_subnet.main.id
  route_table_id = aws_route_table.main.id
}

resource "aws_route_table_association" "peer" {
  subnet_id      = aws_subnet.peer.id
  route_table_id = aws_route_table.peer.id
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