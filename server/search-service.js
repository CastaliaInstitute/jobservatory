const SERVICE_VERSION = "jobservatory-search-api-v1";
const RESPONSE_VERSION = "jobservatory.search-response.v1";
const TOKEN_PATTERN = /[a-z0-9+#.]{2,}/g;
const MAX_QUERY_LENGTH = 256;
const MAX_LIMIT = 50;
const RESULT_CACHE_LIMIT = 100;

let loadedIndexPromise;
const resultCache = new Map();

export const tokenize = value => value.toLowerCase().match(TOKEN_PATTERN) || [];

const hex = buffer => Array.from(new Uint8Array(buffer), value => value.toString(16).padStart(2, "0")).join("");
const json = (value, status = 200, headers = {}) => new Response(`${JSON.stringify(value)}\n`, {
  status,
  headers: {
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": "no-store",
    "Content-Type": "application/json; charset=utf-8",
    "X-Content-Type-Options": "nosniff",
    ...headers,
  },
});

async function loadIndex(env, requestUrl) {
  const cacheHit = Boolean(loadedIndexPromise);
  if (!loadedIndexPromise) {
    loadedIndexPromise = (async () => {
      const manifestResponse = await env.ASSETS.fetch(new URL("/api/search/manifest-v1.json", requestUrl));
      if (!manifestResponse.ok) throw new Error(`serving manifest unavailable: ${manifestResponse.status}`);
      const manifest = await manifestResponse.json();
      if (manifest.schemaVersion !== "jobservatory.serving-index-manifest.v1" || manifest.serviceVersion !== SERVICE_VERSION) {
        throw new Error("serving manifest contract mismatch");
      }
      const indexResponse = await env.ASSETS.fetch(new URL(manifest.index.path, requestUrl));
      if (!indexResponse.ok) throw new Error(`serving index unavailable: ${indexResponse.status}`);
      const bytes = await indexResponse.arrayBuffer();
      if (bytes.byteLength !== manifest.index.bytes) throw new Error("serving index byte length mismatch");
      const digest = `sha256:${hex(await crypto.subtle.digest("SHA-256", bytes))}`;
      if (digest !== manifest.index.sha256) throw new Error("serving index hash mismatch");
      const index = JSON.parse(new TextDecoder().decode(bytes));
      if (
        index.schemaVersion !== "jobservatory.serving-index.v1"
        || index.documents.length !== manifest.index.documents
        || index.statistics.documents !== manifest.index.documents
        || index.model.modelId !== manifest.model.modelId
        || index.corpus.contentSha256 !== manifest.corpus.contentSha256
      ) throw new Error("serving index lineage mismatch");
      return { manifest, index };
    })().catch(error => {
      loadedIndexPromise = undefined;
      throw error;
    });
  }
  return { ...(await loadedIndexPromise), cacheHit };
}

function parseRequest(request) {
  const url = new URL(request.url);
  const query = (url.searchParams.get("q") || "").trim().replace(/\s+/g, " ");
  if (query.length < 2 || query.length > MAX_QUERY_LENGTH) return { error: "q must contain 2 to 256 characters" };
  const queryTerms = [...new Set(tokenize(query))];
  if (!queryTerms.length) return { error: "q must contain at least one searchable token" };
  const rawLimit = url.searchParams.get("limit") || "20";
  if (!/^\d+$/.test(rawLimit)) return { error: "limit must be an integer" };
  const limit = Number(rawLimit);
  if (limit < 1 || limit > MAX_LIMIT) return { error: `limit must be between 1 and ${MAX_LIMIT}` };
  const rawMinimumPay = url.searchParams.get("minimumPay");
  const minimumPay = rawMinimumPay === null ? null : Number(rawMinimumPay);
  if (rawMinimumPay !== null && (!Number.isFinite(minimumPay) || minimumPay < 0 || minimumPay > 10_000_000)) {
    return { error: "minimumPay must be a number between 0 and 10000000" };
  }
  return {
    query,
    queryTerms,
    limit,
    filters: {
      domain: (url.searchParams.get("domain") || "").trim() || null,
      seniority: (url.searchParams.get("seniority") || "").trim() || null,
      location: (url.searchParams.get("location") || "").trim() || null,
      minimumPay,
    },
  };
}

const matchesFilters = (document, filters) => {
  if (filters.domain && document.domain.toLowerCase() !== filters.domain.toLowerCase()) return false;
  if (filters.seniority && document.seniority.toLowerCase() !== filters.seniority.toLowerCase()) return false;
  if (filters.location && !document.location.toLowerCase().includes(filters.location.toLowerCase())) return false;
  if (filters.minimumPay !== null && (!document.compensation || document.compensation.maximum < filters.minimumPay)) return false;
  return true;
};

function rank(index, parsed) {
  const { k1, b } = index.model.parameters;
  const documents = index.documents;
  const scores = new Map();
  for (const term of parsed.queryTerms) {
    const postings = index.invertedIndex[term];
    if (!postings) continue;
    const documentFrequency = postings.length;
    const inverseDocumentFrequency = Math.log(1 + (documents.length - documentFrequency + 0.5) / (documentFrequency + 0.5));
    for (const [documentIndex, frequency] of postings) {
      const document = documents[documentIndex];
      if (!matchesFilters(document, parsed.filters)) continue;
      const denominator = frequency + k1 * (1 - b + b * document.length / index.statistics.averageDocumentLength);
      const score = inverseDocumentFrequency * frequency * (k1 + 1) / denominator;
      scores.set(documentIndex, (scores.get(documentIndex) || 0) + score);
    }
  }
  const ranked = [...scores.entries()]
    .sort((left, right) => right[1] - left[1] || documents[left[0]].observationId.localeCompare(documents[right[0]].observationId));
  return {
    totalCandidates: ranked.length,
    results: ranked.slice(0, parsed.limit).map(([documentIndex, score], rankIndex) => {
      const document = documents[documentIndex];
      return {
        rank: rankIndex + 1,
        observationId: document.observationId,
        employer: document.employer,
        title: document.title,
        location: document.location,
        seniority: document.seniority,
        domain: document.domain,
        compensation: document.compensation,
        sourceUrl: document.sourceUrl,
        score: Number(score.toFixed(8)),
        componentScores: { bm25: Number(score.toFixed(8)) },
      };
    }),
  };
}

function cacheResult(key, value) {
  if (resultCache.has(key)) resultCache.delete(key);
  resultCache.set(key, value);
  if (resultCache.size > RESULT_CACHE_LIMIT) resultCache.delete(resultCache.keys().next().value);
}

const allKeyboardSafeHeaders = (requestId, manifest, timing) => ({
  "Server-Timing": `index;dur=${timing.indexLoadMs.toFixed(2)}, rank;dur=${timing.rankMs.toFixed(2)}, total;dur=${timing.totalMs.toFixed(2)}`,
  "Timing-Allow-Origin": "*",
  "X-Jobservatory-Index": manifest.index.sha256,
  "X-Jobservatory-Model": manifest.model.modelId,
  "X-Jobservatory-Request-Id": requestId,
  "X-Jobservatory-Service": SERVICE_VERSION,
  "X-Robots-Tag": "noindex",
});

export async function handleSearch(context) {
  const requestId = crypto.randomUUID();
  if (context.request.method === "OPTIONS") return new Response(null, { status: 204, headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, OPTIONS", "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "86400" } });
  if (context.request.method !== "GET") return json({ schemaVersion: RESPONSE_VERSION, error: { code: "method_not_allowed", message: "Only GET and OPTIONS are supported." }, requestId }, 405, { Allow: "GET, OPTIONS" });
  const parsed = parseRequest(context.request);
  if (parsed.error) return json({ schemaVersion: RESPONSE_VERSION, error: { code: "invalid_request", message: parsed.error }, requestId }, 400);
  const started = performance.now();
  try {
    const indexStarted = performance.now();
    const { manifest, index, cacheHit: indexCacheHit } = await loadIndex(context.env, context.request.url);
    const indexLoadMs = performance.now() - indexStarted;
    const cacheKey = JSON.stringify([manifest.index.sha256, parsed.queryTerms, parsed.limit, parsed.filters]);
    const resultCacheHit = resultCache.has(cacheKey);
    const rankStarted = performance.now();
    const ranked = resultCacheHit ? resultCache.get(cacheKey) : rank(index, parsed);
    if (!resultCacheHit) cacheResult(cacheKey, ranked);
    const rankMs = performance.now() - rankStarted;
    const totalMs = performance.now() - started;
    const timing = { indexLoadMs, rankMs, totalMs, indexCacheHit, resultCacheHit };
    console.log(JSON.stringify({ event: "search_request", requestId, serviceVersion: SERVICE_VERSION, queryLength: parsed.query.length, queryTerms: parsed.queryTerms.length, filters: Object.fromEntries(Object.entries(parsed.filters).map(([key, value]) => [key, value !== null])), results: ranked.results.length, totalCandidates: ranked.totalCandidates, timing }));
    return json({
      schemaVersion: RESPONSE_VERSION,
      requestId,
      query: parsed.query,
      filters: parsed.filters,
      totalCandidates: ranked.totalCandidates,
      results: ranked.results,
      lineage: { serviceVersion: SERVICE_VERSION, modelId: manifest.model.modelId, indexSha256: manifest.index.sha256, corpusGeneratedAt: manifest.corpus.generatedAt, corpusContentSha256: manifest.corpus.contentSha256, promotionStatus: manifest.promotion.status },
      timing,
    }, 200, allKeyboardSafeHeaders(requestId, manifest, timing));
  } catch (error) {
    console.error(JSON.stringify({ event: "search_failure", requestId, serviceVersion: SERVICE_VERSION, error: error instanceof Error ? error.message : "unknown" }));
    return json({ schemaVersion: RESPONSE_VERSION, error: { code: "service_unavailable", message: "The versioned search index is unavailable." }, requestId }, 503, { "Retry-After": "30", "X-Jobservatory-Service": SERVICE_VERSION });
  }
}

export async function handleHealth(context) {
  const started = performance.now();
  try {
    const { manifest, index, cacheHit } = await loadIndex(context.env, context.request.url);
    return json({
      schemaVersion: "jobservatory.search-health.v1",
      status: "ok",
      serviceVersion: SERVICE_VERSION,
      modelId: manifest.model.modelId,
      indexSha256: manifest.index.sha256,
      corpusGeneratedAt: manifest.corpus.generatedAt,
      corpusContentSha256: manifest.corpus.contentSha256,
      documents: index.statistics.documents,
      indexCacheHit: cacheHit,
      responseMs: Number((performance.now() - started).toFixed(3)),
    }, 200, { "X-Jobservatory-Service": SERVICE_VERSION, "X-Jobservatory-Index": manifest.index.sha256, "X-Jobservatory-Model": manifest.model.modelId });
  } catch (error) {
    console.error(JSON.stringify({ event: "health_failure", serviceVersion: SERVICE_VERSION, error: error instanceof Error ? error.message : "unknown" }));
    return json({ schemaVersion: "jobservatory.search-health.v1", status: "unavailable", serviceVersion: SERVICE_VERSION }, 503, { "Retry-After": "30" });
  }
}

export function resetSearchServiceForTests() {
  loadedIndexPromise = undefined;
  resultCache.clear();
}
