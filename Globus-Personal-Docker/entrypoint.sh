#!/bin/env bash

if [ "$START_GLOBUS" = "true" ]; then
    echo "Starting Globus Connect Personal"
    su gridftp -c "cd /home/gridftp && source ./globus-connect-personal.sh"
else
    su gridftp -c "cd /home/gridftp && source ./initialization.sh"
fi

echo setup complete
