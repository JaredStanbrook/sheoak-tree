# scripts/setup-git-config.sh
#!/bin/bash

echo "🔐 Setting up Git configuration and commit signing..."

# Get user information
read -p "Enter your full name: " FULL_NAME
read -p "Enter your email address: " EMAIL_ADDRESS
read -p "Choose signing method (gpg/ssh): " SIGNING_METHOD

# Set basic Git config
git config --global user.name "$FULL_NAME"
git config --global user.email "$EMAIL_ADDRESS"

# Set other useful defaults
git config --global init.defaultBranch main
git config --global pull.rebase false
git config --global push.default simple

# Set up signing
if [ "$SIGNING_METHOD" = "gpg" ]; then
    echo "Setting up GPG signing..."

    # Check if GPG is installed
    if ! command -v gpg &> /dev/null; then
        echo "❌ GPG not found. Please install GPG first."
        exit 1
    fi

    echo "Please generate a GPG key manually:"
    echo "1. Run: gpg --full-generate-key"
    echo "2. Follow the prompts"
    echo "3. Then run this script again"

    # List existing keys
    gpg --list-secret-keys --keyid-format=long
    read -p "Enter your GPG key ID: " GPG_KEY_ID

    git config --global user.signingkey $GPG_KEY_ID
    git config --global commit.gpgsign true
    git config --global tag.gpgsign true

    echo "✅ GPG signing configured"
    echo "Don't forget to add your GPG key to GitHub!"
    gpg --armor --export $GPG_KEY_ID

elif [ "$SIGNING_METHOD" = "ssh" ]; then
    echo "Setting up SSH signing..."

    # Check for existing SSH key
    if [ -f ~/.ssh/id_ed25519.pub ]; then
        SSH_KEY_PATH=~/.ssh/id_ed25519.pub
    elif [ -f ~/.ssh/id_rsa.pub ]; then
        SSH_KEY_PATH=~/.ssh/id_rsa.pub
    else
        echo "No SSH key found. Generating one..."
        ssh-keygen -t ed25519 -C "$EMAIL_ADDRESS"
        SSH_KEY_PATH=~/.ssh/id_ed25519.pub
    fi

    git config --global user.signingkey $SSH_KEY_PATH
    git config --global gpg.format ssh
    git config --global commit.gpgsign true

    echo "✅ SSH signing configured"
    echo "Don't forget to add your SSH key to GitHub as a signing key!"
    cat $SSH_KEY_PATH
fi

echo ""
echo "📋 Your Git configuration:"
git config --global --list | grep -E "(user\.|commit\.|gpg\.)"
