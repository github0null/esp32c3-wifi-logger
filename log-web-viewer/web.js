const express = require('express');
const expressWs = require('express-ws');
const fs = require('fs');
const path = require('path');

// 初始化 Express 应用
const app = express();
expressWs(app);

// 设置静态文件目录
app.use(express.static(path.join(__dirname, 'public')));

// 列出目录内容的路由
app.get('/browse/', (req, res) => {
    console.log(`browse logs`);
    const dirPath = path.join(__dirname, 'logs');
    fs.readdir(dirPath, (err, files) => {
        if (err) {
            console.log('error:', err.message);
            return res.status(500).send(err.message);
        }
        res.json(files.map(file => ({
            name: file,
            isDirectory: fs.statSync(path.join(dirPath, file)).isDirectory()
        })));
    });
});
app.get('/browse/:dir', (req, res) => {
    console.log(`browse logs/${req.params.dir}`);
    const dirPath = path.join(__dirname, 'logs', req.params.dir);
    fs.readdir(dirPath, (err, files) => {
        if (err) {
            console.log('error:', err.message);
            return res.status(500).send(err.message);
        }
        res.json(files.map(file => ({
            name: file,
            isDirectory: fs.statSync(path.join(dirPath, file)).isDirectory()
        })));
    });
});

// WebSocket 路由
app.ws('/ws/:filePath', function(ws, req) {
  console.log('get file:', 'logs/' + req.params.filePath);
  const filePath = path.join(__dirname, 'logs', req.params.filePath); // 日志文件路径
  const tail = fs.createReadStream(filePath, { flags: 'r', encoding: 'utf8', fd: null });

  let isClosed = false;

  // 当有新的数据可读时发送给客户端
  tail.on('data', chunk => {
    if (!isClosed) {
      ws.send(chunk);
    }
  });

  // 关闭连接时释放资源
  ws.on('close', () => {
    isClosed = true;
    tail.close();
  });
});

// 启动服务器
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server is running on port http://localhost:${PORT}`);
});