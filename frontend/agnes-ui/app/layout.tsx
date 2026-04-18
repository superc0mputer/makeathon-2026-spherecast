import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Agnes UI',
  description: 'Minimal ingredient and substitution priority selector',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
