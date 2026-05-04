#!/bin/bash
# Remove agents from aurelia_admin — only aurelia and zuzu should be members.
set -e

AGENTS=(personal sandbox-1 sandbox-2 sandbox-3 sandbox-4 sandbox-5
        exp-personal-c8d9a6ee exp-personal-634c5e3a exp-personal-c310cf6e exp-personal-d093fd42)

for name in "${AGENTS[@]}"; do
    if id "$name" &>/dev/null; then
        gpasswd -d "$name" aurelia_admin 2>/dev/null && echo "removed $name" || echo "skip $name (not member)"
    else
        echo "skip $name (user doesn't exist)"
    fi
done

echo ""
echo "aurelia_admin members now:"
getent group aurelia_admin
