let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}

function tabId() {
  const key = "siteforge-tab";
  try {
    let id = sessionStorage.getItem(key) || "";
    if (!/^[A-Za-z0-9_-]{16,64}$/.test(id)) {
      const bytes = new Uint8Array(18);
      crypto.getRandomValues(bytes);
      id = btoa(String.fromCharCode(...bytes))
        .replaceAll("+", "-")
        .replaceAll("/", "_")
        .replace(/=+$/, "");
      sessionStorage.setItem(key, id);
    }
    return id;
  } catch {
    return "";
  }
}

function requestHeaders(extra: Record<string, string> = {}) {
  const id = tabId();
  return {
    ...(id ? { "X-Tab-Id": id } : {}),
    ...extra,
  };
}

export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    credentials: "include",
    headers: requestHeaders({
      "Content-Type": "application/json",
      ...(method !== "GET" && path !== "/auth/login" ? { "X-CSRF-Token": csrf } : {}),
    }),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`Request failed (${response.status})`);
    }
    if (response.status === 401 && path !== "/auth/login")
      window.dispatchEvent(new Event("session-expired"));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  }
  return response.json();
}
export async function postForm<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch("/api" + path, {
    method: "POST",
    credentials: "include",
    headers: requestHeaders({ "X-CSRF-Token": csrf }),
    body,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string" ? data.detail : "Upload failed",
    );
  }
  return response.json();
}
export async function fetchBlob(path: string): Promise<Blob> {
  const response = await fetch("/api" + path, {
    credentials: "include",
    headers: requestHeaders(),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string" ? data.detail : "The file could not be loaded",
    );
  }
  return response.blob();
}
export async function downloadFile(path: string, name: string) {
  const response = await fetch("/api" + path, {
    credentials: "include",
    headers: requestHeaders(),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string" ? data.detail : "Download failed",
    );
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
export async function upload<T>(
  path: string,
  file: File,
  category: string,
  extra?: Record<string, string>,
): Promise<T> {
  const body = new FormData();
  body.set("category", category);
  Object.entries(extra || {}).forEach(([key, value]) => body.set(key, value));
  body.set("upload", file);
  const response = await fetch("/api" + path, {
    method: "POST",
    credentials: "include",
    headers: requestHeaders({ "X-CSRF-Token": csrf }),
    body,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string" ? data.detail : "Upload failed",
    );
  }
  return response.json();
}
