const net = require('net');
const os  = require('os');
const fs  = require('fs');

// global -----------------------------------------

let SRV_PORT = 60000;
if (process.env['MY_RMT_SRV_PORT'] && /^\d+$/.test(process.env['MY_RMT_SRV_PORT']))
    SRV_PORT = parseInt(process.env['MY_RMT_SRV_PORT'])

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

// server ----------------------------------------

const server = net.createServer((socket) => {

    const peerAddr = socket.remoteAddress;
    if (peerAddr == undefined)
        return;

    console.log('new connection:', peerAddr);
    const outStream = fs.createWriteStream(`./log_${peerAddr}.log`, { flags: 'a' });

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
                        outStream.write(chunk);
                    chunk = '';
                }
            }
        }
    });
    socket.on('close', () => {
        chunk = chunk.replace(/^data:/, `[${timeStamp()}]`);
        if (chunk.trimEnd() != '')
            outStream.write(chunk + '\n');
        chunk = '';
    });
});

server.on('error', (err) => {
    console.log('server error', err);
});

// Grab an arbitrary unused port.
server.listen(SRV_PORT, '0.0.0.0', () => {
    console.log('opened server on', server.address());
});