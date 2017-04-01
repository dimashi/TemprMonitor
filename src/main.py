import traceback
from time import sleep

from monitor import TempMonitor, log

while True:
    try:
        TempMonitor().run()
    except:
        info = traceback.format_exc()
        log(info)
        sleep(2)
