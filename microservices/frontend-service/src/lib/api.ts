const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api"

class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${endpoint}`

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  })

  if (!response.ok) {
    const message = await response.text().catch(() => response.statusText)
    throw new ApiError(response.status, message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export function get<T>(endpoint: string): Promise<T> {
  return request<T>(endpoint)
}

export function post<T>(endpoint: string, data: unknown): Promise<T> {
  return request<T>(endpoint, {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export function put<T>(endpoint: string, data: unknown): Promise<T> {
  return request<T>(endpoint, {
    method: "PUT",
    body: JSON.stringify(data),
  })
}

export function del<T>(endpoint: string): Promise<T> {
  return request<T>(endpoint, {
    method: "DELETE",
  })
}

export { ApiError }
