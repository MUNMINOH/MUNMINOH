// CADENCE 매도·매수 의뢰 → 노션 데이터베이스
// POST https://api.bldgrunner.com/inquiry  (JSON, 사이트 의뢰서가 보냄)
// 환경 변수: NOTION_DB (데이터베이스 ID), NOTION_TOKEN (노션 통합 시크릿, Cloudflare 시크릿으로 저장)

const ALLOWED_ORIGINS = ["https://cadence.bldgrunner.com", "https://munminoh.github.io"];

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const cors = {
      "Access-Control-Allow-Origin": ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0],
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
      "Vary": "Origin",
    };
    const reply = (body, status = 200) =>
      new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json; charset=utf-8" } });

    const url = new URL(request.url);
    if (url.pathname !== "/inquiry") return reply({ ok: false, error: "not_found" }, 404);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method !== "POST") return reply({ ok: false, error: "method" }, 405);
    if (!ALLOWED_ORIGINS.includes(origin)) return reply({ ok: false, error: "origin" }, 403);
    if (!env.NOTION_TOKEN || !env.NOTION_DB) return reply({ ok: false, error: "not_configured" }, 503);

    let b;
    try { b = await request.json(); } catch { return reply({ ok: false, error: "bad_json" }, 400); }
    if (b && b._honey) return reply({ ok: true }); // 스팸 봇은 조용히 무시

    const clip = (v, n) => String(v ?? "").trim().slice(0, n);
    const kind = b["의뢰 종류"] === "매수" ? "매수" : "매도";
    const name = clip(b["이름"], 100);
    const phone = clip(b["연락처"], 40);
    if (!name || phone.replace(/\D/g, "").length < 9) return reply({ ok: false, error: "invalid" }, 400);
    const place = clip(kind === "매도" ? b["건물 위치"] : b["희망 지역"], 200);
    const amount = clip(kind === "매도" ? b["희망 매도가"] : b["예산"], 100);
    const memo = clip(b["문의 내용"], 1900);
    const text = t => (t ? [{ type: "text", text: { content: t } }] : []);

    const res = await fetch("https://api.notion.com/v1/pages", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.NOTION_TOKEN}`,
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        parent: { database_id: env.NOTION_DB },
        properties: {
          "이름": { title: text(name) },
          "의뢰 종류": { select: { name: kind } },
          "연락처": { phone_number: phone },
          "위치·지역": { rich_text: text(place) },
          "금액": { rich_text: text(amount) },
          "문의 내용": { rich_text: text(memo) },
          "상태": { status: { name: "신규" } },
        },
      }),
    });
    if (!res.ok) {
      console.log("notion error", res.status, await res.text());
      return reply({ ok: false, error: "notion" }, 502);
    }
    return reply({ ok: true });
  },
};
