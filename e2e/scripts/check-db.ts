import 'dotenv/config'
import { databasePool, verifyTarget } from './database.ts'

async function main() {
  if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL is not configured.')
  const pool = databasePool()
  try {
    const client = await pool.connect()
    try {
      const target = await verifyTarget(client)
      console.log(`Database connection verified: host=${target.host}, database=${target.databaseName}.`)
    } finally {
      client.release()
    }
  } finally {
    await pool.end()
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : 'Database check failed.')
  process.exitCode = 1
})
