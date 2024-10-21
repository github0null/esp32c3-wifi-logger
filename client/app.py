import network
import time
import socket
import machine
import select
from predecode import predecode
import re
import asyncio
import deflate
import io

class HttpReq:
    def __init__(self):
        self.done = False
        self.method = None
        self.path = None
        self.version = None
        self.header = dict()
        self.body = None
        # private
        self._hdr_done = False
        self._body_remain_sz = 0
        self._line = bytearray()
    def __str__(self):
        if not self.done:
            return 'Invalid Request'
        s = f'{self.method} {self.path} HTTP/{self.version}\n'
        for k in self.header:
            s += k + ':' + self.header[k] + '\n'
        s += '\n'
        if self.body:
            s += str(self.body)[:16].rstrip() + ' ...'
        return s
    def intput(self, byte) -> bool:
        if self.done:
            return True
        if not self._hdr_done:
            self._line.append(byte)
            if byte == 0x0A:
                hdr_line = self._line.decode('utf8').strip()
                if hdr_line == '':
                    # header end
                    self._hdr_done = True
                    # if body size == 0, the request is done.
                    if self._body_remain_sz == 0:
                        self.done = True
                elif self.method == None:
                    m = re.match(r'([A-Z]+) (/.*) HTTP/(.+)', hdr_line)
                    if m:
                        self.method  = m.group(1)
                        self.path    = m.group(2)
                        self.version = m.group(3)
                else:
                    idx = hdr_line.find(':')
                    if idx != -1:
                        k = hdr_line[:idx].strip()
                        v = hdr_line[idx + 1:].strip()
                        self.header[k] = v
                        if k == 'Content-Length':
                            self._body_remain_sz = int(self.header['Content-Length'])
                            self.body = bytearray()
                self._line = bytearray()
        else:
            if self._body_remain_sz > 0:
                self.body.append(byte)
                self._body_remain_sz -= 1
            self.done = self._body_remain_sz == 0
        return self.done

class HttpRsp:
    HTTP_CODES = {
        100: 'Continue',
        101: 'Switching Protocols',
        102: 'Processing',
        103: 'Early Hints',
        200: 'OK',
        201: 'Created',
        202: 'Accepted',
        203: 'Non-Authoritative Information',
        204: 'No Content',
        205: 'Reset Content',
        206: 'Partial Content',
        207: 'Multi-Status',
        208: 'Already Reported',
        226: 'IM Used',
        300: 'Multiple Choices',
        301: 'Moved Permanently',
        302: 'Found',
        303: 'See Other',
        304: 'Not Modified',
        305: 'Use Proxy',
        306: '(Unused)',
        307: 'Temporary Redirect',
        308: 'Permanent Redirect',
        400: 'Bad Request',
        401: 'Unauthorized',
        402: 'Payment Required',
        403: 'Forbidden',
        404: 'Not Found',
        405: 'Method Not Allowed',
        406: 'Not Acceptable',
        407: 'Proxy Authentication Required',
        408: 'Request Timeout',
        409: 'Conflict',
        410: 'Gone',
        411: 'Length Required',
        412: 'Precondition Failed',
        413: 'Content Too Large',
        414: 'URI Too Long',
        415: 'Unsupported Media Type',
        416: 'Range Not Satisfiable',
        417: 'Expectation Failed',
        418: '(Unused)',
        421: 'Misdirected Request',
        422: 'Unprocessable Content',
        423: 'Locked',
        424: 'Failed Dependency',
        425: 'Too Early',
        426: 'Upgrade Required',
        427: 'Unassigned',
        428: 'Precondition Required',
        429: 'Too Many Requests',
        430: 'Unassigned',
        431: 'Request Header Fields Too Large',
        451: 'Unavailable For Legal Reasons',
        500: 'Internal Server Error',
        501: 'Not Implemented',
        502: 'Bad Gateway',
        503: 'Service Unavailable',
        504: 'Gateway Timeout',
        505: 'HTTP Version Not Supported',
        506: 'Variant Also Negotiates',
        507: 'Insufficient Storage',
        508: 'Loop Detected',
        509: 'Unassigned',
        510: 'Not Extended (OBSOLETED)',
        511: 'Network Authentication Required',
    }
    def __init__(self, http_code = 200):
        self.header = []
        self.status = f'{http_code} {HttpRsp.HTTP_CODES.get(http_code, "Unknown")}'
        self.data   = None
    def set_status(self, http_code: int, http_status: str = None):
        if http_status == None:
            self.status = f'{http_code} {HttpRsp.HTTP_CODES.get(http_code, "Unknown")}'
        else:
            self.status = f'{http_code} {http_status}'
        return self
    def add_header(self, line):
        if line not in self.header:
            self.header.append(line)
        return self
    def set_data(self, rsp_data: any = None, compress = False):
        self.data = rsp_data
        if compress:
            stream = io.BytesIO()
            with deflate.DeflateIO(stream, deflate.ZLIB) as d:
                buf = rsp_data if type(rsp_data) != str else rsp_data.encode('utf8')
                d.write(buf)
            self.data = stream.getvalue()
            self.add_header(f'Content-Encoding: deflate')
        return self
    def make(self) -> bytes:
        hdr = []
        hdr.append(f'HTTP/1.1 {self.status}')
        for s in self.header: hdr.append(s)
        if self.data != None:
            body_len = len(self.data)
            if type(self.data) == str:
                body_len = len(self.data.encode())
            hdr.append(f'Content-Length: {body_len}')
        hdr.append('')
        txbuf = bytearray(('\r\n'.join(hdr) + '\r\n').encode())
        if self.data != None:
            if type(self.data) == str:
                for b in self.data.encode():
                    txbuf.append(b)
            else:
                for b in bytes(self.data):
                    txbuf.append(b)
        return bytes(txbuf)
    def __str__(self):
        hdr = []
        hdr.append(f'HTTP/1.1 {self.status}')
        for s in self.header: hdr.append(s)
        if self.data != None:
            body_len = len(self.data.encode()) if type(self.data) == str else len(self.data)
            hdr.append(f'Content-Length: {body_len}')
        hdr.append('')
        rsp = ''
        for l in hdr:
            rsp += l + '\n'
        if self.data != None:
            s = self.data if type(self.data) == str else str(self.data)
            rsp += s[:16].rstrip() + ' ...'
        return rsp

CFG_DEVICE_TAG  = 'dev0'

CFG_WLAN_SSID   = '<SSID>'
CFG_WLAN_PASS   = '<PASS>'
CFG_UART_BAUD   = 115200
CFG_UART_PIN_TX = 0
CFG_UART_PIN_RX = 1
CFG_LED_PIN     = 8

CFG_RMT_SERVER_EN = 0
CFG_RMT_SERVER    = '255.255.255.255'
CFG_RMT_PORT      = 60000

wlan     = None
local_ip = None
uart1    = None
led1_pin = None

# <'ip:port', { '..': ... }>
event_stream_conns = dict()

rmt_recorder = {
    'writer': None,
    'evt.abort': asyncio.Event()
}

def read_user_settings(ign_default=True):
    try:
        lines = []
        with open('settings.txt', 'r') as f:
            for l in f.readlines():
                lines.append(l.strip())
        return lines
    except Exception as err:
        if ign_default:
            raise err
        lines = []
        for k in globals():
            if k[:4] == 'CFG_':
                if eval(f'type({k})==str'):
                    lines.append(f"{k}='{eval(k)}'")
                else:
                    lines.append(f'{k}={eval(k)}')
        return lines

def save_user_settings(items_or_str):
    with open('settings.txt', 'w') as f:
        if type(items_or_str) == list:
            f.writelines(items_or_str)
        else:
            f.write(items_or_str)

def init():
    global wlan, local_ip, uart1, led1_pin

    print('load user settings ...')
    try:
        for line in read_user_settings():
            if line[:4] == 'CFG_':
                print(' -', line)
                exec(line, globals())
        print('done.')
    except Exception as e:
        print(f'fail to load user settings, use default.', e)

    print('init pin ...')
    if CFG_LED_PIN:
        led1_pin = machine.Pin(CFG_LED_PIN, machine.Pin.OUT, machine.Pin.PULL_UP)
        led_onoff(0)
    print('done.')

    print('enable station interface and connect to WiFi access point ...')
    network.hostname('wifi-uart-tool')
    print('hostname:', network.hostname())
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print(f'connecting to network "{CFG_WLAN_SSID}"...', end='')
    wlan.connect(CFG_WLAN_SSID, CFG_WLAN_PASS)
    while not wlan.isconnected():
        print('.', end='')
        led_onoff(1)
        time.sleep(1)
        led_onoff(0)
    print('')
    led_onoff(0)
    local_ip, subnet, gateway, dns = wlan.ifconfig()
    print('network config:')
    print(f'  - ip     : {local_ip}')
    print(f'  - subnet : {subnet}')
    print(f'  - gateway: {gateway}')
    print(f'  - dns    : {dns}')
    print('done.')

    print('init uart ...')
    uart1 = machine.UART(1, baudrate=CFG_UART_BAUD, tx=CFG_UART_PIN_TX, rx=CFG_UART_PIN_RX)
    print('done.')

async def process_request(req, writer, conn_id):
    HTTP_METHOD = req.method
    HTTP_PATH   = req.path
    HTTP_BODY   = req.body
    # --------------------------
    # http router
    if HTTP_METHOD == 'GET' and \
        (HTTP_PATH == '/' or HTTP_PATH == '/index.html'):
        text_html = ''
        with open('/index.html', 'r', encoding='utf8') as f:
            text_html = f.read()
            text_html = text_html.replace("${INFO}", f'SerialPort Viewer (BAUD={CFG_UART_BAUD} TX={CFG_UART_PIN_TX} RX={CFG_UART_PIN_RX})')
        rsp = HttpRsp(200) \
            .add_header('Server: mpy') \
            .add_header('Content-Type: text/html') \
            .set_data(text_html, compress=True)
        print('>>>>>>>>>> HTTP RESPONSE')
        print(rsp)
        writer.write(rsp.make())
        await writer.drain()
    elif HTTP_METHOD == 'GET' and HTTP_PATH == '/log':
        rsp = HttpRsp(200) \
            .add_header('Server: mpy') \
            .add_header('Content-Type: text/event-stream') \
            .add_header('Cache-Control: no-cache')
        print('>>>>>>>>>> HTTP RESPONSE')
        print(rsp)
        writer.write(rsp.make())
        await writer.drain()
        # clean old connections
        if conn_id in event_stream_conns:
            print('clean old event-stream')
            conn = event_stream_conns[conn_id]
            conn['writer'].close()
        event_stream_conns[conn_id] = dict()
        event_stream_conns[conn_id]['writer'] = writer
    elif HTTP_PATH == '/settings' and HTTP_METHOD == 'GET':
        text_html = ''
        with open('/settings.html', 'r', encoding='utf8') as f:
            text_html = f.read() \
                .replace('${CURRENT_VAL}', '\n'.join(read_user_settings(False)))
        rsp = HttpRsp(200) \
            .add_header('Server: mpy') \
            .add_header('Content-Type: text/html') \
            .set_data(text_html, compress=True)
        print('>>>>>>>>>> HTTP RESPONSE')
        print(rsp)
        writer.write(rsp.make())
        await writer.drain()
    elif HTTP_METHOD == 'POST':
        ok = False
        errMsg = None
        if HTTP_BODY:
            if HTTP_PATH == '/settings':
                try:
                    setting_val = HTTP_BODY.decode('utf8')
                    print('write settings:')
                    print(setting_val)
                    save_user_settings(setting_val)
                    ok = True
                except Exception as e:
                    errMsg = str(e)
            elif HTTP_PATH == '/cmd':
                value = HTTP_BODY.decode('utf8')
                if value == 'reboot':
                    async def delay_reboot():
                        await asyncio.sleep(3)
                        machine.reset()
                    asyncio.create_task(delay_reboot())
                    ok = True
                else:
                    errMsg = 'unknown cmd: ' + value
            else:
                errMsg = 'Invalid path: ' + HTTP_PATH
        else:
            errMsg = 'Body Cannot be empty !'
        rsp = HttpRsp(200 if ok else 400) \
            .add_header('Server: mpy') \
            .set_data(errMsg)
        print('>>>>>>>>>> HTTP RESPONSE')
        print(rsp)
        writer.write(rsp.make())
        await writer.drain()
    else:
        rsp = HttpRsp(404)
        if HTTP_METHOD == 'POST':
            rsp.set_status(403)
        else:
            text_html = ''
            with open('/404.html', 'r', encoding='utf8') as f:
                text_html = f.read()
            rsp.set_data(text_html)
        rsp.add_header('Server: mpy') \
            .add_header('Content-Type: text/html; charset=UTF-8')
        print('>>>>>>>>>> HTTP RESPONSE')
        print(rsp)
        writer.write(rsp.make())
        await writer.drain()

async def http_handler(reader, writer):
    addr = reader.get_extra_info('peername')
    http_conn_id = f'{addr[0]}:{addr[1]}'
    print('connection established:', addr)
    try:
        while True:
            req = HttpReq()
            while True:
                rx = await reader.read(1)
                if not rx:
                    raise Exception('no recv data')
                for b in rx:
                    req.intput(b)
                if req.done:
                    break
            print('<<<<<<<<<< HTTP REQUEST')
            print(req)
            await process_request(req, writer, http_conn_id)
            # Connection:keep-alive ?
            if req.header.get('Connection', 'keep-alive') == 'close':
                writer.close()
                break
    except Exception as e:
        print(f'connection {http_conn_id} broken:', e)
    finally:
        print(f'connection {http_conn_id} closed.')

async def rmt_recorder_process():
    while True:
        try:
            _host = CFG_RMT_SERVER
            _port = CFG_RMT_PORT
            print(f'connect remote recorder "{_host}:{_port}" ...')
            reader, writer = await asyncio.open_connection(_host, _port)
            print('remote recorder established.')
            try:
                writer.write(f'data: ---------- remote recorder startuped, tag: {CFG_DEVICE_TAG} ----------\n\n'.encode())
                await writer.drain()
            except:
                print(f'invalid remote recorder {_host}:{_port}, retry after 5min')
                await asyncio.sleep(5 * 60)
                continue
            # start
            rmt_recorder['evt.abort'].clear()
            rmt_recorder['writer'] = writer
            await rmt_recorder['evt.abort'].wait()
            rmt_recorder['writer'] = None
            writer.close()
            print('fail to write into recorder.')
        except Exception as e:
            print('remote recorder abort:', e)
        finally:
            print('reconnect after 10sec...')
            await asyncio.sleep(10)

async def send_to_web_terminal(tx_buffer):
    global event_stream_conns
    delList = []
    for k in event_stream_conns:
        try:
            conn = event_stream_conns[k]
            conn['writer'].write(tx_buffer)
            await conn['writer'].drain()
        except Exception as e:
            print('fail to write into event-stream:', e)
            conn['writer'].close()
            delList.append(k)
    for k in delList:
        print('delete event-stream:', k)
        del event_stream_conns[k]

async def send_to_remote_recorder(tx_buffer):
    global rmt_recorder
    if rmt_recorder['writer']:
        try:
            rmt_recorder['writer'].write(tx_buffer)
            await rmt_recorder['writer'].drain()
        except Exception as e:
            print('fail to write into remote recorder:', e)
            rmt_recorder['writer'] = None
            rmt_recorder['evt.abort'].set()

async def uart_handler():
    log_line = bytearray(f'data: [{CFG_DEVICE_TAG}] '.encode())
    last_active_time = time.time()
    while True:
        if uart1.any() == 0:
            await asyncio.sleep_ms(50)
            if time.time() > last_active_time + 40:
                last_active_time = time.time()
                print('send keepalive.')
                _buf = ': keepalive\n\n'.encode()
                await send_to_remote_recorder(_buf)
                await send_to_web_terminal(_buf)
            continue
        rx = uart1.read()
        if not rx:
            continue
        # process data
        last_active_time = time.time()
        for b in rx:
            if b == 0x0D: # CR
                continue
            elif b == 0x0A: # LF
                log_line.append(0x0A)
                log_line.append(0x0A)
                tx_buffer = predecode(log_line)
                log_line = bytearray(f'data: [{CFG_DEVICE_TAG}] '.encode())
                # send log
                await send_to_web_terminal(tx_buffer)
                await send_to_remote_recorder(tx_buffer)
            else:
                log_line.append(b)

def led_onoff(on):
    global led1_pin
    if led1_pin:
        led1_pin.value(not on)

async def main():
    print('logger client startup ...')
    asyncio.create_task(uart_handler())
    if CFG_RMT_SERVER_EN:
        asyncio.create_task(rmt_recorder_process())
    print('server startup ...')
    server = await asyncio.start_server(http_handler, local_ip, 80, backlog=2)
    async with server:
        await server.wait_closed()
    print('exit.')
