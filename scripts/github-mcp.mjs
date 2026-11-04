#!/usr/bin/env node
// Starts the GitHub MCP server (used by .mcp.json). Takes GITHUB_PERSONAL_ACCESS_TOKEN from the
// environment, or else from the gitignored .env in the repo root, so the token never enters the repo.
import { readFileSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { parseEnv } from 'node:util'

const KEY = 'GITHUB_PERSONAL_ACCESS_TOKEN'
const envFile = new URL('../.env', import.meta.url)

// .mcp.json forwards "${GITHUB_PERSONAL_ACCESS_TOKEN}"; when that variable is unset it arrives
// empty or as the literal "${...}" text, which must not be sent to GitHub as a token
const fromEnvironment = process.env[KEY]
if (!fromEnvironment || fromEnvironment.startsWith('${')) {
  delete process.env[KEY]
  try {
    const token = parseEnv(readFileSync(envFile, 'utf8'))[KEY]
    if (token) process.env[KEY] = token
  } catch (err) {
    if (err.code !== 'ENOENT') throw err
  }
}
// stderr only: stdout carries the MCP protocol
if (!process.env[KEY]) console.error(`[github-mcp] ${KEY} not found: add ${KEY}=<token> to .env`)

// One command string instead of an args array: shell:true is needed for npx on Windows,
// and passing args alongside it triggers Node's DEP0190 warning
const child = spawn('npx -y @modelcontextprotocol/server-github', { stdio: 'inherit', shell: true })
child.on('exit', code => process.exit(code ?? 1))
