"""Auto-start the opencode Maya bridge when Maya launches."""
try:
    import maya_bridge

    maya_bridge.start()
except Exception as exc:
    print("maya-bridge failed to start: %s" % exc)
