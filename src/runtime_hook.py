import sys
import os
os.environ['QT_DEBUG_PLUGINS'] = '1'
if sys.platform == 'linux':
    os.environ['LD_LIBRARY_PATH'] = sys._MEIPASS
