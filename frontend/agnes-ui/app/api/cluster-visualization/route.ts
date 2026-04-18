import fs from 'node:fs'

import { NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const clusterHtmlPath = '/Users/maiafilip/Desktop/network_global_clusters.html'

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
