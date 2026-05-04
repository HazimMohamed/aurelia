#!/bin/bash
# Remove leftover ephemeral agent homes, Linux users, and config entries.
set -e

GHOSTS=(exp-personal-c8d9a6ee exp-personal-634c5e3a exp-personal-c310cf6e exp-personal-d093fd42)

for name in "${GHOSTS[@]}"; do
    echo "Cleaning $name..."

    # Remove home dir
    if [ -d "/home/$name" ]; then
        rm -rf "/home/$name"
        echo "  removed /home/$name"
    fi

    # Remove Linux user
    if id "$name" &>/dev/null; then
        userdel "$name" 2>/dev/null && echo "  removed user $name" || echo "  userdel failed for $name"
    fi

    # Remove from config.json
    python3 - "$name" <<'EOF'
import json, sys
name = sys.argv[1]
path = "/var/aurelia/config.json"
cfg = json.loads(open(path).read())
cfg.get("agents", {}).pop(name, None)
open(path, "w").write(json.dumps(cfg, indent=4))
print(f"  removed {name} from config.json")
EOF
done

echo ""
echo "Remaining agents in config:"
python3 -c "import json; cfg=json.load(open('/var/aurelia/config.json')); print(list(cfg.get('agents',{}).keys()))"
