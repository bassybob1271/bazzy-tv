variable "oci_tenancy_ocid"       { type = string }
variable "oci_user_ocid"          { type = string }
variable "oci_fingerprint"        { type = string }
variable "oci_private_key_path"   { type = string }
variable "oci_compartment_id"     { type = string }
variable "oci_region"             { type = string; default = "us-ashburn-1" }
variable "oci_ubuntu_image_ocid"  { type = string; description = "Ubuntu 22.04 image OCID for chosen region" }
variable "oci_ubuntu_image_id"    { type = string; default = "" }
variable "ssh_public_key"         { type = string }
variable "cloudflare_api_token"   { type = string; sensitive = true }
variable "api_instance_count"     { type = number; default = 2 }
variable "worker_instance_count"  { type = number; default = 2 }
