const Busboy = require("busboy");
const axios = require("axios");
const FormData = require("form-data");

const ENGINE_URL = process.env.SMART_UPLOADER_ENGINE_URL || "http://localhost:8000";

/**
 * Express middleware for streaming a single file directly to the FastAPI engine.
 */
function uploadSingle(fieldName, options = {}) {
  return (req, res, next) => {
    let busboy;
    try {
      busboy = Busboy({ headers: req.headers });
    } catch (err) {
      return next(new Error(`Failed to initialize Busboy: ${err.message}`));
    }

    let uploadPromise = null;
    let fileUploaded = false;

    busboy.on("file", (name, fileStream, info) => {
      const { filename, mimeType } = info;
      
      if (name !== fieldName) {
        // Skip files that do not match our fieldName
        fileStream.resume();
        return;
      }

      fileUploaded = true;
      const form = new FormData();
      
      // Append the live readable stream directly to the multipart payload.
      // This streams data directly from Client -> Express -> FastAPI!
      form.append("file", fileStream, {
        filename: filename,
        contentType: mimeType
      });

      // Pass configuration flags
      const compress = options.compress !== undefined ? options.compress : true;
      const autoFormat = options.autoFormat !== undefined ? options.autoFormat : true;
      
      form.append("compress", String(compress));
      form.append("autoFormat", String(autoFormat));
      
      if (options.maxSize) {
        form.append("maxSize", String(options.maxSize));
      }

      const activeEngineUrl = options.engineUrl || ENGINE_URL;

      uploadPromise = axios.post(`${activeEngineUrl}/upload`, form, {
        headers: {
          ...form.getHeaders()
        },
        maxContentLength: Infinity,
        maxBodyLength: Infinity
      }).then(res => res.data.data || res.data);
    });

    busboy.on("finish", async () => {
      if (!fileUploaded) {
        return next(new Error(`No file found in field "${fieldName}"`));
      }

      try {
        // Wait for the FastAPI upload to complete
        req.file = await uploadPromise;
        next();
      } catch (err) {
        const errorMsg = err.response?.data?.detail || err.message;
        next(new Error(`SmartUploader Engine Error: ${errorMsg}`));
      }
    });

    busboy.on("error", (err) => {
      next(err);
    });

    req.pipe(busboy);
  };
}

/**
 * Express middleware to handle streaming multiple files.
 */
function uploadArray(fieldName, maxCount = 10, options = {}) {
  return (req, res, next) => {
    let busboy;
    try {
      busboy = Busboy({ headers: req.headers });
    } catch (err) {
      return next(new Error(`Failed to initialize Busboy: ${err.message}`));
    }

    const uploadPromises = [];
    req.files = [];

    busboy.on("file", (name, fileStream, info) => {
      const { filename, mimeType } = info;

      if (name !== fieldName) {
        fileStream.resume();
        return;
      }

      if (uploadPromises.length >= maxCount) {
        fileStream.resume();
        return;
      }

      const form = new FormData();
      form.append("file", fileStream, {
        filename: filename,
        contentType: mimeType
      });

      const compress = options.compress !== undefined ? options.compress : true;
      const autoFormat = options.autoFormat !== undefined ? options.autoFormat : true;
      form.append("compress", String(compress));
      form.append("autoFormat", String(autoFormat));

      const activeEngineUrl = options.engineUrl || ENGINE_URL;

      const p = axios.post(`${activeEngineUrl}/upload`, form, {
        headers: {
          ...form.getHeaders()
        },
        maxContentLength: Infinity,
        maxBodyLength: Infinity
      }).then(res => res.data.data || res.data);

      uploadPromises.push(p);
    });

    busboy.on("finish", async () => {
      if (uploadPromises.length === 0) {
        return next();
      }

      try {
        req.files = await Promise.all(uploadPromises);
        next();
      } catch (err) {
        const errorMsg = err.response?.data?.detail || err.message;
        next(new Error(`SmartUploader Engine Error: ${errorMsg}`));
      }
    });

    busboy.on("error", (err) => {
      next(err);
    });

    req.pipe(busboy);
  };
}

module.exports = {
  single: uploadSingle,
  array: uploadArray,
  engineUrl: ENGINE_URL
};
