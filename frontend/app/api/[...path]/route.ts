import { type NextRequest } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

// Headers that must not be forwarded to the backend
const DROP_REQUEST_HEADERS = new Set([
  'host', 'connection', 'keep-alive', 'transfer-encoding', 'te',
  'trailers', 'upgrade', 'proxy-authenticate', 'proxy-authorization',
])

async function proxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<Response> {
  const { path } = await params
  const search = request.nextUrl.search
  const backendUrl = `${BACKEND_URL}/${path.join('/')}${search}`

  const forwardHeaders = new Headers()
  request.headers.forEach((value, key) => {
    if (!DROP_REQUEST_HEADERS.has(key.toLowerCase())) {
      forwardHeaders.set(key, value)
    }
  })

  const hasBody = request.method !== 'GET' && request.method !== 'HEAD'
  const body = hasBody ? await request.arrayBuffer() : undefined

  const backendResponse = await fetch(backendUrl, {
    method: request.method,
    headers: forwardHeaders,
    body,
    cache: 'no-store',
  })

  const responseHeaders = new Headers()
  backendResponse.headers.forEach((value, key) => {
    // set-cookie must use append to preserve multiple values
    if (key.toLowerCase() === 'set-cookie') {
      responseHeaders.append(key, value)
    } else {
      responseHeaders.set(key, value)
    }
  })

  return new Response(backendResponse.body, {
    status: backendResponse.status,
    headers: responseHeaders,
  })
}

export const GET = proxy
export const POST = proxy
export const PUT = proxy
export const PATCH = proxy
export const DELETE = proxy
export const OPTIONS = proxy
export const HEAD = proxy
