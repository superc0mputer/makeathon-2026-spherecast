import fs from 'node:fs'
import path from 'node:path'

import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

// Correctly join the root directory with the path to the file
const clusterHtmlPath = path.join(
  process.cwd(),
  'app',
  'api',
  'cluster-visualization',
  'network_global_clusters.html'
)

export async function GET() {
  try {
    const html = fs.readFileSync(clusterHtmlPath, 'utf-8')
    return new NextResponse(html, {
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
      },
    })
  } catch (error) {
    console.error('Failed to load cluster visualization HTML', error)
    return NextResponse.json(
      { error: 'Cluster visualization file could not be loaded.' },
      { status: 404 },
    )
  }
}