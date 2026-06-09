import { MongoClient, Db } from "mongodb";

const uri = process.env.MONGO_URI || "mongodb://localhost:27017";
const dbName = process.env.MONGO_DB_NAME || "dulichapp";

let globalWithMongo = global as typeof globalThis & {
  _mongoClientPromise?: Promise<MongoClient>;
};

let client: MongoClient;
let clientPromise: Promise<MongoClient>;

if (process.env.NODE_ENV === "development") {
  if (!globalWithMongo._mongoClientPromise) {
    client = new MongoClient(uri, {
      serverSelectionTimeoutMS: 3000,
    });
    globalWithMongo._mongoClientPromise = client.connect();
  }
  clientPromise = globalWithMongo._mongoClientPromise;
} else {
  client = new MongoClient(uri, {
    serverSelectionTimeoutMS: 3000,
  });
  clientPromise = client.connect();
}

export async function connectToDatabase(): Promise<{ client: MongoClient; db: Db }> {
  const connClient = await clientPromise;
  const db = connClient.db(dbName);
  return { client: connClient, db };
}
