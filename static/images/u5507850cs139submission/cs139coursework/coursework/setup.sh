#!/bin/bash

portnum=5${USER: -4}
if [ "$1" = "--port" ]; then
  portnum="$2"
fi

# add the FLASK RUN PORT to .env if it doesn't alrady exist
if ! grep -q FLASK_RUN_PORT ".env" 2>/dev/null; then
    echo Creating .env
    echo FLASK_DEBUG=True >.env
    echo FLASK_RUN_PORT=$portnum >> .env
fi

# add virtual environment if it doesn't already exist
if ! [[ -d vcwk ]]; then
    echo Adding virtual environment 
    python3 -m venv vcwk

    # create pip.conf if doesn't exist
    echo Creating vcwk/pip.conf
    ( cat <<'EOF'
[install]
user = false
EOF
    ) > vcwk/pip.conf

    source vcwk/bin/activate

    echo Setting up Flask requirements
    # needed python -m pip because pip alone has trouble with spaces in the directory path
    python -m pip install -r requirements.txt
    deactivate
fi

# activate the virtual environment for the lab
source vcwk/bin/activate

# run Flask 
./run.sh eventbyte
