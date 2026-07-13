const express = require('express');
const path = require('path');
const uploadx = require('uploadx');

const app = express();
const PORT = 3000;

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve frontend dashboard/demo
app.use(express.static(path.join(__dirname, 'public')));

/**
 * 1. Single File Upload Middleware
 * Automatically streams directly client -> express -> fastapi, compressing on fastapi, saving to self-hosted engine
 */
app.post('/api/upload', uploadx.single('file', {
  compress: true,
  autoFormat: true,
  maxSize: '100MB'
}), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ status: 'error', message: 'No file uploaded' });
  }
  res.json({
    status: 'success',
    file: req.file
  });
});

/**
 * 2. Multi File Upload Middleware
 */
app.post('/api/upload-multi', uploadx.array('files', 5, {
  compress: true,
  autoFormat: true
}), (req, res) => {
  if (!req.files || req.files.length === 0) {
    return res.status(400).json({ status: 'error', message: 'No files uploaded' });
  }
  res.json({
    status: 'success',
    files: req.files
  });
});

/**
 * 3. Playwright Automation Capture
 */
app.post('/api/capture', async (req, res) => {
  const { url, formatType } = req.body;
  if (!url) {
    return res.status(400).json({ status: 'error', message: 'URL is required' });
  }

  try {
    const axios = require('axios');
    const FormData = require('form-data');
    const form = new FormData();
    form.append('url', url);
    form.append('format_type', formatType || 'screenshot');

    const response = await axios.post(`${uploadx.engineUrl}/automation/capture`, form, {
      headers: form.getHeaders()
    });
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ status: 'error', message: error.message });
  }
});

/**
 * 4. Get File Metadata
 */
app.get('/api/file/:id', async (req, res) => {
  try {
    const axios = require('axios');
    const response = await axios.get(`${uploadx.engineUrl}/file/${req.params.id}`);
    res.json(response.data);
  } catch (error) {
    res.status(404).json({ status: 'error', message: error.message });
  }
});

/**
 * 5. Delete File
 */
app.delete('/api/file/:id', async (req, res) => {
  try {
    const axios = require('axios');
    const response = await axios.delete(`${uploadx.engineUrl}/file/${req.params.id}`);
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ status: 'error', message: error.message });
  }
});

app.listen(PORT, () => {
  console.log(`🚀 SmartUploader Demo Express Server running at http://localhost:${PORT}`);
});
