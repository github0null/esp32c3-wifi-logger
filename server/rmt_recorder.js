const net = require('net');
const os  = require('os');
const fs  = require('fs');
const nodePath = require('path');

// global -----------------------------------------

let SRV_PORT = 60000;
if (process.env['MY_RMT_SRV_PORT'] && /^\d+$/.test(process.env['MY_RMT_SRV_PORT']))
    SRV_PORT = parseInt(process.env['MY_RMT_SRV_PORT'])

const logger = fs.createWriteStream('./server.log', { flags: 'a' });

// recorder ----------------------------------------

function timeStamp() {
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
    return `${time.year}/${time.month.toString().padStart(2, '0')}/${time.date.toString().padStart(2, '0')}`
        + ` ${time.hour.toString().padStart(2, '0')}:${time.minute.toString().padStart(2, '0')}:${time.second.toString().padStart(2, '0')}`
        + ` ${time.region}`;
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

    logger.write(`new connection: ${peerAddr}` + os.EOL);

    const connCtx = new Map();

    try {
        fs.mkdirSync(`${peerAddr}.log`);
    } catch (error) {
        //nothing todo
    }

    connCtx.set('path', `${peerAddr}.log/${dateTimeStampForFileName()}.log`);
    connCtx.set('outStream', fs.createWriteStream(connCtx.get('path'), { flags: 'a' }));

    // create standalone log file for every day
    connCtx.set('timer', setInterval(() => {
        const oname = nodePath.basename(connCtx.get('path'));
        const nname = `${dateTimeStampForFileName()}.log`;
        if (oname != nname) {
            connCtx.set('path', `${peerAddr}.log/${nname}`);
            const oldStream = connCtx.get('outStream');
            connCtx.set('outStream', fs.createWriteStream(connCtx.get('path'), { flags: 'a' }));
            oldStream.close();
        }
    }, 1000));

    let chunk = '';
    socket.on('data', (data) => {
        let str = data.toString();
        for (const c of str) {
            chunk += c;
            if (c == '\n') {
                if (chunk.endsWith('\n\n')) {
                    chunk = chunk.substring(0, chunk.length - 1);
                    chunk = chunk.replace(/^data:/, `[${timeStamp()}]`);
                    if (chunk.trimEnd() != '')
                        connCtx.get('outStream').write(chunk);
                    chunk = '';
                }
            }
        }
    });
    socket.on('close', () => {
        chunk = chunk.replace(/^data:/, `[${timeStamp()}]`);
        if (chunk.trimEnd() != '')
            connCtx.get('outStream').write(chunk + '\n');
        chunk = '';
        clearInterval(connCtx.get('timer'));
        connCtx.get('outStream').close();
    });
});

server.on('error', (err) => {
    logger.write(`server error: ${err.message + err.stack}` + os.EOL);
});

// Grab an arbitrary unused port.
server.listen(SRV_PORT, '0.0.0.0', () => {
    logger.write(`opened server on ${server.address()} at ${timeStamp}` + os.EOL);
});