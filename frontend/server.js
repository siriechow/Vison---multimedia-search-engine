/**
 * Vison - Frontend Server
 * Express server with API proxy to Python backend
 */

const express = require('express');
const path = require('path');
const morgan = require('morgan');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

// Logging
app.use(morgan('dev'));

// View engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Static files
app.use(express.static(path.join(__dirname, 'public')));

// Parse JSON & form data
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Proxy API requests to Python backend
app.use('/api', createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true,
    pathRewrite: { '^/api': '/api' },
    onError: (err, req, res) => {
        console.error('Proxy error:', err.message);
        res.status(502).json({
            error: 'Backend service unavailable',
            details: 'Make sure the Python backend is running on ' + BACKEND_URL,
        });
    },
}));

// Proxy static files from backend
app.use('/static', createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true,
}));

// Main page
app.get('/', (req, res) => {
    res.render('index', {
        title: 'Vison — Multimedia Search Engine',
        backendUrl: BACKEND_URL,
    });
});

// Start server
app.listen(PORT, () => {
    console.log(`\n  🔍 Vison Frontend`);
    console.log(`  ─────────────────────────────`);
    console.log(`  🌐 UI:      http://localhost:${PORT}`);
    console.log(`  🔗 Backend: ${BACKEND_URL}`);
    console.log(`  ─────────────────────────────\n`);
});
