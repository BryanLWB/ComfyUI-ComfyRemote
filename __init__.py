import sys

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./web"

if "server" in sys.modules:
    from .comfyremote_connector.integration import install

    install()
