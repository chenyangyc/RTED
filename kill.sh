#!/bin/bash

# Find all processes with 'process' in their name, excluding the grep command itself
pids=$(ps aux | grep 'python' | awk '{print $2}')

# Check if any processes were found
if [ -z "$pids" ]; then
  echo "No processes found with 'process' in their name."
  exit 0
fi

# Kill each found process
for pid in $pids; do
  echo "Killing process with PID $pid"
  kill -9 $pid
done

echo "All processes with 'python' in their name have been killed."

