type SearchObservation = {
  observationId: string; employer: string; title: string; location: string; seniority: string; domain: string;
  classifications: Record<string, { label: string; evidence: string }[] | unknown>;
};

const tokenize = (text: string) => text.toLowerCase().match(/[a-z0-9+#.]{2,}/g) || [];
const textFor = (item: SearchObservation) => {
  const evidence = ["aiRelationship", "systemLayer", "skills"].flatMap(family => {
    const hits = item.classifications[family];
    return Array.isArray(hits) ? hits.flatMap(hit => [hit.label, hit.evidence]) : [];
  });
  return [item.title, item.employer, item.location, item.seniority, item.domain, ...evidence].join(" ");
};
const hash = (value: string) => {
  let result = 2166136261;
  for (let index = 0; index < value.length; index += 1) { result ^= value.charCodeAt(index); result = Math.imul(result, 16777619); }
  return result >>> 0;
};
const denseVector = (text: string) => {
  const words = tokenize(text.slice(0, 1400));
  const features = [...words.map(word => `w:${word}`), ...words.slice(0, -1).map((word, index) => `w:${word}_${words[index + 1]}`)];
  const vector = new Map<number, number>();
  for (const feature of features) { const digest = hash(feature), bucket = digest % 512; vector.set(bucket, (vector.get(bucket) || 0) + ((digest & 1) ? 1 : -1)); }
  const norm = Math.sqrt(Array.from(vector.values()).reduce((sum, value) => sum + value * value, 0)) || 1;
  vector.forEach((value, key) => vector.set(key, value / norm));
  return vector;
};

export function createHybridIndex(observations: SearchObservation[]) {
  const documents = observations.map(item => { const text = textFor(item), terms = tokenize(text), counts = new Map<string, number>(); terms.forEach(term => counts.set(term, (counts.get(term) || 0) + 1)); return { item, counts, length: terms.length, vector: denseVector(text) }; });
  const averageLength = documents.reduce((sum, document) => sum + document.length, 0) / Math.max(documents.length, 1);
  const documentFrequency = new Map<string, number>();
  documents.forEach(document => document.counts.forEach((_, term) => documentFrequency.set(term, (documentFrequency.get(term) || 0) + 1)));
  return { search(query: string) {
    const queryTerms = tokenize(query), querySet = new Set(queryTerms), queryVector = denseVector(query);
    const bm25 = documents.map(document => { let score = 0; queryTerms.forEach(term => { const frequency = document.counts.get(term) || 0; if (!frequency) return; const df = documentFrequency.get(term) || 0, idf = Math.log(1 + (documents.length - df + .5) / (df + .5)); score += idf * frequency * 2.2 / (frequency + 1.2 * (.25 + .75 * document.length / averageLength)); }); return [document.item.observationId, score] as const; }).sort((a, b) => b[1] - a[1]);
    const dense = documents.map(document => { let score = 0; queryVector.forEach((value, key) => { score += value * (document.vector.get(key) || 0); }); return [document.item.observationId, score] as const; }).sort((a, b) => b[1] - a[1]);
    const fused = new Map<string, number>(); [bm25, dense].forEach(run => run.forEach(([id], rank) => fused.set(id, (fused.get(id) || 0) + 1 / (61 + rank))));
    const byId = new Map(documents.map(document => [document.item.observationId, document.item]));
    return Array.from(fused.entries()).map(([id, score]) => { const item = byId.get(id)!, title = new Set(tokenize(item.title)), metadata = new Set(tokenize(`${item.seniority} ${item.domain} ${item.location}`)); const titleCoverage = Array.from(querySet).filter(term => title.has(term)).length / Math.max(querySet.size, 1), metadataCoverage = Array.from(querySet).filter(term => metadata.has(term)).length / Math.max(querySet.size, 1); return { item, score: score + .08 * titleCoverage + .03 * metadataCoverage }; }).sort((a, b) => b.score - a.score);
  }};
}
