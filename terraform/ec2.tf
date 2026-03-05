# =============================================================================
# CNAP AI SIEM Copilot — EC2 Instance Configuration
# =============================================================================

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # Determine if this is a GPU instance type
  is_gpu_instance = startswith(var.instance_type, "g4dn") || startswith(var.instance_type, "p3")

  # Cloud-init user data — installs Docker, Docker Compose, NVIDIA drivers
  user_data = <<-USERDATA
    #!/bin/bash
    set -euo pipefail
    exec > >(tee /var/log/cloud-init-output.log | logger -t user-data -s 2>/dev/console) 2>&1

    echo "=== CNAP AI SIEM Copilot: Starting instance initialization ==="
    export DEBIAN_FRONTEND=noninteractive

    # Update system
    apt-get update -y
    apt-get upgrade -y

    # Install prerequisites
    apt-get install -y \
      curl \
      wget \
      unzip \
      ca-certificates \
      gnupg \
      lsb-release \
      jq \
      git \
      awscli

    # Install Docker
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Add ubuntu user to docker group
    usermod -aG docker ubuntu

    # Enable Docker service
    systemctl enable docker
    systemctl start docker

    %{ if local.is_gpu_instance && var.enable_gpu ~}
    # Install NVIDIA drivers and CUDA toolkit
    echo "=== Installing NVIDIA drivers ==="
    apt-get install -y linux-headers-$(uname -r)
    distribution=$(. /etc/os-release; echo $ID$VERSION_ID | tr -d '.')
    wget "https://developer.download.nvidia.com/compute/cuda/repos/$${distribution}/x86_64/cuda-keyring_1.1-1_all.deb"
    dpkg -i cuda-keyring_1.1-1_all.deb
    apt-get update -y
    apt-get install -y cuda-drivers

    # Install NVIDIA Container Toolkit
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
      gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
      sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
      tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    apt-get update -y
    apt-get install -y nvidia-container-toolkit
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
    %{ endif ~}

    # Create application directory
    mkdir -p /opt/cnap-siem
    chown ubuntu:ubuntu /opt/cnap-siem

    # Configure CloudWatch agent for logs
    apt-get install -y amazon-cloudwatch-agent || true

    echo "=== Cloud-init finished successfully ==="
  USERDATA
}

resource "aws_instance" "siem_copilot" {
  ami                    = data.aws_ami.ubuntu_24.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.siem_copilot.id]
  iam_instance_profile   = aws_iam_instance_profile.siem_copilot.name
  key_name               = var.ssh_key_name != "" ? var.ssh_key_name : null

  user_data                   = local.user_data
  user_data_replace_on_change = false

  # Disable public IP — access only via SSM
  associate_public_ip_address = false

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.ebs_volume_size_gb
    encrypted             = true
    delete_on_termination = true

    tags = {
      Name = "${local.name_prefix}-root-ebs"
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"  # IMDSv2 required
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  monitoring = true

  tags = {
    Name = "${local.name_prefix}-instance"
  }

  lifecycle {
    ignore_changes = [ami]  # Don't replace instance on AMI updates
  }
}

resource "aws_iam_instance_profile" "siem_copilot" {
  name = "${local.name_prefix}-instance-profile"
  role = aws_iam_role.siem_copilot.name
}
