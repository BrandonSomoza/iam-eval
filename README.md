# IAM LLM Policy Evaluation

Evaluates the reliability of LLMs at generating least-privilege IAM action policies for Terraform-managed AWS network infrastructure. Compares LLM output against Pike-generated ground truth across 50 configurations, 3 models, and 3 prompt strategies.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
export TOGETHER_API_KEY=your_key_here
python3 main.py --tier all --model all --prompt all
```

## Models
- meta-llama/Llama-3.3-70B-Instruct-Turbo
- Qwen/Qwen2.5-7B-Instruct-Turbo
- meta-llama/Meta-Llama-3-8B-Instruct-Lite

## Prompts
- v1: baseline prompt
- v2: Terraform internals hint
- v3: Pike validation prompt
