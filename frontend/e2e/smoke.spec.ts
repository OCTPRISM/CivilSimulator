/**
 * PR smoke: auth → create session → step → restore (mock LLM backend).
 * Runs against CIVSIM_API_BASE (default http://127.0.0.1:8000).
 */
import { test, expect } from "@playwright/test";

const API = process.env.CIVSIM_API_BASE || "http://127.0.0.1:8000";

test.describe("main path smoke", () => {
  test("register → create → step → restore", async ({ request }) => {
    const uname = `pw_${Date.now().toString(36)}`;
    const password = "pw-smoke-pass-99";

    const health = await request.get(`${API}/api/health`);
    expect(health.ok(), await health.text()).toBeTruthy();

    const reg = await request.post(`${API}/api/auth/register`, {
      data: { username: uname, password, display_name: "pw" },
    });
    expect(reg.ok(), await reg.text()).toBeTruthy();
    const { token } = await reg.json();
    expect(token).toBeTruthy();
    const auth = { Authorization: `Bearer ${token}` };

    const created = await request.post(`${API}/api/sessions`, {
      headers: auth,
      data: {
        seed_key: "ancient",
        category_key: "official",
        variant_key: "student",
      },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const createdBody = await created.json();
    const sid = createdBody.session.id as string;
    const pid = createdBody.session.player_id as string;
    expect(sid).toMatch(/^sess_/);
    expect(pid).toBeTruthy();

    const step = await request.post(`${API}/api/sessions/${sid}/step`, {
      headers: {
        ...auth,
        "Idempotency-Key": `pw-step-${Date.now()}`,
      },
      data: { input: "我环顾四周。", player_id: pid },
    });
    expect(step.ok(), await step.text()).toBeTruthy();
    const stepBody = await step.json();
    expect(stepBody.page).toBeTruthy();
    expect(typeof stepBody.revision).toBe("number");

    // Process-restart simulation: restore from snapshot (step force-saves).
    const restored = await request.post(`${API}/api/sessions/${sid}/restore`, {
      headers: auth,
    });
    expect(restored.ok(), await restored.text()).toBeTruthy();
    const restBody = await restored.json();
    expect(restBody.restored === true || restBody.session?.id === sid).toBeTruthy();
    expect(restBody.session?.id).toBe(sid);
    expect(restBody.session?.player_id).toBe(pid);

    // Envelope on unauthorized
    const bare = await request.post(`${API}/api/sessions/${sid}/step`, {
      data: { input: "no auth" },
    });
    expect(bare.status()).toBe(401);
    const err = await bare.json();
    expect(err.error?.code).toBe("AUTH_REQUIRED");
  });
});
