#!/usr/bin/env node
// Removes GITHUB_PERSONAL_ACCESS_TOKEN from .env once GitHub reports it expired or revoked.
//   node scripts/expire-github-token.mjs           check with GitHub, delete only if no longer valid
//   node scripts/expire-github-token.mjs --force   delete without checking
// Only the local copy is deleted; GitHub itself already rejects an expired token.
import { readFileSync, writeFileSync } from 'node:fs'
import { parseEnv } from 'node:util'

const KEY = 'GITHUB_PERSONAL_ACCESS_TOKEN'
const envFile = new URL('../.env', import.meta.url)

let text
try {
  text = readFileSync(envFile, 'utf8')
} catch (err) {
  if (err.code !== 'ENOENT') throw err
  console.log('No .env file; nothing to delete.')
  process.exit(0)
}

const token = parseEnv(text)[KEY]
if (!token) {
  console.log(`${KEY} is not in .env; nothing to delete.`)
  process.exit(0)
}

function removeToken() {
  const eol = text.includes('\r\n') ? '\r\n' : '\n'
  // Drop only the token line; any other settings in .env stay as they are
  const kept = text.split(/\r?\n/).filter(line => !new RegExp(`^\\s*(export\\s+)?${KEY}\\s*=`).test(line))
  writeFileSync(envFile, kept.join(eol))
  console.log(`Removed ${KEY} from .env.`)
}

if (process.argv.includes('--force')) {
  removeToken()
  process.exit(0)
}

// A network error throws here and leaves .env untouched
const res = await fetch('https://api.github.com/user', {
  headers: { Authorization: `Bearer ${token}`, 'User-Agent': 'inventory-management-token-check' },
})
if (res.status === 401) {
  console.log('GitHub rejected the token (expired or revoked).')
  removeToken()
} else if (res.ok) {
  // GitHub reports the expiry of the calling token in this header, e.g. "2026-11-10 12:00:00 +0100"
  const expires = res.headers.get('github-authentication-token-expiration')
  console.log(`Token is still valid${expires ? ` until ${expires}` : ' and has no expiry date'}; nothing deleted.`)
} else {
  console.error(`Unexpected response ${res.status} from GitHub; .env left unchanged.`)
  process.exit(1)
}
