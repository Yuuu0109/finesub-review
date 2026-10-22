import { test } from "node:test";
import assert from "node:assert/strict";
import { mockIPC, clearMocks } from "@tauri-apps/api/mocks";

// Exercise the real official JS HTTP adapter; native networking is mocked here.
test("desktop transport retains CSRF, multipart files and binary downloads", async () => {
  const store = new Map<string, string>();
  Object.assign(globalThis, {
    isTauri: true,
    window: globalThis,
    location: { hash: "" },
    localStorage: { getItem: (k: string) => store.get(k) || null, setItem: (k: string, v: string) => store.set(k, v) },
  });
  let config: any;
  let read = false;
  mockIPC((command, args: any) => {
    if (command === "plugin:http|fetch") { config = args.clientConfig; return 1; }
    if (command === "plugin:http|fetch_send") return {
      status: 200, statusText: "OK", url: config.url,
      headers: [["content-type", "application/octet-stream"]], rid: 2,
    };
    if (command === "plugin:http|fetch_read_body") {
      if (read) return [1];
      read = true;
      return [80, 75, 0, 255, 0];
    }
    throw new Error(`Unexpected IPC command ${command}`);
  });
  try {
    const { request, savedServer, selectServer, scopedDraftKey } = await import("../src/transport.ts");
    assert.equal(savedServer(), "https://49.234.185.63");
    const form = new FormData();
    form.append("files", new Blob(["知识正文"], { type: "text/markdown" }), "知识.md");
    const response = await request("/imports", { method: "POST", headers: { "X-CSRF-Token": "test-csrf" }, body: form });
    assert.equal(config.url, "https://49.234.185.63/api/imports");
    assert.equal(config.maxRedirections, 0);
    assert.equal(config.method, "POST");
    const headers = new Headers(config.headers);
    assert.equal(headers.get("x-csrf-token"), "test-csrf");
    assert.match(headers.get("content-type")!, /^multipart\/form-data; boundary=/);
    const data = new TextDecoder().decode(new Uint8Array(config.data));
    assert.match(data, /知识.md/);
    assert.match(data, /知识正文/);
    assert.deepEqual(new Uint8Array(await response.arrayBuffer()), new Uint8Array([80, 75, 0, 255]));
    const oldKey = scopedDraftKey("same-user-and-entry");
    selectServer("https://another.example.com");
    assert.equal(savedServer(), "https://another.example.com");
    assert.notEqual(scopedDraftKey("same-user-and-entry"), oldKey);
  } finally {
    clearMocks();
  }
});
