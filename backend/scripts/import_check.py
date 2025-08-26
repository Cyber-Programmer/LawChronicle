import importlib, traceback, sys
try:
    m = importlib.import_module('app.api.v1.endpoints.phase4')
    print('OK import')
except Exception as e:
    traceback.print_exc()
    print('IMPORT ERROR', e)
    sys.exit(1)
