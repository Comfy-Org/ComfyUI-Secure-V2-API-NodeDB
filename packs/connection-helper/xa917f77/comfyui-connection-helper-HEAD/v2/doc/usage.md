# Usage

Right-click a target node and open **Connection Helper**.

- **Connect nearest compatible inputs** searches nodes to the left and connects
  the closest output for each first unconnected input type.
- **Copy inputs from nearest node** duplicates the nearest node's incoming
  links, matching target inputs by name.
- **Copy all connections from nearest node** also duplicates outgoing links;
  like upstream, it does nothing unless the target is fully disconnected.

The nearest-node copy actions use a 1,000 graph-unit radius, matching upstream.
