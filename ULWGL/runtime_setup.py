#!/usr/bin/python
import json
import os
import requests
import tarfile
import tempfile
import shutil
import subprocess
import re

def force_rename(src, dst):
    if os.path.exists(dst):
        os.remove(dst)  # or os.unlink(dst)
    os.rename(src, dst)

# Open the JSON file and load its content into a Python dictionary
with open('ULWGL_VERSION.json', 'r') as file:
    data = json.load(file)

# Access the 'runtime_platform' value
runtime_platform_value = data['ulwgl']['versions']['runtime_platform']

# Assuming runtime_platform_value is "sniper_platform_0.20240125.75305"
# Split the string at 'sniper_platform_'
split_value = runtime_platform_value.split('sniper_platform_')

# The part after 'sniper_platform_' is at index  1, so we access it
sniper_version = split_value[1]

# Step  1: Define the URL of the file to download
base_url = "https://repo.steampowered.com/steamrt3/images/{sniper_version}/steam-container-runtime-complete.tar.gz"

# Using f-string formatting to insert the variable into the URL
url = base_url.format(sniper_version=sniper_version)

# Command to download the file and pipe the progress to Zenity
download_command = f'wget -c "{url}" --progress=dot:mega --show-progress -O /tmp/steam-container-runtime-complete.tar.gz'

# Execute the command and pipe the output to Zenity
# Execute the command and pipe the output to Zenity
with subprocess.Popen(download_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
    # Start Zenity with a pipe to its standard input
    zenity_proc = subprocess.Popen(['zenity', '--progress', '--auto-close', '--text=Downloading Runtime, please wait...', '--percentage=0'], stdin=subprocess.PIPE)

    for line in iter(proc.stdout.readline, b''):
        # Parse the output to extract the progress percentage
        if b'%' in line:
            line_str = line.decode('utf-8')
            match = re.search(r'(\d+)%', line_str)
            if match:
                percentage = match.group(1)
                # Send the percentage to Zenity's standard input
                zenity_proc.stdin.write(percentage.encode('utf-8') + b'\n')
                zenity_proc.stdin.flush()

    # Close the Zenity process's standard input
    zenity_proc.stdin.close()
    zenity_proc.wait()

# Assuming the file is downloaded to '/tmp/steam-container-runtime-complete.tar.gz'
tar_path = '/tmp/steam-container-runtime-complete.tar.gz'

# Open the tar file
with tarfile.open(tar_path, "r:gz") as tar:
    # Ensure the target directory exists
    os.makedirs(os.path.expanduser("~/.local/share/ULWGL/"), exist_ok=True)
    # Extract the 'depot' folder to the target directory
    for member in tar.getmembers():
        if member.name.startswith("steam-container-runtime/depot/"):
            tar.extract(member, path=os.path.expanduser("~/.local/share/ULWGL/"))

    # Step 4: move the files to the correct location
    source_dir = os.path.expanduser("~/.local/share/ULWGL/steam-container-runtime/depot/")
    destination_dir = os.path.expanduser("~/.local/share/ULWGL/")

    # List all files in the source directory
    files = os.listdir(source_dir)

    # Move each file to the destination directory, overwriting if it exists
    for file in files:
        src_file = os.path.join(source_dir, file)
        dest_file = os.path.join(destination_dir, file)
        if os.path.isfile(dest_file) or os.path.islink(dest_file):
            os.remove(dest_file)  # remove the file
        elif os.path.isdir(dest_file):
            shutil.rmtree(dest_file)  # remove dir and all contains
        shutil.move(src_file, dest_file)

    # Remove the extracted directory and all its contents
    shutil.rmtree(os.path.expanduser("~/.local/share/ULWGL/steam-container-runtime/"))
    force_rename(os.path.join(destination_dir, "_v2-entry-point"), os.path.join(destination_dir, "ULWGL"))
