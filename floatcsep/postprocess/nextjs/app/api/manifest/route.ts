import { NextResponse } from 'next/server';
import fs from 'fs/promises';

export async function GET() {
  try {
    const manifestPath = process.env.MANIFEST_PATH;

    if (!manifestPath) {
      return NextResponse.json(
        { error: 'Manifest path not configured. Set MANIFEST_PATH environment variable.' },
        { status: 500 }
      );
    }

    const data = await fs.readFile(manifestPath, 'utf-8');
    const manifest = JSON.parse(data);

    return NextResponse.json(manifest, {
      headers: {
        'Cache-Control': 'public, max-age=3600',
      },
    });
  } catch (error) {
    console.error('Error loading manifest:', error);
    return NextResponse.json(
      { error: 'Failed to load manifest', details: String(error) },
      { status: 500 }
    );
  }
}
