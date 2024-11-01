const net = require('net');
const os  = require('os');
const fs  = require('fs');
const nodePath = require('path');
const util = require('util');

// global -----------------------------------------

let SRV_PORT = 60000;
if (process.env['MY_RMT_SRV_PORT'] && /^\d+$/.test(process.env['MY_RMT_SRV_PORT']))
    SRV_PORT = parseInt(process.env['MY_RMT_SRV_PORT'])

const logger = fs.createWriteStream('./server.log', { flags: 'a' });
logger.log = (...args) => {
    const formattedArgs = args.map(arg => {
        if (typeof(arg) == 'string') return arg;
        return util.inspect(arg, { showHidden: false, depth: null, colors: false });
    });
    const message = formattedArgs.join(' ');
    logger.write(message + os.EOL);
};

// recorder ----------------------------------------

function timeStamp(noDate) {
    const date = new Date();
    const time = {
        year:   date.getFullYear(),
        month:  date.getMonth() + 1,
        date:   date.getDate(),
        hour:   date.getHours(),
        minute: date.getMinutes(),
        second: date.getSeconds(),
        region: date.toTimeString().split(' ')[1]
    };
    if (noDate) {
        return `${time.hour.toString().padStart(2, '0')}:${time.minute.toString().padStart(2, '0')}:${time.second.toString().padStart(2, '0')}`;
    } else {
        return `${time.year}/${time.month.toString().padStart(2, '0')}/${time.date.toString().padStart(2, '0')}` 
            + ` ${time.hour.toString().padStart(2, '0')}:${time.minute.toString().padStart(2, '0')}:${time.second.toString().padStart(2, '0')}`;
    }
}

function dateTimeStampForFileName() {
    const date = new Date();
    const time = {
        year:   date.getFullYear(),
        month:  date.getMonth() + 1,
        date:   date.getDate()
    };
    return `${time.year}-${time.month.toString().padStart(2, '0')}-${time.date.toString().padStart(2, '0')}`;
}

// server ----------------------------------------

const server = net.createServer((socket) => {

    const peerAddr = socket.remoteAddress;
    if (peerAddr == undefined)
        return;

    logger.log('new connection:', peerAddr, 'at', timeStamp());

    const connCtx = new Map();

    try {
        fs.mkdirSync(`${peerAddr}`);
        connCtx.set('path', `${peerAddr}/${dateTimeStampForFileName()}.log`);
    } catch (error) {
        //nothing todo
    }

    // create standalone log file for every day
    connCtx.set('timer', setInterval(() => {
        const oname = nodePath.basename(connCtx.get('path'));
        const nname = `${dateTimeStampForFileName()}.log`;
        if (oname != nname) {
            connCtx.set('path', `${peerAddr}/${nname}`);
            const oldStream = connCtx.get('outStream');
            if (oldStream) {
                connCtx.set('outStream', fs.createWriteStream(connCtx.get('path'), { flags: 'a' }));
                oldStream.close();
            }
        }
    }, 1000));

    let chunk = '';
    socket.on('data', (data) => {
        let str = data.toString();
        for (const c of str) {
            chunk += c;
            if (c == '\n') {
                if (chunk.startsWith(':')) { // 以冒号开头的行为注释行，会被忽略
                    chunk = '';
                }
                else if (chunk.endsWith('\n\n')) {
                    chunk = chunk.substring(0, chunk.length - 1);
                    chunk = chunk.replace(/^data:/, `[${timeStamp(true)}]`);
                    if (chunk.trimEnd() != '') {
                        let stream = connCtx.get('outStream');
                        if (stream == undefined) {
                            stream = fs.createWriteStream(connCtx.get('path'), { flags: 'a' });
                            connCtx.set('outStream', stream);
                        }
                        stream.write(chunk);
                    }
                    chunk = '';
                }
            }
        }
    });
    socket.on('close', () => {
        chunk = chunk.replace(/^data:/, `[${timeStamp(true)}]`);
        if (chunk.trimEnd() != '') {
            const stream = connCtx.get('outStream');
            if (stream) {
                stream.write(chunk + '\n');
                stream.close();
            }
        }
        chunk = '';
        clearInterval(connCtx.get('timer'));
        logger.log(`connection ${peerAddr} closed.`);
    });
    socket.on('error', (err) => {
        logger.log(`socket '${peerAddr}' error:`);
        logger.log(err);
    });
});

server.on('error', (err) => {
    logger.log('server error:', err);
});

// Grab an arbitrary unused port.
server.listen(SRV_PORT, '0.0.0.0', () => {
    logger.log('opened server on:', server.address(), 'at', timeStamp());
});