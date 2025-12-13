import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execAsync = promisify(exec);

// In-memory cache for forecast data
const forecastCache = new Map<string, any>();

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const forecastPath = searchParams.get('path');
    const modelIndex = searchParams.get('modelIndex');
    const timeWindow = searchParams.get('timeWindow');
    const isCatalogFc = searchParams.get('isCatalogFc') === 'true';
    const regionData = searchParams.get('region');

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

    const command = `python "${pythonScript}" load_forecast "${forecastPath}" "${appRoot}" '${regionData || '{}'}' "${isCatalogFc}"`;

    console.log(`Loading forecast: ${cacheKey}`);
    const { stdout, stderr } = await execAsync(command);

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
  }
}
