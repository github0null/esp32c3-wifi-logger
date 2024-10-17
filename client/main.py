# --------------------------------------------------------------------------------
# Put your code in 'app.py' and export your entry functions:
#
#  def init():
#     ...  
#  async def main():
#     ...
# --------------------------------------------------------------------------------

import micropython
import machine
import time
import sys
import gc
import os
import app
import asyncio

print('------------- main.py -------------')
micropython.mem_info()

class _TaskAbortError(Exception):
    pass

def task_error_handler(loop, context):
    print('call task_error_handler')
    e1 = context["exception"]
    e2 = Exception('task abort !\n' + \
                   f' loop: {str(loop)}\n' + \
                   f' future: {str(context["future"])}\n' + \
                   f' message: {str(context["message"])}')
    sys.print_exception(e1)
    dump_traceback(e1, e2)
    raise _TaskAbortError(f'task error')

def dump_traceback(*exceptions: any):
    _filepath = "traceback.txt"
    _mode = 'a'
    try:
        _stat = os.stat(_filepath)
        #print(f'os.stat({_filepath}): {str(_stat)}')
        # os.stat = (32768, 0, 0, 0, 0, 0, 60794, 774971513, 774971513, 774971513)
        fsize = _stat[6]
        #print(f'  size: {str(fsize)} Bytes')
        if fsize > (10 * 1024):
            _mode = 'w'
    except Exception as err:
        print(f'fail to stat file: "{_filepath}":', err)
    with open(_filepath, _mode) as f:
        f.write('\n------------------------------\n')
        f.write('RAM free: ' + str(gc.mem_free()) + ' Bytes')
        f.write('\n')
        for e in exceptions:
            sys.print_exception(e, f)

try:
    app.init()
    asyncio.Loop.set_exception_handler(task_error_handler)
    asyncio.run(app.main())
except KeyboardInterrupt:
    print('------------- user interrupted (ctrl+c) ------------')
except MemoryError as e:
    print('------------- MemoryError ------------')
    sys.print_exception(e)
    dump_traceback(e)
except _TaskAbortError as e:
    print('task error.')
except Exception as e:
    print('------------- dump exception ------------')
    sys.print_exception(e)
    dump_traceback(e)
finally:
    print('------------- cleanup and reboot after 5sec delay -------------')
    time.sleep(5)
    machine.reset()