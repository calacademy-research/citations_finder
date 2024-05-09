#!/bin/bash

# Change to the directory of the script
cd "$(dirname "$0")"

# Variables
RCLONE_CONFIG_DIR="$HOME/.config/rclone"
RCLONE_CONFIG_FILE="$RCLONE_CONFIG_DIR/rclone.conf"
MOUNT_DIR="/Volumes/pdf"
RCLONE_BIN="/usr/local/bin/rclone"
# RCLONE_BIN="$PWD/rclone-v1.65.0-osx-amd64/rclone"
VM_PASSWORDS_FILE="./vm/vm_passwords.yml"

# Obtain the current user's UID and GID
USER_UID=$(id -u)
USER_GID=$(id -g)


# Extract values from YAML file
pdf_s3_secret_access_key=$(yq e '.pdf_s3_secret_access_key' "$VM_PASSWORDS_FILE")
pdf_s3_access_key_id=$(yq e '.pdf_s3_access_key_id' "$VM_PASSWORDS_FILE")
pdf_s3_pdf_endpoint=$(yq e '.pdf_s3_pdf_endpoint' "$VM_PASSWORDS_FILE")



# Ensure rclone config directory exists
mkdir -p "$RCLONE_CONFIG_DIR"
chmod 0755 "$RCLONE_CONFIG_DIR"

# Add configuration to rclone.conf
{
  echo "[pdf-cloud]"
  echo "type = s3"
  echo "provider = Other"
  echo "access_key_id = $pdf_s3_access_key_id"
  echo "secret_access_key = $pdf_s3_secret_access_key"
  echo "endpoint = $pdf_s3_pdf_endpoint"
  echo "acl = private"
} > "$RCLONE_CONFIG_FILE"

# Kill existing rclone process
sudo pkill -f $RCLONE_BIN

sudo rmdir /Volumes/pdf

# Unmount the directory if mounted
sudo umount "$MOUNT_DIR"

# Check if mount directory exists and create it if not
[ ! -d "$MOUNT_DIR" ] && sudo mkdir -p "$MOUNT_DIR" && sudo chmod 0755 "$MOUNT_DIR"

# Mount pdf-cloud using rclone with user write permissions and friendly file creation
#sudo $RCLONE_BIN mount pdf-cloud:citations-finder-pdfs "$MOUNT_DIR" --default-permissions --allow-other --umask 002 --file-perms 0666 --dir-perms 0777 --daemon
runme="sudo -E $RCLONE_BIN mount pdf-cloud:citations-finder-pdfs "$MOUNT_DIR" --default-permissions --allow-other --umask 002 --file-perms 0666 --dir-perms 0777 --uid $USER_UID --gid $USER_GID --daemon"
#echo $runme
`$runme`

# Create symbolic link for pdfs
ln -s /Volumes/pdf/pdf "$PWD/pdf"
