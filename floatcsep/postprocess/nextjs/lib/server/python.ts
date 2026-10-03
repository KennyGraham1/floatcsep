import { execFile } from 'child_process';
import crypto from 'crypto';
import fs from 'fs/promises';
import path from 'path';
import { HttpError } from './http';

/** Bump together with FORMAT_VERSION in manifest_api.py. */
const DATA_VERSION = 7;

const SCRIPT = path.join(process.cwd(), 'manifest_api.py');

// `floatcsep view` passes its own interpreter; a bare `python` may be another env.
const pythonExecutable = () => process.env.FLOATCSEP_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');

const cacheDir = () => process.env.FLOATCSEP_DASHBOARD_CACHE || path.join(process.cwd(), '.cache', 'data');

const inflight = new Map<string, Promise<string>>();

/** A cache key that changes whenever the source file (or the request) changes. */
export async function sourceKey(kind: string, file: string, extra: unknown = null): Promise<string> {
  let stat;
  try {
    stat = await fs.stat(file);
  } catch {
    throw new HttpError(404, `File not found: ${path.basename(file)}`, file);
  }
  const identity = JSON.stringify({ v: DATA_VERSION, kind, file, mtime: stat.mtimeMs, size: stat.size, extra });
  return crypto.createHash('sha1').update(identity).digest('hex');
}

/**
 * Return the path of the output for `key` (a JSON document, or `extension`),
 * running the Python helper to create it when it is not cached yet. Concurrent
 * requests share one run.
 */
export async function cachedPythonJob(key: string, args: string[], extension = '.json'): Promise<string> {
  const out = path.join(cacheDir(), `${key}${extension}`);
  try {
    await fs.access(out);
    return out;
  } catch {
    // not cached yet
  }

  let job = inflight.get(key);
  if (!job) {
    job = (async () => {
      await fs.mkdir(cacheDir(), { recursive: true });
      await runPython([...args, '--out', out]);
      return out;
    })().finally(() => inflight.delete(key));
    inflight.set(key, job);
  }
  return job;
}

function lastJsonLine(stdout: string): { ok?: boolean; error?: string } | null {
  const lines = stdout.trim().split(/\r?\n/).reverse();
  for (const line of lines) {
    try {
      return JSON.parse(line);
    } catch {
      // not the status line
    }
  }
  return null;
}

function runPython(args: string[]): Promise<void> {
  const python = pythonExecutable();
  return new Promise((resolve, reject) => {
    execFile(
      python,
      [SCRIPT, ...args],
      {
        maxBuffer: 32 * 1024 * 1024,
        timeout: 30 * 60 * 1000,
        windowsHide: true,
        env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONWARNINGS: 'ignore' },
      },
      (error, stdout, stderr) => {
        const status = lastJsonLine(stdout);
        if (!error && status?.ok) {
          resolve();
          return;
        }
        const log = stderr.trim().split(/\r?\n/).slice(-15).join('\n');
        if ((error as NodeJS.ErrnoException | null)?.code === 'ENOENT') {
          reject(
            new HttpError(
              500,
              `Python interpreter not found: ${python}`,
              'Set FLOATCSEP_PYTHON, or launch the dashboard with `floatcsep view <config> --ui nextjs`.',
            ),
          );
          return;
        }
        reject(new HttpError(500, status?.error || error?.message || 'The Python data loader failed', log));
      },
    );
  });
}
