export type Seed = {
  key: string;
  name: string;
  genre: string;
  premise: string;
  is_custom?: boolean;
};

export type Beat = {
  kind: "narration" | "speech" | "action" | "system";
  speaker: string | null;
  content: string;
};

export type StoryChoice = {
  label: string;
  hint: string;
  action: string;
};

export type Page = {
  page_no: number;
  chapter: string;
  scene: {
    location_id: string;
    location_name: string;
    summary: string;
    present_agent_ids: string[];
  };
  beats: Beat[];
  choices: StoryChoice[];
  tension?: number;
};

export type InventoryItem = {
  id: string;
  name: string;
  kind: string;
  qty: number;
  meta?: Record<string, unknown>;
};

export type GameTask = {
  id: string;
  title: string;
  description: string;
  source: "work" | "story" | "self" | string;
  status: "open" | "completed" | "failed" | string;
  rewards: { gold?: number; food?: string[]; equipment?: string[] };
  tick_created: number;
  tick_deadline?: number | null;
  location_id?: string | null;
  keywords?: string[];
};

export type ScheduledInjection = {
  id: string;
  tick: number;
  kind: "event" | "character";
  payload: Record<string, unknown>;
  fired: boolean;
};

export type AgentSkill = {
  id: string;
  name: string;
  kind: "basic" | "unique" | string;
  description?: string;
  cooldown: number;
  last_used_tick?: number;
  action_prompt?: string;
  ready: boolean;
};

export type Agent = {
  id: string;
  name: string;
  kind: "player" | "npc";
  persona: string;
  goals: string[];
  traits: string[];
  location_id: string | null;
  relations?: Record<string, number>;
  avatar?: string;
  appearance?: { figure?: string; category?: string; skin?: string };
  profession?: string;
  schedule?: { from: number; to: number; location: string; activity: string }[];
  economy?: {
    income_label?: string;
    income_per_unit?: number;
    unit?: string;
    daily_capacity?: number;
    daily_expenses?: number;
    starting_savings?: number;
    meal_tier?: string;
  };
  current_activity?: string;
  savings?: number;
  today_income?: number;
  today_customers?: number;
  last_meal_tier?: string;
  presence?: "active" | "dormant" | "proxy";
  dormant_since_tick?: number | null;
  last_observed_tick?: number;
  offline_mode?: string;
  offline_rationale?: string;
  world_x?: number;
  world_z?: number;
  behavior?: string;
  inventory?: InventoryItem[];
  equipment?: Record<string, unknown>;
  skills?: AgentSkill[];
};

export type WorldStats = {
  politics: number;
  economy: number;
  livelihood: number;
  military: number;
  environment: number;
  history: { politics: number; economy: number;
             livelihood: number; military: number; environment: number }[];
  summary: { politics: string; economy: string;
             livelihood: string; military: string; environment: string };
};

export type FinanceGood = {
  id: string;
  name: string;
  base: number;
  price: number;
  inventory: number;
  supply_tick: number;
  demand_tick: number;
  change_pct: number;
};

export type FinanceSnapshot = {
  seed: string;
  tick: number;
  price_index: number;
  inflation: number;
  money_supply: number;
  velocity: number;
  gini: number;
  volume: number;
  goods: FinanceGood[];
  shocks: {
    id: string; kind: string; good_id: string;
    magnitude: number; remaining: number; note: string;
  }[];
  history: {
    tick: number;
    price_index: number;
    inflation: number;
    money_supply: number;
    velocity: number;
    gini: number;
    volume: number;
    prices: Record<string, number>;
  }[];
  last_events?: { kind: string; summary: string; importance?: number }[];
  reproducible?: boolean;
  engine?: string;
};

export type MissedShard = {
  tick: number;
  kind: string;
  perceived: string;
  clarity: "rumour" | "fragment" | "miss" | string;
  importance: number;
  truth?: string;
};

export type WakeBriefing = {
  ticks_asleep: number;
  from_tick: number;
  to_tick: number;
  clock_label: string;
  narrative: string;
  offline_mode?: "sleep" | "proxy" | string;
  shards: MissedShard[];
  npc_shifts: { name: string; from: string; to: string; activity?: string }[];
  world_stats_hint: string;
};

export type Session = {
  id: string;
  world: any;
  agents: Agent[];
  player_id: string;
  player_ids?: string[];
  user_id?: string | null;
  seed_key?: string;
  pages: Page[];
  tension_curve?: number[];
  stats?: WorldStats;
  finance?: FinanceSnapshot | null;
  finance_lab?: Record<string, unknown> | null;
  simulation?: {
    provider: string;
    running: boolean;
    last_model: string;
    last_tick: number;
    last_error: string;
    last_reasoning: string;
    continuous: boolean;
  };
  injections?: ScheduledInjection[];
  tasks?: GameTask[];
};

export type User = {
  id: string;
  username: string;
  display_name: string;
  created_at: number;
};

export type CharacterVariant = {
  key: string;
  name: string;
  avatar?: string;
  figure?: string;
  persona: string;
  goals?: string[];
  traits?: string[];
  profession?: string;
  equipment?: Record<string, string>;
  starting_items?: { name: string; kind?: string; qty?: number }[];
};

export type CharacterCategory = {
  key: string;
  name: string;
  description: string;
  variants: CharacterVariant[];
};

export type PlayerCatalog = {
  seed_key: string;
  categories: CharacterCategory[];
};

const base = ""; // same-origin via Next rewrites

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("civsim_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch(url: string, init: RequestInit = {}) {
  const headers: Record<string, string> = {
    ...authHeaders(),
    ...(init.headers as Record<string, string> | undefined),
  };
  if (init.body && !headers["Content-Type"] && !(init.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const r = await fetch(url, { ...init, headers });
  if (!r.ok) {
    let msg = await r.text();
    try {
      const j = JSON.parse(msg);
      const d = j.detail;
      msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((x: { msg?: string }) => x.msg).join("; ") : j.error || j.message || msg;
    } catch { /* keep text */ }
    throw new Error(typeof msg === "string" ? msg.replace(/^Error:\s*/i, "") : "请求失败");
  }
  return r;
}

export async function listSeeds(): Promise<Seed[]> {
  const r = await apiFetch(`${base}/api/seeds`, { cache: "no-store" as RequestCache });
  const j = await r.json();
  return j.seeds;
}

export async function getPlayerCatalog(seedKey: string): Promise<PlayerCatalog> {
  const r = await apiFetch(`${base}/api/seeds/${seedKey}/characters`, { cache: "no-store" as RequestCache });
  return r.json();
}

export async function register(username: string, password: string, display_name = "") {
  const r = await apiFetch(`${base}/api/auth/register`, {
    method: "POST",
    body: JSON.stringify({ username, password, display_name }),
  });
  return r.json() as Promise<{ token: string; user: User }>;
}

export async function login(username: string, password: string) {
  const r = await apiFetch(`${base}/api/auth/login`, {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  return r.json() as Promise<{ token: string; user: User }>;
}

export async function getMe() {
  const r = await apiFetch(`${base}/api/auth/me`);
  return r.json() as Promise<{ user: User; sessions: { session_id: string; seed_key: string }[] }>;
}

export async function createSession(
  seed_key: string,
  opts: {
    description?: string;
    category_key?: string;
    variant_key?: string;
    skin?: string;
  } = {},
) {
  const r = await apiFetch(`${base}/api/sessions`, {
    method: "POST",
    body: JSON.stringify({
      seed_key,
      description: opts.description || "",
      category_key: opts.category_key,
      variant_key: opts.variant_key,
      skin: opts.skin,
    }),
  });
  return (await r.json()) as { session: Session; page: Page };
}

export async function stepSession(sid: string, input: string | null) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/step`, {
    method: "POST",
    body: JSON.stringify({ input }),
  });
  return (await r.json()) as { page: Page; stats?: WorldStats; session?: Session };
}

export async function talkToNpc(sid: string, npc_id: string, text: string) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/talk`, {
    method: "POST",
    body: JSON.stringify({ npc_id, text }),
  });
  return (await r.json()) as { npc_id: string; npc_name: string; reply: string };
}

export async function sendHeartbeat(sid: string, player_id?: string) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/heartbeat`, {
    method: "POST",
    body: JSON.stringify({ player_id }),
  });
  return r.json() as Promise<{ player_id: string; presence: string; tick: number }>;
}

export async function sleepSession(sid: string, reason = "manual") {
  const r = await apiFetch(`${base}/api/sessions/${sid}/sleep`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
  return r.json() as Promise<{
    presence: string;
    offline_mode?: string;
    offline_rationale?: string;
    dormant_since_tick: number;
    session: Session;
  }>;
}

export async function wakeSession(sid: string) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/wake`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  return r.json() as Promise<{
    already_awake: boolean;
    presence: string;
    briefing: WakeBriefing | null;
    session: Session;
  }>;
}

export async function injectEvent(
  sid: string, tick: number, summary: string, importance = 0.85,
) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/inject/event`, {
    method: "POST",
    body: JSON.stringify({ tick, summary, importance }),
  });
  return r.json() as Promise<{ injection: ScheduledInjection; session: Session }>;
}

export async function injectCharacter(
  sid: string, body: {
    tick: number; name: string; persona: string;
    profession?: string; location_id?: string; traits?: string[]; agent_kind?: string;
  },
) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/inject/character`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json() as Promise<{ injection: ScheduledInjection; session: Session }>;
}

export async function skipToTick(sid: string, target_tick: number) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/skip-to-tick`, {
    method: "POST",
    body: JSON.stringify({ target_tick }),
  });
  return r.json() as Promise<{ tick: number; steps: number; session: Session }>;
}

export async function useSkill(sid: string, skill_id: string, player_id?: string) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/use-skill`, {
    method: "POST",
    body: JSON.stringify({ skill_id, player_id }),
  });
  return (await r.json()) as { page: Page; stats?: WorldStats; session?: Session };
}

export async function createSelfTask(
  sid: string, title: string, description = "", rewards?: GameTask["rewards"],
) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/tasks/self`, {
    method: "POST",
    body: JSON.stringify({ title, description, rewards }),
  });
  return r.json() as Promise<{ task: GameTask; session: Session }>;
}

export async function completeTask(sid: string, task_id: string) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/tasks/${task_id}/complete`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  return r.json() as Promise<{ task?: GameTask; pay?: number; session: Session }>;
}

export async function getFinance(sid: string) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/finance`);
  return r.json() as Promise<{ finance: FinanceSnapshot; tick: number }>;
}

export async function financeShock(
  sid: string,
  body: {
    kind: "supply" | "demand" | "price" | string;
    good_id?: string;
    magnitude?: number;
    duration?: number;
    note?: string;
  },
) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/finance/shock`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json() as Promise<{
    shock: FinanceSnapshot["shocks"][number];
    finance: FinanceSnapshot;
    session: Session;
  }>;
}

export async function advanceFinance(sid: string, steps = 24) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/finance/advance`, {
    method: "POST",
    body: JSON.stringify({ steps }),
  });
  return r.json() as Promise<{
    steps: number;
    finance: FinanceSnapshot;
    session: Session;
    events?: { kind: string; summary: string }[];
  }>;
}

export type LabEvent = {
  id: string;
  at_step: number;
  title: string;
  kind: string;
  magnitude: number;
  note: string;
};

export async function labGlobalForecast(sid: string, horizon = 24) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/finance/lab/global/forecast`, {
    method: "POST",
    body: JSON.stringify({ horizon }),
  });
  return r.json();
}

export async function labGlobalEvent(
  sid: string,
  body: { at_step: number; title: string; kind?: string; magnitude?: number; note?: string },
) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/finance/lab/global/event`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function labCityForecast(sid: string, horizon = 24, cityKey?: string) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/finance/lab/city/forecast`, {
    method: "POST",
    body: JSON.stringify({ horizon, city_key: cityKey }),
  });
  return r.json();
}

export async function labCityEvent(
  sid: string,
  body: { at_step: number; title: string; kind?: string; magnitude?: number; note?: string },
) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/finance/lab/city/event`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function labCorporateForecast(
  sid: string,
  body: { horizon?: number; company_name?: string; sector?: string; company_key?: string } = {},
) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/finance/lab/corporate/forecast`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function labCorporateEvent(
  sid: string,
  body: { at_step: number; title: string; kind?: string; magnitude?: number; note?: string },
) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/finance/lab/corporate/event`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function labRetailRun(
  sid: string,
  body: { risk?: string; horizon?: string; capital?: number } = {},
) {
  const r = await apiFetch(`${base}/api/sessions/${sid}/finance/lab/retail/run`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json();
}

// ---------- standalone experiment labs ----------
export type LabMeta = {
  key: string;
  name: string;
  blurb: string;
  status: "ready" | "building" | string;
  accent?: string;
};

export type LabWorkspace = {
  id: string;
  lab_key: string;
  civilization_key?: string;
  civilization_name?: string;
  genre: string;
  meta: LabMeta;
  finance: FinanceSnapshot | null;
  finance_lab: any;
  opinion?: any;
  military?: any;
  policy?: any;
  weather?: any;
  environment?: any;
  population?: any;
  timeline_events?: TimelineEvent[];
  last_report?: LabReport | null;
  status: string;
};

export type TimelineEvent = {
  id?: string;
  time_label?: string;
  at_step: number;
  title: string;
  description?: string;
  magnitude?: number;
  kind?: string;
  source?: string;
  channel_preview?: Record<string, number>;
  entities?: string[];
  rationale?: string;
};

export type LabReport = {
  title: string;
  lab_key: string;
  civilization_key: string;
  civilization_name: string;
  horizon: number;
  dimensions: string[];
  charts: {
    id: string;
    title: string;
    type: string;
    x_key?: string;
    x_label?: string;
    y_label?: string;
    series?: { key: string; label: string; values: number[] }[];
    labels?: string[];
    bins?: { label: string; count: number; start?: number; end?: number }[];
    points?: { x: number; y: number; label?: string }[];
    axes?: { label: string; value: number; raw?: number }[];
    analysis?: string;
  }[];
  tables: { title: string; columns: string[]; rows: (string | number)[][] }[];
  event_impacts: { time: string; title: string; magnitude: number; effect: string }[];
  predictions: {
    dimension: string;
    horizon: number;
    from_value: number;
    to_value: number;
    change_pct: number;
    trend: string;
  }[];
  analysis: { heading: string; body: string }[];
  disclaimer: string;
  conclusion?: string;
  chart_analyses?: { chart_id: string; title: string; body: string }[];
};

export type CivilizationDashboard = {
  seed_key: string;
  name: string;
  genre: string;
  premise: string;
  rules: string[];
  era_label: string;
  population_explanation: string;
  demographics: Record<string, unknown>;
  metrics: { key: string; label: string; value: number; unit: string; display: string }[];
  historical_events: { era: string; title: string; description: string }[];
  factions: { name: string; ideology: string }[];
  locations: { name: string; description: string }[];
  current_state: {
    stage: string;
    government: string;
    operating_logic: string;
    summary: string;
  };
};

export async function getCivilizationDashboard(seedKey: string): Promise<CivilizationDashboard> {
  const r = await apiFetch(`${base}/api/seeds/${seedKey}/dashboard`, { cache: "no-store" as RequestCache });
  const j = await r.json();
  return j.dashboard as CivilizationDashboard;
}

export type CustomCivilizationConfig = {
  name: string;
  class_structure: Record<string, number>;
  age_structure: Record<string, number>;
  operating_logic: string;
  government_form: string;
  professions: { name: string; description?: string; playable?: boolean }[];
  roles: {
    key?: string; name: string; persona?: string; profession?: string;
    goals?: string[]; traits?: string[];
  }[];
  historical_events: { era?: string; title: string; description?: string }[];
  current_stage: string;
};

export async function createCustomCivilization(config: CustomCivilizationConfig) {
  const r = await apiFetch(`${base}/api/civilizations/custom`, {
    method: "POST",
    body: JSON.stringify(config),
  });
  return r.json() as Promise<{ civilization: Seed & { id?: string } }>;
}

export async function listCustomCivilizations() {
  const r = await apiFetch(`${base}/api/civilizations/custom`);
  const j = await r.json();
  return j.civilizations as (Seed & { id: string })[];
}

export async function listLabs(): Promise<LabMeta[]> {
  const r = await apiFetch(`${base}/api/labs`);
  const j = await r.json();
  return j.labs as LabMeta[];
}

export async function openLab(labKey: string, civilizationKey = "modern"): Promise<LabWorkspace> {
  const r = await apiFetch(`${base}/api/labs/${labKey}/open`, {
    method: "POST",
    body: JSON.stringify({ civilization_key: civilizationKey }),
  });
  return r.json() as Promise<LabWorkspace>;
}

export async function rebindLab(labId: string, civilizationKey: string): Promise<LabWorkspace> {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/rebind`, {
    method: "POST",
    body: JSON.stringify({ civilization_key: civilizationKey }),
  });
  return r.json() as Promise<LabWorkspace>;
}

export async function getLabWorkspace(labId: string): Promise<LabWorkspace> {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}`);
  return r.json() as Promise<LabWorkspace>;
}

export async function labWsAdvanceFinance(labId: string, steps = 24) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/finance/advance`, {
    method: "POST",
    body: JSON.stringify({ steps }),
  });
  return r.json();
}

export async function labWsFinanceShock(
  labId: string,
  body: {
    kind: "supply" | "demand" | "price" | string;
    good_id?: string;
    magnitude?: number;
    duration?: number;
    note?: string;
  },
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/finance/shock`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsGlobalForecast(labId: string, horizon = 24) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/finance/lab/global/forecast`, {
    method: "POST",
    body: JSON.stringify({ horizon }),
  });
  return r.json();
}

export async function labWsGlobalEvent(
  labId: string,
  body: { at_step: number; title: string; kind?: string; magnitude?: number; note?: string },
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/finance/lab/global/event`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsCityForecast(labId: string, horizon = 24, cityKey?: string) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/finance/lab/city/forecast`, {
    method: "POST",
    body: JSON.stringify({ horizon, city_key: cityKey }),
  });
  return r.json();
}

export async function labWsCityEvent(
  labId: string,
  body: { at_step: number; title: string; kind?: string; magnitude?: number; note?: string },
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/finance/lab/city/event`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsCorporateForecast(
  labId: string,
  body: { horizon?: number; company_name?: string; sector?: string; company_key?: string } = {},
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/finance/lab/corporate/forecast`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsCorporateEvent(
  labId: string,
  body: { at_step: number; title: string; kind?: string; magnitude?: number; note?: string },
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/finance/lab/corporate/event`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsRetailRun(
  labId: string,
  body: { risk?: string; horizon?: string; capital?: number } = {},
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/finance/lab/retail/run`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsOpinionSimulate(labId: string, body: { steps?: number; topic?: string } = {}) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/opinion/simulate`, {
    method: "POST", body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsOpinionIntervene(labId: string, key: string, note = "") {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/opinion/intervene`, {
    method: "POST", body: JSON.stringify({ key, note }),
  });
  return r.json();
}

export async function labWsMilitaryConfigure(
  labId: string, body: { scenario_key: string; battlefield_key: string },
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/military/configure`, {
    method: "POST", body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsMilitarySimulate(
  labId: string,
  body: { steps?: number; scenario_key?: string; battlefield_key?: string } = {},
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/military/simulate`, {
    method: "POST", body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsPolicySimulate(
  labId: string,
  body: { steps?: number; agency_key?: string; instrument_key?: string } = {},
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/policy/simulate`, {
    method: "POST", body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsWeatherSimulate(
  labId: string,
  body: { steps?: number; role_key?: string; pattern_key?: string } = {},
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/weather/simulate`, {
    method: "POST", body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsEnvironmentSimulate(
  labId: string,
  body: {
    steps?: number; region_key?: string; measure_key?: string;
    emission_intensity?: number; enterprise_name?: string;
  } = {},
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/environment/simulate`, {
    method: "POST", body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsPopulationSimulate(
  labId: string,
  body: { years?: number; scope?: string; region_key?: string; city_key?: string } = {},
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/population/simulate`, {
    method: "POST", body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsPopulationShock(
  labId: string, body: { kind: string; magnitude?: number; note?: string },
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/population/shock`, {
    method: "POST", body: JSON.stringify(body),
  });
  return r.json();
}

export async function labWsPopulationPolicy(labId: string, kind: string, magnitude = 1) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/population/policy`, {
    method: "POST", body: JSON.stringify({ kind, magnitude }),
  });
  return r.json();
}

export async function labWsPopulationCognition(labId: string, kind: string, magnitude = 1) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/population/cognition`, {
    method: "POST", body: JSON.stringify({ kind, magnitude }),
  });
  return r.json();
}

export async function labWsUploadDataset(labId: string, file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/datasets/upload`, {
    method: "POST",
    body: fd,
  });
  return r.json();
}

export async function labWsAddManualEvents(
  labId: string,
  events: { time?: string; title: string; magnitude?: number; kind?: string; description?: string }[],
  useLlmNer = true,
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/events/manual`, {
    method: "POST",
    body: JSON.stringify({
      use_llm_ner: useLlmNer,
      events: events.map((e, i) => ({
        time: e.time || `T+${i * 4}`,
        title: e.title,
        magnitude: e.magnitude ?? 0.15,
        kind: e.kind || "custom",
        description: e.description || "",
      })),
    }),
  });
  return r.json();
}

export async function labWsRunReport(
  labId: string,
  body: { horizon?: number; mode?: string } = {},
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/report/run`, {
    method: "POST",
    body: JSON.stringify({ horizon: body.horizon ?? 24, mode: body.mode ?? "auto" }),
  });
  return r.json();
}

export function downloadPdfBase64(base64: string, filename: string) {
  const bin = atob(base64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  const blob = new Blob([arr], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function labWsFinanceSimulate(
  labId: string,
  body: {
    mode: string;
    horizon?: number;
    city_key?: string;
    company_key?: string;
    company_name?: string;
    sector?: string;
    risk?: string;
    retail_horizon?: string;
    capital?: number;
    market_steps?: number;
    skip_llm?: boolean;
  },
) {
  const r = await apiFetch(`${base}/api/labs/workspace/${labId}/finance/simulate`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return r.json();
}

// ---------- 3D Generator ----------
export type GeneratorStatus = {
  enabled: boolean;
  url: string;
  model: string;
  subfolder: string;
  texture_enabled: boolean;
  online: boolean;
  message: string;
};

export type MapGenerateResult = {
  slug: string;
  prompt: string;
  genre: string;
  png_url: string;
  json_url: string;
  locations: { id: string; name: string; x: number; y: number }[];
};

export type CharacterOutfit = {
  id: string;
  era: string;
  occupation: string;
  label: string;
  blurb: string;
  clothing: string[];
  props: string[];
  prompt: string;
  civilization?: string;
  civilization_name?: string;
  asset_dir?: string;
  meta_url?: string;
  props_urls?: string[];
};

export type GeneratorCivilization = {
  id: string;
  name: string;
  genre: string;
  era: string;
  outfit_count: number;
  default_role?: string;
  character_url?: string;
  catalog_url?: string;
};

export type CharacterGenerateResult = {
  job_id: string | null;
  status: string;
  glb_url?: string | null;
  kind?: string;
  prompt?: string | null;
  source?: string;
  error?: string | null;
  outfit_id?: string | null;
  outfit?: {
    id?: string;
    label?: string;
    era?: string;
    occupation?: string;
    clothing?: string[];
    props?: string[];
  } | null;
};

export async function listGeneratorCivilizations(): Promise<GeneratorCivilization[]> {
  const r = await apiFetch(`${base}/api/generator/civilizations`);
  const j = await r.json();
  return j.civilizations ?? [];
}

export async function listCharacterOutfits(civilization?: string | null): Promise<CharacterOutfit[]> {
  const qs = civilization ? `?civilization=${encodeURIComponent(civilization)}` : "";
  const r = await apiFetch(`${base}/api/generator/outfits${qs}`);
  const j = await r.json();
  return j.outfits ?? [];
}

export async function pollGeneratorJob(jobId: string): Promise<CharacterGenerateResult> {
  const r = await apiFetch(`${base}/api/generator/jobs/${jobId}`);
  return r.json();
}

export async function waitForGeneratorJob(
  jobId: string,
  onProgress?: (job: CharacterGenerateResult) => void,
  maxMs = 2_400_000,
): Promise<CharacterGenerateResult> {
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    const job = await pollGeneratorJob(jobId);
    onProgress?.(job);
    if (job.status === "done") return job;
    if (job.status === "failed") throw new Error(job.error || "生成失败");
    await new Promise((r) => setTimeout(r, 2500));
  }
  throw new Error("生成超时，请稍后重试");
}

/** Fetch GLB with auth — useGLTF cannot send Authorization headers on its own. */
export async function loadGlbBlobUrl(glbPath: string): Promise<string> {
  const url = glbPath.startsWith("http") ? glbPath : `${base}${glbPath}`;
  const r = await apiFetch(url);
  const blob = await r.blob();
  return URL.createObjectURL(blob);
}

export async function getGeneratorStatus(): Promise<GeneratorStatus> {
  const r = await apiFetch(`${base}/api/generator/status`);
  const j = await r.json();
  return j.generator;
}

export async function generateMap3D(
  prompt: string,
  genre?: string,
  civilization?: string,
): Promise<MapGenerateResult> {
  const r = await apiFetch(`${base}/api/generator/map`, {
    method: "POST",
    body: JSON.stringify({
      prompt,
      genre: genre || null,
      civilization: civilization || genre || null,
    }),
  });
  return r.json();
}

export async function generateModelFromText(
  prompt: string,
  kind: "character" | "prop" = "character",
  outfitId?: string | null,
  civilization?: string | null,
): Promise<CharacterGenerateResult> {
  const r = await apiFetch(`${base}/api/generator/model/text`, {
    method: "POST",
    body: JSON.stringify({
      prompt,
      kind,
      outfit_id: kind === "character" ? outfitId || null : null,
      civilization: kind === "character" ? civilization || null : null,
    }),
  });
  const started = await r.json();
  if (started.status === "pending" && started.job_id) {
    return waitForGeneratorJob(started.job_id);
  }
  return started;
}

export async function generateModelFromImage(
  file: File,
  kind: "character" | "prop" = "character",
  prompt = "",
  outfitId?: string | null,
  civilization?: string | null,
): Promise<CharacterGenerateResult> {
  const fd = new FormData();
  fd.append("image", file);
  const qs = new URLSearchParams({ kind, prompt });
  if (kind === "character" && outfitId) qs.set("outfit_id", outfitId);
  if (kind === "character" && civilization) qs.set("civilization", civilization);
  const r = await apiFetch(`${base}/api/generator/model/image?${qs}`, {
    method: "POST",
    body: fd,
  });
  const started = await r.json();
  if (started.status === "pending" && started.job_id) {
    return waitForGeneratorJob(started.job_id);
  }
  return started;
}

/** @deprecated use generateModelFromImage */
export async function generateCharacter3D(file: File, withTexture = false): Promise<CharacterGenerateResult> {
  const fd = new FormData();
  fd.append("image", file);
  const qs = withTexture ? "?with_texture=true" : "";
  const r = await apiFetch(`${base}/api/generator/character${qs}`, {
    method: "POST",
    body: fd,
  });
  return r.json();
}
