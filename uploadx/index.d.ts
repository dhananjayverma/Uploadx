import { Request, Response, NextFunction } from 'express';

export interface UploadOptions {
  /**
   * Whether to compress files automatically (e.g. WebP conversion for images).
   * @default true
   */
  compress?: boolean;
  /**
   * Whether to auto-convert image formats to WebP.
   * @default true
   */
  autoFormat?: boolean;
  /**
   * Max size limit for files (e.g., '100MB', '500KB').
   * @default '100MB'
   */
  maxSize?: string;
}

export interface FileMetadata {
  id: string;
  filename: string;
  original_name: string;
  mime_type: string;
  size: number;
  hash: string;
  category: 'images' | 'videos' | 'docs' | 'temp';
  path: string;
  url: string;
  created_at: string;
}

declare global {
  namespace Express {
    interface Request {
      file?: FileMetadata;
      files?: FileMetadata[];
    }
  }
}

/**
 * Middleware for single file upload.
 * Streams file directly to the FastAPI processing backend.
 */
export function single(fieldName: string, options?: UploadOptions): (req: Request, res: Response, next: NextFunction) => void;

/**
 * Middleware for multiple files upload.
 * Streams array of files directly to the FastAPI processing backend.
 */
export function array(fieldName: string, maxCount?: number, options?: UploadOptions): (req: Request, res: Response, next: NextFunction) => void;

export const engineUrl: string;
