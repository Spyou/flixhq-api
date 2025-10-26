#!/bin/bash
set -e

# Install Chrome dependencies
apt-get update
apt-get install -y wget unzip
apt-get install -y libnss3 libxss1 libasound2 libgconf-2-4

# Install Chrome
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
apt-get update
apt-get install -y google-chrome-stable

# Install Python dependencies
pip install -r requirements.txt
