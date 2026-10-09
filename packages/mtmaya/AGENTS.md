# Maya session

- No Maya calls at import time. Importing a module must not query the scene, create nodes, load plugins, or register callbacks.
- `userSetup.py` stays a thin entry point: configure logging, then return. Heavy work belongs behind an explicit command.
- Scene changes go through `maya.cmds` inside an undo chunk. Restore selection when the tool did not mean to change it.
- Register scriptJobs, callbacks, and Qt widgets once, and remove them on unload. Parent Qt widgets to Maya’s main window and use Maya’s shipped Qt bindings.
- Prefer list-based `cmds` calls over per-node Python loops. Do not build MEL or `eval` strings.

```python
def run() -> None:
    """Rename the selection in one undo chunk."""
    cmds.undoInfo(openChunk=True)
    try:
        nodes = cmds.ls(selection=True, long=True) or []
        for node in nodes:
            cmds.rename(node, "hero_")
    finally:
        cmds.undoInfo(closeChunk=True)
```
