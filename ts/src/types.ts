export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonObject
  | JsonValue[];

export interface JsonObject {
  [key: string]: JsonValue;
}

export type FilterValue = string | number | boolean | Array<string | number | boolean>;

export interface UpsertRequest {
  table: string;
  rows: JsonObject[];
  embeddingSourceColumn: string;
  embeddingModel?: string;
  embeddingColumn?: string;
  idColumn?: string;
}

export interface UpsertResponse {
  count: number;
  ids: string[];
}

export interface SearchRequest {
  table: string;
  query: string;
  filters?: Record<string, FilterValue>;
  joinFilter?: Record<string, FilterValue>;
  limit?: number;
  rerank?: boolean;
  embeddingModel?: string;
  rerankModel?: string;
  idColumn?: string;
  textColumns?: string[];
  metadataColumn?: string;
  returnColumns?: string[];
  embeddingColumn?: string;
  candidateLimit?: number;
  joinTable?: string;
  leftJoinColumn?: string;
  rightJoinColumn?: string;
}

export interface SearchResult {
  id: string;
  content: string;
  payload: JsonObject;
  metadata: JsonObject;
  score: number;
  distance?: number;
}

export interface SearchResponse {
  results: SearchResult[];
  reranked: boolean;
  candidateCount: number;
}

export interface AlloyNativeTransport {
  upsert(request: UpsertRequest): Promise<UpsertResponse>;
  search(request: SearchRequest): Promise<SearchResponse>;
}
