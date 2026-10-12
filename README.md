# maya-bridge

Run scripts inside a live Autodesk Maya session from an MCP client such as
[opencode](https://opencode.ai). `maya-bridge` has two halves:

- **`maya_bridge.py`** — a tiny TCP server that runs *inside* Maya on the main
  thread and executes Python or MEL, returning stdout, the value of the last
  expression, and any traceback. It is auto-started by `userSetup.py`.
- **`mcp_server.py`** — a dependency-free MCP stdio server that forwards tool
  calls to the in-Maya bridge and exposes them as the `maya_run` and
  `maya_status` tools.

```
MCP client  <--stdin/stdout-->  mcp_server.py  <--TCP 127.0.0.1:7789-->  Maya (maya_bridge.py)
```

## Requirements

- Autodesk Maya (the bridge is developed against 2026/2027; older versions work
  as long as `maya.utils.executeInMainThreadWithResult` exists).
- Python 3 for the MCP server — standard library only, no `pip install` needed.

## Install

### 1. Maya side

Copy `maya_bridge.py` and `userSetup.py` into Maya's `scripts` directory:

```
~/Library/Preferences/Autodesk/maya/<version>/scripts/
```

The included script does this for you (macOS, default version 2027):

```sh
./install.sh 2027
```

Then restart Maya. The bridge starts automatically and prints:

```
maya-bridge listening on 127.0.0.1:7789
```

To start it manually instead, run this in Maya's Script Editor:

```python
import maya_bridge
maya_bridge.start()
```

### 2. MCP client side

Add the server to your opencode config (`~/.config/opencode/opencode.jsonc`),
pointing at the absolute path of `mcp_server.py`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "maya": {
      "type": "local",
      "command": ["python3", "/ABSOLUTE/PATH/TO/maya-bridge/mcp_server.py"],
      "environment": { "MAYA_BRIDGE_PORT": "7789" },
      "timeout": 300000,
      "enabled": true
    }
  },
  "experimental": { "mcp_timeout": 300000 }
}
```

See `opencode.jsonc.example`. Any MCP client that speaks the `initialize`,
`tools/list`, and `tools/call` methods works.

## Tools

### `maya_status`

Confirms the bridge is reachable and reports Maya version, platform, current
scene, node count, and the current selection.

### `maya_run`

| argument          | type    | notes                                                        |
| ----------------- | ------- | ------------------------------------------------------------ |
| `code`            | string  | Python or MEL source to execute (required).                  |
| `lang`            | string  | `python` (default) or `mel`.                                 |
| `timeout_seconds` | number  | Default 120, max 290. Maya keeps running after a timeout.    |

The script runs on Maya's **main thread**, so Maya's UI blocks while it runs.
Python globals persist between calls (a persistent REPL session) and `cmds`
(`maya.cmds`) and `mel` (`maya.mel`) are pre-imported. The value of the last
expression is returned as `result`.

## Configuration

| variable            | default     | used by      |
| ------------------- | ----------- | ------------ |
| `MAYA_BRIDGE_PORT`  | `7789`      | both halves  |

Set the same port on both sides if you change it.

## Security

The bridge listens on `127.0.0.1` only and executes arbitrary code on your
machine by design. Do not expose the port to a network — treat it like a local
shell. Anyone who can reach the port can run anything as your user.

## License

MIT — see [LICENSE](LICENSE).
