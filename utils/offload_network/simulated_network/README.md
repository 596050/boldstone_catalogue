# Simulated network

This directory is an integration-test artifact, not a live network config.
`run_simulation.py` recreates it with a controller, durable queue, configured
data source, and isolated Windows/Linux/macOS-labelled worker directories.

The simulation executes the real sealed-bundle builder and remote runner. It
does not emulate OS-specific shells or establish SSH connections.
