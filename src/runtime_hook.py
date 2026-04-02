import sys
import os
if os.environ.get('LOGANALYSIS_QT_DEBUG_PLUGINS') == '1':
    os.environ['QT_DEBUG_PLUGINS'] = '1'
if sys.platform == 'linux' and hasattr(sys, '_MEIPASS'):
    existing = os.environ.get('LD_LIBRARY_PATH')
    if existing:
        os.environ['LD_LIBRARY_PATH'] = f"{sys._MEIPASS}{os.pathsep}{existing}"
    else:
        os.environ['LD_LIBRARY_PATH'] = sys._MEIPASS
