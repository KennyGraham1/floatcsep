import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import { promises as fs } from 'fs';
import os from 'os';
import crypto from 'crypto';

export const dynamic = 'force-dynamic';

const execAsync = promisify(exec);

// In-memory cache for forecast data
const forecastCache = new Map<string, any>();

export async function POST(request: NextRequest) {
  let tempFilePath: string | null = null;
  try {
    const body = await request.json();
    const { path: forecastPath, modelIndex, timeWindow, isCatalogFc, region: regionData } = body;

    if (!forecastPath) {
      return NextResponse.json(
        { error: 'Forecast path required' },
        { status: 400 }
      );
    }

    // Check cache
    const cacheKey = `${modelIndex}|${timeWindow}`;
    if (forecastCache.has(cacheKey)) {
      console.log(`Cache hit for forecast: ${cacheKey}`);
      return NextResponse.json(forecastCache.get(cacheKey), {
        headers: {
          'Cache-Control': 'public, max-age=3600',
        },
      });
    }

    // Call Python subprocess
    const appRoot = process.env.APP_ROOT || '.';
    const pythonScript = path.join(process.cwd(), 'manifest_api.py');
    const regionStr = JSON.stringify(regionData || {});

    // Write region data to temp file to avoid command line length limits
    const tempDir = os.tmpdir();
    const tempFileName = `region-${crypto.randomUUID()}.json`;
    tempFilePath = path.join(tempDir, tempFileName);
    await fs.writeFile(tempFilePath, regionStr);

    const command = `python "${pythonScript}" load_forecast "${forecastPath}" "${appRoot}" "${tempFilePath}" "${isCatalogFc}"`;

    console.log(`Loading forecast: ${cacheKey}`);
    const { stdout, stderr } = await execAsync(command, { maxBuffer: 1024 * 1024 * 50 }); // Enable large buffer

    if (stderr) {
      console.error('Python stderr:', stderr);
    }

    const data = JSON.parse(stdout);

    if (data.error) {
      return NextResponse.json(
        { error: data.error },
        { status: 500 }
      );
    }

    // Cache result
    forecastCache.set(cacheKey, data);
    console.log(`Cached forecast: ${cacheKey} (${data.cells?.length || 0} cells)`);

    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'public, max-age=3600',
      },
    });
  } catch (error) {
    console.error('Error loading forecast:', error);
    return NextResponse.json(
      { error: 'Failed to load forecast data', details: String(error) },
      { status: 500 }
    );
  } finally {
    // Clean up temp file
    if (tempFilePath) {
      try {
        await fs.unlink(tempFilePath);
      } catch (err) {
        console.error('Failed to delete temp file:', err);
      }
    }
  }
}
