terraform {
  required_version = ">= 1.6"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }

  backend "s3" {
    # Store state in OCI Object Storage (S3-compatible)
    bucket                      = "bazzy-terraform-state"
    key                         = "bazzy-video/terraform.tfstate"
    region                      = "us-ashburn-1"
    endpoint                    = "https://<TENANCY_NAMESPACE>.compat.objectstorage.us-ashburn-1.oraclecloud.com"
    skip_region_validation      = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    force_path_style            = true
  }
}

# ─────────────────────────────────────────────
# OCI Provider
# ─────────────────────────────────────────────
provider "oci" {
  tenancy_ocid     = var.oci_tenancy_ocid
  user_ocid        = var.oci_user_ocid
  fingerprint      = var.oci_fingerprint
  private_key_path = var.oci_private_key_path
  region           = var.oci_region
}

# ─────────────────────────────────────────────
# Cloudflare Provider
# ─────────────────────────────────────────────
provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# ─────────────────────────────────────────────
# OCI Object Storage — Media buckets
# ─────────────────────────────────────────────
resource "oci_objectstorage_bucket" "media_hot" {
  compartment_id = var.oci_compartment_id
  namespace      = data.oci_objectstorage_namespace.ns.namespace
  name           = "bazzy-video-media-hot"
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"

  lifecycle_policy_etag = oci_objectstorage_object_lifecycle_policy.media_lifecycle.etag

  freeform_tags = {
    "Project" = "BazzyVideo"
    "Tier"    = "Hot"
  }
}

resource "oci_objectstorage_bucket" "media_cold" {
  compartment_id = var.oci_compartment_id
  namespace      = data.oci_objectstorage_namespace.ns.namespace
  name           = "bazzy-video-media-cold"
  access_type    = "NoPublicAccess"
  storage_tier   = "Archive"

  freeform_tags = {
    "Project" = "BazzyVideo"
    "Tier"    = "Cold"
  }
}

data "oci_objectstorage_namespace" "ns" {
  compartment_id = var.oci_tenancy_ocid
}

# Move to cold storage after 90 days
resource "oci_objectstorage_object_lifecycle_policy" "media_lifecycle" {
  namespace = data.oci_objectstorage_namespace.ns.namespace
  bucket    = oci_objectstorage_bucket.media_hot.name

  rules {
    name        = "archive-after-90-days"
    action      = "ARCHIVE"
    time_amount = 90
    time_unit   = "DAYS"
    is_enabled  = true
    target      = "objects"
  }

  rules {
    name        = "delete-after-365-days"
    action      = "DELETE"
    time_amount = 365
    time_unit   = "DAYS"
    is_enabled  = true
    target      = "objects"
  }
}

# ─────────────────────────────────────────────
# OCI Compute — API + Worker nodes
# ─────────────────────────────────────────────
resource "oci_core_instance" "api" {
  count               = var.api_instance_count
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  compartment_id      = var.oci_compartment_id
  display_name        = "bazzy-video-api-${count.index}"
  shape               = "VM.Standard.E4.Flex"

  shape_config {
    ocpus         = 2
    memory_in_gbs = 16
  }

  source_details {
    source_type = "image"
    source_id   = var.oci_ubuntu_image_id
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = true
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = base64encode(templatefile("${path.module}/scripts/api_init.sh", {
      docker_compose_url = "https://raw.githubusercontent.com/YOUR_ORG/bazzy-video/main/docker-compose.yml"
    }))
  }
}

resource "oci_core_instance" "worker" {
  count               = var.worker_instance_count
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  compartment_id      = var.oci_compartment_id
  display_name        = "bazzy-video-worker-${count.index}"
  shape               = "VM.Standard.E4.Flex"

  shape_config {
    ocpus         = 4   # More CPU for FFmpeg
    memory_in_gbs = 32
  }

  source_details {
    source_type = "image"
    source_id   = var.oci_ubuntu_image_id
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.private.id
    assign_public_ip = false
  }
}

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.oci_tenancy_ocid
}

# ─────────────────────────────────────────────
# OCI VCN + Subnets
# ─────────────────────────────────────────────
resource "oci_core_vcn" "main" {
  compartment_id = var.oci_compartment_id
  cidr_block     = "10.0.0.0/16"
  display_name   = "bazzy-video-vcn"
  dns_label      = "bazzyvideo"
}

resource "oci_core_subnet" "public" {
  compartment_id    = var.oci_compartment_id
  vcn_id            = oci_core_vcn.main.id
  cidr_block        = "10.0.1.0/24"
  display_name      = "public-subnet"
  dns_label         = "public"
  route_table_id    = oci_core_route_table.public.id
  security_list_ids = [oci_core_security_list.public.id]
}

resource "oci_core_subnet" "private" {
  compartment_id             = var.oci_compartment_id
  vcn_id                     = oci_core_vcn.main.id
  cidr_block                 = "10.0.2.0/24"
  display_name               = "private-subnet"
  dns_label                  = "private"
  prohibit_public_ip_on_vnic = true
  security_list_ids          = [oci_core_security_list.private.id]
}

resource "oci_core_internet_gateway" "igw" {
  compartment_id = var.oci_compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "bazzy-igw"
  enabled        = true
}

resource "oci_core_route_table" "public" {
  compartment_id = var.oci_compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "public-rt"

  route_rules {
    network_entity_id = oci_core_internet_gateway.igw.id
    destination       = "0.0.0.0/0"
  }
}

resource "oci_core_security_list" "public" {
  compartment_id = var.oci_compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "public-sl"

  ingress_security_rules {
    protocol = "6" # TCP
    source   = "0.0.0.0/0"
    tcp_options { min = 80;  max = 80 }
  }
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options { min = 443; max = 443 }
  }
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options { min = 22;  max = 22 }
  }
  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }
}

resource "oci_core_security_list" "private" {
  compartment_id = var.oci_compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "private-sl"

  ingress_security_rules {
    protocol = "6"
    source   = "10.0.1.0/24" # Only from public subnet
  }
  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }
}

# ─────────────────────────────────────────────
# Cloudflare DNS + CDN
# ─────────────────────────────────────────────
data "cloudflare_zone" "bazzy" {
  name = "bazzyvideo.com"
}

resource "cloudflare_record" "api" {
  zone_id = data.cloudflare_zone.bazzy.id
  name    = "api"
  value   = oci_core_instance.api[0].public_ip
  type    = "A"
  proxied = true  # Through Cloudflare CDN
  ttl     = 1
}

resource "cloudflare_record" "www" {
  zone_id = data.cloudflare_zone.bazzy.id
  name    = "www"
  value   = oci_core_instance.api[0].public_ip
  type    = "A"
  proxied = true
  ttl     = 1
}

resource "cloudflare_record" "root" {
  zone_id = data.cloudflare_zone.bazzy.id
  name    = "@"
  value   = oci_core_instance.api[0].public_ip
  type    = "A"
  proxied = true
  ttl     = 1
}

# Cloudflare Page Rules — cache HLS segments aggressively
resource "cloudflare_page_rule" "hls_cache" {
  zone_id  = data.cloudflare_zone.bazzy.id
  target   = "bazzyvideo.com/hls/*"
  priority = 1

  actions {
    cache_level = "cache_everything"
    edge_cache_ttl = 86400  # 24hr CDN edge cache for .ts segments
  }
}

# ─────────────────────────────────────────────
# Outputs
# ─────────────────────────────────────────────
output "api_public_ips" {
  value = oci_core_instance.api[*].public_ip
}

output "media_hot_bucket" {
  value = oci_objectstorage_bucket.media_hot.name
}

output "media_cold_bucket" {
  value = oci_objectstorage_bucket.media_cold.name
}
