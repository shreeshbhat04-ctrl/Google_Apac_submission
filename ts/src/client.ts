import {
  AlloyNativeTransport,
  SearchRequest,
  SearchResponse,
  UpsertRequest,
  UpsertResponse,
} from "./types";

export interface AlloyDBClientOptions {
  transport: AlloyNativeTransport;
  defaultEmbeddingModel?: string;
  defaultRerankModel?: string;
}

export interface AlloyIndexOptions {
  table: string;
  idColumn?: string;
  textColumns?: string[];
  metadataColumn?: string;
  embeddingColumn?: string;
  embeddingModel?: string;
  embeddingSourceColumn?: string;
}

export interface AlloyIndexQueryOptions {
  filters?: SearchRequest["filters"];
  joinFilter?: SearchRequest["joinFilter"];
  limit?: number;
  rerank?: boolean;
  rerankModel?: string;
  returnColumns?: string[];
  candidateLimit?: number;
  joinTable?: string;
  leftJoinColumn?: string;
  rightJoinColumn?: string;
}

export interface AlloyIndexUpsertOptions {
  embeddingSourceColumn?: string;
  idColumn?: string;
  embeddingModel?: string;
}

export class AlloyDBClient {
  private readonly transport: AlloyNativeTransport;
  private readonly defaultEmbeddingModel: string;
  private readonly defaultRerankModel: string;

  private constructor(options: AlloyDBClientOptions) {
    this.transport = options.transport;
    this.defaultEmbeddingModel =
      options.defaultEmbeddingModel ?? "text-embedding-005";
    this.defaultRerankModel =
      options.defaultRerankModel ?? "gemini-2.0-flash-global";
  }

  static async connect(options: AlloyDBClientOptions): Promise<AlloyDBClient> {
    return new AlloyDBClient(options);
  }

  async upsertRows(request: UpsertRequest): Promise<UpsertResponse> {
    return this.transport.upsert({
      ...request,
      embeddingModel: request.embeddingModel ?? this.defaultEmbeddingModel,
    });
  }

  async upsertRawText(request: UpsertRequest): Promise<UpsertResponse> {
    return this.upsertRows(request);
  }

  async searchHybrid(request: SearchRequest): Promise<SearchResponse> {
    return this.transport.search({
      ...request,
      embeddingModel: request.embeddingModel ?? this.defaultEmbeddingModel,
      rerankModel: request.rerankModel ?? this.defaultRerankModel,
    });
  }

  index(options: AlloyIndexOptions): AlloyIndex {
    return new AlloyIndex(this, options);
  }
}

export class AlloyIndex {
  private readonly client: AlloyDBClient;
  private readonly options: Required<
    Pick<
      AlloyIndexOptions,
      "table" | "idColumn" | "textColumns" | "embeddingColumn"
    >
  > &
    Pick<AlloyIndexOptions, "metadataColumn" | "embeddingModel" | "embeddingSourceColumn">;

  constructor(client: AlloyDBClient, options: AlloyIndexOptions) {
    this.client = client;
    this.options = {
      table: options.table,
      idColumn: options.idColumn ?? "id",
      textColumns: options.textColumns ?? ["content"],
      metadataColumn: options.metadataColumn ?? "metadata",
      embeddingColumn: options.embeddingColumn ?? "embedding",
      embeddingModel: options.embeddingModel,
      embeddingSourceColumn: options.embeddingSourceColumn,
    };
  }

  async upsert(
    rows: UpsertRequest["rows"],
    options: AlloyIndexUpsertOptions = {},
  ): Promise<UpsertResponse> {
    const embeddingSourceColumn =
      options.embeddingSourceColumn ?? this.options.embeddingSourceColumn;

    if (!embeddingSourceColumn) {
      throw new Error(
        "embeddingSourceColumn is required unless the index was created with a default.",
      );
    }

    return this.client.upsertRows({
      table: this.options.table,
      rows,
      embeddingSourceColumn,
      embeddingColumn: this.options.embeddingColumn,
      idColumn: options.idColumn ?? this.options.idColumn,
      embeddingModel: options.embeddingModel ?? this.options.embeddingModel,
    });
  }

  async query(
    query: string,
    options: AlloyIndexQueryOptions = {},
  ): Promise<SearchResponse> {
    return this.client.searchHybrid({
      table: this.options.table,
      query,
      filters: options.filters,
      joinFilter: options.joinFilter,
      limit: options.limit,
      rerank: options.rerank,
      rerankModel: options.rerankModel,
      idColumn: this.options.idColumn,
      textColumns: this.options.textColumns,
      metadataColumn: this.options.metadataColumn,
      returnColumns: options.returnColumns,
      embeddingColumn: this.options.embeddingColumn,
      candidateLimit: options.candidateLimit,
      joinTable: options.joinTable,
      leftJoinColumn: options.leftJoinColumn,
      rightJoinColumn: options.rightJoinColumn,
      embeddingModel: this.options.embeddingModel,
    });
  }
}
